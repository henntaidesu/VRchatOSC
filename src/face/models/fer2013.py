#!/usr/bin/env python3
"""
FER2013情感识别模型
基于CNN架构的面部情感识别模型，使用FER2013数据集训练
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


class FER2013Model(nn.Module):
    """FER2013 CNN模型"""
    
    def __init__(self, num_classes=7):
        super(FER2013Model, self).__init__()
        
        # 卷积层
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        
        # 池化层
        self.pool = nn.MaxPool2d(2, 2)
        
        # Dropout层
        self.dropout1 = nn.Dropout(0.25)
        self.dropout2 = nn.Dropout(0.5)
        
        # 全连接层
        self.fc1 = nn.Linear(128 * 6 * 6, 512)  # 48x48经过3次池化后是6x6
        self.fc2 = nn.Linear(512, num_classes)
        
        # 批量归一化
        self.bn1 = nn.BatchNorm2d(32)
        self.bn2 = nn.BatchNorm2d(64)
        self.bn3 = nn.BatchNorm2d(128)
        self.bn_fc = nn.BatchNorm1d(512)
    
    def forward(self, x):
        # 第一个卷积块
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.dropout1(x)
        
        # 第二个卷积块  
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.dropout1(x)
        
        # 第三个卷积块
        x = self.pool(F.relu(self.bn3(self.conv3(x))))
        x = self.dropout1(x)
        
        # 扁平化
        x = x.view(-1, 128 * 6 * 6)
        
        # 全连接层
        x = F.relu(self.bn_fc(self.fc1(x)))
        x = self.dropout2(x)
        x = self.fc2(x)
        
        return x


class FER2013Detector:
    """FER2013情感检测器"""
    
    def __init__(self, device='auto', model_weights_path=None):
        """
        初始化FER2013检测器
        
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
        
        self.logger.info(f"FER2013使用设备: {self.device}")
        
        # 情感标签 (FER2013数据集标准7种情感)
        self.emotion_labels = [
            'Angry',     # 0 - 愤怒
            'Disgust',   # 1 - 厌恶
            'Fear',      # 2 - 恐惧  
            'Happy',     # 3 - 快乐
            'Sad',       # 4 - 悲伤
            'Surprise',  # 5 - 惊讶
            'Neutral'    # 6 - 中性
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
        """加载FER2013模型"""
        try:
            self.model = FER2013Model(num_classes=7)
            
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
                self.logger.info(f"成功加载FER2013权重: {weights_path}")
            else:
                self.logger.error(f"未找到FER2013权重文件 {weights_path}，无法使用该模型")
                raise FileNotFoundError(f"FER2013权重文件不存在: {weights_path}")
            
            self.model.to(self.device)
            self.model.eval()
            
        except Exception as e:
            self.logger.error(f"加载FER2013模型失败: {e}")
            raise
    
    def _get_default_weights_path(self):
        """获取默认权重文件路径"""
        weights_dir = Path("models/fer2013")
        weights_dir.mkdir(parents=True, exist_ok=True)
        return str(weights_dir / "fer2013_weights.pth")
    
    
    def preprocess_face(self, face_img):
        """预处理面部图像"""
        try:
            # 转换为灰度图
            if len(face_img.shape) == 3:
                gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = face_img
            
            # 调整大小到48x48 (FER2013标准输入尺寸)
            face_resized = cv2.resize(gray, (48, 48))
            
            # 归一化和标准化
            face_normalized = face_resized.astype(np.float32)
            face_normalized = (face_normalized - 127.5) / 127.5  # [-1, 1]
            
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
        
        # 根据情感类型调整表情参数 (FER2013特定的映射)
        if emotion_name == 'Happy':
            # 快乐 -> 强烈微笑
            expressions['smile'] = min(1.0, confidence * 1.8)
        elif emotion_name == 'Surprise':
            # 惊讶 -> 张嘴 + 眨眼
            expressions['mouth_open'] = min(1.0, confidence * 1.3)
            expressions['eyeblink_left'] = min(1.0, confidence * 0.9)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.9)
        elif emotion_name == 'Sad':
            # 悲伤 -> 眨眼
            expressions['eyeblink_left'] = min(1.0, confidence * 0.7)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.7)
        elif emotion_name == 'Angry':
            # 愤怒 -> 轻微张嘴
            expressions['mouth_open'] = min(1.0, confidence * 0.4)
        elif emotion_name == 'Fear':
            # 恐惧 -> 眨眼 + 轻微张嘴
            expressions['eyeblink_left'] = min(1.0, confidence * 0.8)
            expressions['eyeblink_right'] = min(1.0, confidence * 0.8)
            expressions['mouth_open'] = min(1.0, confidence * 0.3)
        elif emotion_name == 'Disgust':
            # 厌恶 -> 张嘴
            expressions['mouth_open'] = min(1.0, confidence * 0.6)
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
        """处理单帧图像，检测面部并识别情感 - FER2013优化版"""
        expressions = self._get_default_expressions()
        
        try:
            # 转换为灰度图进行面部检测
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 优化的面部检测参数 - 与其他模型保持一致
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1,        # 更精细的尺度步长
                minNeighbors=5,         # 增加最小邻居数，减少误检
                minSize=(60, 60),       # 增大最小面部尺寸，过滤小物体
                maxSize=(400, 400),     # 适当限制最大尺寸
                flags=cv2.CASCADE_SCALE_IMAGE  # 使用更稳定的检测方式
            )
            
            annotated_frame = frame.copy()
            
            if len(faces) > 0:
                # 选择最大的面部（通常是最接近摄像头的）
                largest_face = max(faces, key=lambda face: face[2] * face[3])
                (x, y, w, h) = largest_face
                
                # 验证面部区域的有效性
                if not self._is_valid_face_region(gray, x, y, w, h):
                    return annotated_frame, expressions
                
                # 扩展面部区域以包含更多特征（但不超出图像边界）
                margin = int(min(w, h) * 0.12)  # FER2013使用中等边距12%
                x_expanded = max(0, x - margin)
                y_expanded = max(0, y - margin)
                w_expanded = min(frame.shape[1] - x_expanded, w + 2 * margin)
                h_expanded = min(frame.shape[0] - y_expanded, h + 2 * margin)
                
                face_roi = frame[y_expanded:y_expanded+h_expanded, x_expanded:x_expanded+w_expanded]
                
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
                
                # 绘制更明显的面部框（红色边框表示FER2013）
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
                
                # 绘制扩展框（用于情感分析）
                cv2.rectangle(annotated_frame, (x_expanded, y_expanded), 
                            (x_expanded+w_expanded, y_expanded+h_expanded), (255, 0, 255), 1)
                
                # 显示情感信息
                text = f"FER2013: {emotion_name} ({confidence:.2f})"
                cv2.putText(annotated_frame, text, (x, y-15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # 显示置信度较高的情感参数
                y_offset = y + h + 25
                sorted_emotions = sorted(expressions.items(), key=lambda item: item[1], reverse=True)
                
                for expr_name, value in sorted_emotions[:3]:  # 只显示前3个最强的情感
                    if value > 0.12:  # FER2013使用中等阈值
                        display_name = {
                            'angry': 'Angry',
                            'disgust': 'Disgust', 
                            'fear': 'Fear',
                            'happy': 'Happy',
                            'sad': 'Sad',
                            'surprise': 'Surprise',
                            'neutral': 'Neutral'
                        }.get(expr_name, expr_name)
                        
                        # 使用颜色编码显示不同情感
                        color = self._get_emotion_color(expr_name)
                        text = f"{display_name}: {value:.2f}"
                        cv2.putText(annotated_frame, text, (x, y_offset), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                        y_offset += 20
                
                # 在右上角显示面部质量信息和模型特有信息
                quality_score = self._calculate_face_quality(face_roi)
                quality_text = f"Quality: {quality_score:.2f} (FER2013)"
                cv2.putText(annotated_frame, quality_text, (frame.shape[1] - 200, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                # 显示FER2013特色信息
                model_info = f"Classic CNN: {len(faces)} faces"
                cv2.putText(annotated_frame, model_info, (frame.shape[1] - 200, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
            
            return annotated_frame, expressions
            
        except Exception as e:
            self.logger.error(f"FER2013帧处理失败: {e}")
            return frame, expressions
    
    def _is_valid_face_region(self, gray_frame, x, y, w, h):
        """验证检测到的区域是否为有效的面部 - FER2013版本"""
        try:
            # 检查区域大小合理性
            if w < 60 or h < 60 or w > 400 or h > 400:
                return False
            
            # 检查宽高比（人脸通常接近1:1.2）
            aspect_ratio = w / h
            if aspect_ratio < 0.7 or aspect_ratio > 1.5:
                return False
            
            # 检查区域是否在图像边界内
            if x < 0 or y < 0 or x + w > gray_frame.shape[1] or y + h > gray_frame.shape[0]:
                return False
            
            # 检查区域内的纹理复杂度（面部应该有一定的纹理变化）
            roi = gray_frame[y:y+h, x:x+w]
            texture_variance = np.var(roi)
            if texture_variance < 45:  # FER2013使用中等严格的阈值
                return False
            
            return True
            
        except Exception:
            return False
    
    def _calculate_face_quality(self, face_roi):
        """计算面部图像质量分数 - FER2013版本"""
        try:
            if face_roi is None or face_roi.size == 0:
                return 0.0
            
            # 转换为灰度图
            if len(face_roi.shape) == 3:
                gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            else:
                gray_face = face_roi
            
            # 计算清晰度（使用拉普拉斯算子）
            laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
            sharpness_score = min(1.0, laplacian_var / 450.0)  # FER2013中等清晰度要求
            
            # 计算对比度
            contrast_score = min(1.0, gray_face.std() / 55.0)  # 中等对比度要求
            
            # 计算亮度适宜性
            mean_brightness = gray_face.mean()
            brightness_score = 1.0 - abs(mean_brightness - 128) / 128.0  # 128为理想亮度
            
            # 综合质量分数 - FER2013权重分配（更注重基础指标）
            quality_score = (sharpness_score * 0.4 + contrast_score * 0.35 + brightness_score * 0.25)
            
            return quality_score
            
        except Exception:
            return 0.0
    
    def _get_emotion_color(self, emotion_name):
        """获取情感对应的颜色 - FER2013经典配色"""
        emotion_colors = {
            'angry': (0, 0, 255),      # 红色
            'disgust': (0, 150, 255),  # 橙色
            'fear': (150, 0, 150),     # 紫色
            'happy': (0, 255, 0),      # 绿色
            'sad': (255, 0, 0),        # 蓝色
            'surprise': (255, 255, 0), # 青色
            'neutral': (150, 150, 150) # 中灰色
        }
        return emotion_colors.get(emotion_name, (255, 255, 255))
    
    def release(self):
        """释放资源"""
        try:
            if self.model is not None:
                del self.model
                self.model = None
                
            if self.device.type == 'cuda':
                torch.cuda.empty_cache()
                
            self.logger.info("FER2013资源已释放")
            
        except Exception as e:
            self.logger.error(f"释放FER2013资源时出错: {e}")