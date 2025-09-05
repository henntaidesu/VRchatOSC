#!/usr/bin/env python3
"""
ResEmoteNet情感识别模型
基于ResNet架构的面部情感识别模型
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


class BasicBlock(nn.Module):
    """ResNet基本块"""
    
    def __init__(self, in_channels, out_channels, stride=1):
        super(BasicBlock, self).__init__()
        
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, 
                              stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, 
                              stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        
        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, 
                         stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )
    
    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class ResEmoteNet(nn.Module):
    """ResEmoteNet模型实现"""
    
    def __init__(self, num_classes=7):
        super(ResEmoteNet, self).__init__()
        
        # 简化的ResNet结构用于情感识别
        self.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        
        # ResNet blocks
        self.layer1 = self._make_layer(64, 64, 2)
        self.layer2 = self._make_layer(64, 128, 2, stride=2)
        self.layer3 = self._make_layer(128, 256, 2, stride=2)
        self.layer4 = self._make_layer(256, 512, 2, stride=2)
        
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512, num_classes)
        
    def _make_layer(self, in_channels, out_channels, blocks, stride=1):
        layers = []
        
        # 第一个块可能需要下采样
        layers.append(BasicBlock(in_channels, out_channels, stride))
        
        # 其余块
        for _ in range(1, blocks):
            layers.append(BasicBlock(out_channels, out_channels))
            
        return nn.Sequential(*layers)
    
    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        
        return x


class ResEmoteNetDetector:
    """ResEmoteNet情感检测器"""
    
    def __init__(self, device='auto', model_weights_path=None):
        """
        初始化ResEmoteNet检测器
        
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
        
        self.logger.info(f"ResEmoteNet使用设备: {self.device}")
        
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
        """加载ResEmoteNet模型"""
        try:
            self.model = ResEmoteNet(num_classes=7)
            
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
                self.logger.info(f"成功加载ResEmoteNet权重: {weights_path}")
            else:
                self.logger.warning(f"未找到权重文件 {weights_path}，使用随机初始化权重")
                # 创建占位符权重文件
                self._create_placeholder_weights(weights_path)
            
            self.model.to(self.device)
            self.model.eval()
            
        except Exception as e:
            self.logger.error(f"加载ResEmoteNet模型失败: {e}")
            raise
    
    def _get_default_weights_path(self):
        """获取默认权重文件路径"""
        weights_dir = Path("models/resemotenet")
        weights_dir.mkdir(parents=True, exist_ok=True)
        return str(weights_dir / "resemotenet_weights.pth")
    
    def _create_placeholder_weights(self, weights_path):
        """创建占位符权重文件"""
        try:
            weights_dir = Path(weights_path).parent
            weights_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存随机初始化的权重作为占位符，使用ResEmoteNet模型结构
            placeholder_model = ResEmoteNet(num_classes=7)
            torch.save(placeholder_model.state_dict(), weights_path)
            self.logger.info(f"创建ResEmoteNet占位符权重: {weights_path}")
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
            
            # 调整大小到48x48 (ResEmoteNet输入尺寸)
            face_resized = cv2.resize(gray, (48, 48))
            
            # 归一化到[0,1]
            face_normalized = face_resized.astype(np.float32) / 255.0
            
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
        """将情感转换为VRChat表情参数"""
        expressions = self._get_default_expressions()
        
        # 根据情感类型调整表情参数
        if emotion_name == 'Happy':
            # 快乐 -> 增强微笑
            expressions['smile'] = min(1.0, confidence * 1.5)
        elif emotion_name == 'Surprise':
            # 惊讶 -> 张嘴 + 眨眼
            expressions['mouth_open'] = min(1.0, confidence * 1.2)
            expressions['eyeblink_left'] = min(1.0, confidence * 0.8)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.8)
        elif emotion_name == 'Sad':
            # 悲伤 -> 轻微眨眼
            expressions['eyeblink_left'] = min(1.0, confidence * 0.6)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.6)
        elif emotion_name == 'Angry':
            # 愤怒 -> 无特殊表情，保持中性
            pass
        elif emotion_name == 'Fear':
            # 恐惧 -> 眨眼
            expressions['eyeblink_left'] = min(1.0, confidence * 0.7)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.7)
        elif emotion_name == 'Disgust':
            # 厌恶 -> 轻微张嘴
            expressions['mouth_open'] = min(1.0, confidence * 0.5)
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
                gray, 1.1, 4, minSize=(100, 100)
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
                
                # 绘制面部框
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # 显示情感信息
                text = f"ResEmoteNet: {emotion_name} ({confidence:.2f})"
                cv2.putText(annotated_frame, text, (x, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # 显示情感参数
                y_offset = y + h + 20
                for expr_name, value in expressions.items():
                    if value > 0.05:  # 只显示有显著值的情感
                        display_name = {
                            'angry': '愤怒',
                            'disgust': '厌恶',
                            'fear': '恐惧',
                            'happy': '高兴',
                            'sad': '伤心',
                            'surprise': '惊讶',
                            'neutral': '中立'
                        }.get(expr_name, expr_name)
                        
                        text = f"{display_name}: {value:.2f}"
                        cv2.putText(annotated_frame, text, (x, y_offset), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
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
                
            self.logger.info("ResEmoteNet资源已释放")
            
        except Exception as e:
            self.logger.error(f"释放ResEmoteNet资源时出错: {e}")