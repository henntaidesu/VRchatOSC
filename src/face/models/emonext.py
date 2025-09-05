#!/usr/bin/env python3
"""
EmoNeXt情感识别模型
基于ConvNeXt架构的现代化面部情感识别模型
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import cv2
import numpy as np
from typing import Dict, Tuple, Optional
import logging
import os
from pathlib import Path


class LayerNorm(nn.Module):
    """LayerNorm支持两种数据格式: channels_last (default) or channels_first."""
    
    def __init__(self, normalized_shape, eps=1e-6, data_format="channels_last"):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.bias = nn.Parameter(torch.zeros(normalized_shape))
        self.eps = eps
        self.data_format = data_format
        if self.data_format not in ["channels_last", "channels_first"]:
            raise NotImplementedError 
        self.normalized_shape = (normalized_shape, )
    
    def forward(self, x):
        if self.data_format == "channels_last":
            return F.layer_norm(x, self.normalized_shape, self.weight, self.bias, self.eps)
        elif self.data_format == "channels_first":
            u = x.mean(1, keepdim=True)
            s = (x - u).pow(2).mean(1, keepdim=True)
            x = (x - u) / torch.sqrt(s + self.eps)
            x = self.weight[:, None, None] * x + self.bias[:, None, None]
            return x


class Block(nn.Module):
    """ConvNeXt基本块"""
    
    def __init__(self, dim, drop_path=0., layer_scale_init_value=1e-6):
        super().__init__()
        self.dwconv = nn.Conv2d(dim, dim, kernel_size=7, padding=3, groups=dim)  # depthwise conv
        self.norm = LayerNorm(dim, eps=1e-6)
        self.pwconv1 = nn.Linear(dim, 4 * dim)  # pointwise/1x1 convs, implemented with linear layers
        self.act = nn.GELU()
        self.pwconv2 = nn.Linear(4 * dim, dim)
        self.gamma = nn.Parameter(layer_scale_init_value * torch.ones((dim)), 
                                 requires_grad=True) if layer_scale_init_value > 0 else None
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()

    def forward(self, x):
        input = x
        x = self.dwconv(x)
        x = x.permute(0, 2, 3, 1)  # (N, C, H, W) -> (N, H, W, C)
        x = self.norm(x)
        x = self.pwconv1(x)
        x = self.act(x)
        x = self.pwconv2(x)
        if self.gamma is not None:
            x = self.gamma * x
        x = x.permute(0, 3, 1, 2)  # (N, H, W, C) -> (N, C, H, W)

        x = input + self.drop_path(x)
        return x


class DropPath(nn.Module):
    """Drop paths (Stochastic Depth)"""
    def __init__(self, drop_prob=None):
        super(DropPath, self).__init__()
        self.drop_prob = drop_prob

    def forward(self, x):
        if self.drop_prob == 0. or not self.training:
            return x
        keep_prob = 1 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = keep_prob + torch.rand(shape, dtype=x.dtype, device=x.device)
        random_tensor.floor_()
        output = x.div(keep_prob) * random_tensor
        return output


class EmoNeXtModel(nn.Module):
    """EmoNeXt模型 - 基于ConvNeXt的情感识别模型"""
    
    def __init__(self, num_classes=7, 
                 depths=[2, 2, 6, 2], dims=[96, 192, 384, 768],
                 drop_path_rate=0., layer_scale_init_value=1e-6, head_init_scale=1.):
        super().__init__()

        self.downsample_layers = nn.ModuleList()  # stem and 3 intermediate downsampling conv layers
        stem = nn.Sequential(
            nn.Conv2d(1, dims[0], kernel_size=4, stride=4),
            LayerNorm(dims[0], eps=1e-6, data_format="channels_first")
        )
        self.downsample_layers.append(stem)
        for i in range(3):
            downsample_layer = nn.Sequential(
                    LayerNorm(dims[i], eps=1e-6, data_format="channels_first"),
                    nn.Conv2d(dims[i], dims[i+1], kernel_size=2, stride=2),
            )
            self.downsample_layers.append(downsample_layer)

        self.stages = nn.ModuleList()  # 4 feature resolution stages, each consisting of multiple residual blocks
        dp_rates = [x.item() for x in torch.linspace(0, drop_path_rate, sum(depths))]
        cur = 0
        for i in range(4):
            stage = nn.Sequential(
                *[Block(dim=dims[i], drop_path=dp_rates[cur + j], 
                        layer_scale_init_value=layer_scale_init_value) for j in range(depths[i])]
            )
            self.stages.append(stage)
            cur += depths[i]

        self.norm = nn.LayerNorm(dims[-1], eps=1e-6)  # final norm layer
        self.head = nn.Linear(dims[-1], num_classes)

        self.apply(self._init_weights)
        self.head.weight.data.mul_(head_init_scale)
        self.head.bias.data.mul_(head_init_scale)

    def _init_weights(self, m):
        if isinstance(m, (nn.Conv2d, nn.Linear)):
            nn.init.trunc_normal_(m.weight, std=.02)
            nn.init.constant_(m.bias, 0)

    def forward_features(self, x):
        for i in range(4):
            x = self.downsample_layers[i](x)
            x = self.stages[i](x)
        return self.norm(x.mean([-2, -1]))  # global average pooling, (N, C, H, W) -> (N, C)

    def forward(self, x):
        x = self.forward_features(x)
        x = self.head(x)
        return x


class EmoNeXtDetector:
    """EmoNeXt情感检测器"""
    
    def __init__(self, device='auto', model_weights_path=None):
        """
        初始化EmoNeXt检测器
        
        Args:
            device: 计算设备 ('cuda', 'cpu', 或 'auto')
            model_weights_path: 模型权重文件路径
        """
        self.logger = logging.getLogger(__name__)
        
        # 设置设备
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.logger.info(f"EmoNeXt使用设备: {self.device}")
        
        # 情感标签 (7种基本情感)
        self.emotion_labels = [
            'Angry',     # 愤怒
            'Disgust',   # 厌恶  
            'Fear',      # 恐惧
            'Happy',     # 快乐
            'Sad',       # 悲伤
            'Surprise',  # 惊讶
            'Neutral'    # 中性
        ]
        
        # 面部检测器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # 初始化模型
        self.model = None
        self.load_model(model_weights_path)
        
        # 表情历史用于平滑
        self.emotion_history = []
        self.history_size = 5
    
    def load_model(self, weights_path=None):
        """加载EmoNeXt模型"""
        try:
            # EmoNeXt-Tiny配置
            self.model = EmoNeXtModel(
                num_classes=7,
                depths=[2, 2, 6, 2], 
                dims=[48, 96, 192, 384],  # 适用于48x48输入的较小配置
                drop_path_rate=0.1,
                layer_scale_init_value=1e-6
            )
            
            if weights_path is None:
                weights_path = self._get_default_weights_path()
            
            # 加载权重
            if os.path.exists(weights_path):
                checkpoint = torch.load(weights_path, map_location=self.device)
                if 'state_dict' in checkpoint:
                    self.model.load_state_dict(checkpoint['state_dict'])
                elif 'model_state_dict' in checkpoint:
                    self.model.load_state_dict(checkpoint['model_state_dict'])
                else:
                    self.model.load_state_dict(checkpoint)
                self.logger.info(f"成功加载EmoNeXt权重: {weights_path}")
            else:
                self.logger.warning(f"未找到权重文件 {weights_path}，使用随机初始化权重")
                # 创建占位符权重文件
                self._create_placeholder_weights(weights_path)
            
            self.model.to(self.device)
            self.model.eval()
            
        except Exception as e:
            self.logger.error(f"加载EmoNeXt模型失败: {e}")
            raise
    
    def _get_default_weights_path(self):
        """获取默认权重文件路径"""
        weights_dir = Path("models/emonext")
        weights_dir.mkdir(parents=True, exist_ok=True)
        return str(weights_dir / "emonext_weights.pth")
    
    def _create_placeholder_weights(self, weights_path):
        """创建占位符权重文件"""
        try:
            weights_dir = Path(weights_path).parent
            weights_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存随机初始化的权重作为占位符，使用EmoNeXt模型结构
            placeholder_model = EmoNeXtModel(
                num_classes=7,
                depths=[2, 2, 6, 2], 
                dims=[48, 96, 192, 384],
                drop_path_rate=0.1,
                layer_scale_init_value=1e-6
            )
            torch.save(placeholder_model.state_dict(), weights_path)
            self.logger.info(f"创建EmoNeXt占位符权重: {weights_path}")
        except Exception as e:
            self.logger.warning(f"创建占位符权重失败: {e}")
    
    def preprocess_face(self, face_img):
        """预处理面部图像"""
        try:
            # 转换为灰度图
            if len(face_img.shape) == 3:
                gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = face_img
            
            # 调整大小到48x48
            face_resized = cv2.resize(gray, (48, 48))
            
            # 归一化到[0,1]并标准化
            face_normalized = face_resized.astype(np.float32) / 255.0
            # ImageNet标准化(适配ConvNeXt)
            face_normalized = (face_normalized - 0.485) / 0.229
            
            # 转换为PyTorch张量 [1, 1, 48, 48]
            face_tensor = torch.from_numpy(face_normalized).unsqueeze(0).unsqueeze(0)
            return face_tensor.to(self.device)
            
        except Exception as e:
            self.logger.error(f"面部图像预处理失败: {e}")
            raise
    
    def detect_emotion_single_face(self, face_img):
        """检测单个面部的情感"""
        try:
            # 预处理
            input_tensor = self.preprocess_face(face_img)
            
            # 推理
            with torch.no_grad():
                outputs = self.model(input_tensor)
                probabilities = F.softmax(outputs, dim=1)
                predicted_emotion_idx = torch.argmax(probabilities, dim=1).item()
                confidence = probabilities[0][predicted_emotion_idx].item()
            
            # 获取情感名称
            emotion_name = self.emotion_labels[predicted_emotion_idx]
            
            # 直接返回7种情感的概率分布
            expressions = self._probabilities_to_expressions(probabilities[0])
            
            return expressions, emotion_name, confidence
            
        except Exception as e:
            self.logger.error(f"情感检测失败: {e}")
            return self._get_default_expressions(), 'Neutral', 0.0
    
    def _emotion_to_expressions(self, emotion_name, confidence):
        """将情感转换为VRChat表情参数 (EmoNeXt优化版本)"""
        expressions = self._get_default_expressions()
        
        # EmoNeXt的高精度情感映射
        if emotion_name == 'Happy':
            # 快乐 -> 强烈微笑
            expressions['smile'] = min(1.0, confidence * 2.0)
        elif emotion_name == 'Surprise':
            # 惊讶 -> 张嘴 + 眨眼 (更强烈的反应)
            expressions['mouth_open'] = min(1.0, confidence * 1.5)
            expressions['eyeblink_left'] = min(1.0, confidence * 1.0)
            expressions['eyeblink_right'] = min(1.0, confidence * 1.0)
        elif emotion_name == 'Sad':
            # 悲伤 -> 眨眼 (模拟哭泣)
            expressions['eyeblink_left'] = min(1.0, confidence * 0.8)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.8)
        elif emotion_name == 'Angry':
            # 愤怒 -> 轻微张嘴 (咬牙)
            expressions['mouth_open'] = min(1.0, confidence * 0.5)
        elif emotion_name == 'Fear':
            # 恐惧 -> 眨眼 + 张嘴 (恐惧表情)
            expressions['eyeblink_left'] = min(1.0, confidence * 0.9)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.9)
            expressions['mouth_open'] = min(1.0, confidence * 0.4)
        elif emotion_name == 'Disgust':
            # 厌恶 -> 张嘴 (皱眉表情)
            expressions['mouth_open'] = min(1.0, confidence * 0.7)
        # Neutral 保持默认值
        
        return expressions
    
    def _probabilities_to_expressions(self, probabilities):
        """将模型输出的概率分布转换为7种标准情感"""
        expressions = {}
        for i, emotion_label in enumerate(self.emotion_labels):
            key = emotion_label.lower()  # 转换为小写作为键
            expressions[key] = probabilities[i].item()
        
        return expressions
    
    def _get_default_expressions(self):
        """获取默认表情参数 - 7种标准情感"""
        return {
            'angry': 0.0,      # 愤怒
            'disgust': 0.0,    # 厌恶
            'fear': 0.0,       # 恐惧
            'happy': 0.0,      # 高兴
            'sad': 0.0,        # 伤心
            'surprise': 0.0,   # 惊讶
            'neutral': 1.0     # 中立（默认状态）
        }
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """处理单帧图像，检测面部并识别情感"""
        expressions = self._get_default_expressions()
        
        try:
            # 转换为灰度图进行面部检测
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, 1.05, 2, minSize=(30, 30), maxSize=(300, 300)
            )
            
            annotated_frame = frame.copy()
            
            if len(faces) > 0:
                # 处理第一个检测到的面部
                (x, y, w, h) = faces[0]
                face_roi = frame[y:y+h, x:x+w]
                
                # 检测情感
                expressions, emotion_name, confidence = self.detect_emotion_single_face(face_roi)
                
                # 添加到历史记录并平滑处理
                self.emotion_history.append(expressions)
                if len(self.emotion_history) > self.history_size:
                    self.emotion_history.pop(0)
                
                # 计算平滑后的表情数据
                smoothed_expressions = {}
                for key in expressions.keys():
                    values = [hist[key] for hist in self.emotion_history]
                    smoothed_expressions[key] = np.mean(values)
                
                expressions = smoothed_expressions
                
                # 绘制面部框 (蓝色边框表示EmoNeXt)
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                
                # 显示情感信息
                text = f"EmoNeXt: {emotion_name} ({confidence:.2f})"
                cv2.putText(annotated_frame, text, (x, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                # 显示表情参数
                y_offset = y + h + 20
                for expr_name, value in expressions.items():
                    if value > 0.01:  # 只显示有值的表情
                        display_name = {
                            'eyeblink_left': '左眼',
                            'eyeblink_right': '右眼',
                            'mouth_open': '张嘴',
                            'smile': '微笑'
                        }.get(expr_name, expr_name)
                        
                        if expr_name == 'eyeblink_right':  # 避免重复显示眨眼
                            continue
                            
                        text = f"{display_name}: {value:.2f}"
                        cv2.putText(annotated_frame, text, (x, y_offset), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 128, 0), 1)
                        y_offset += 20
            
            return annotated_frame, expressions
            
        except Exception as e:
            self.logger.error(f"帧处理失败: {e}")
            return frame, expressions
    
    def release(self):
        """释放资源"""
        try:
            if self.model is not None:
                del self.model
                self.model = None
                
            if self.device.type == 'cuda':
                torch.cuda.empty_cache()
                
            self.logger.info("EmoNeXt资源已释放")
            
        except Exception as e:
            self.logger.error(f"释放EmoNeXt资源时出错: {e}")