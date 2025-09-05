#!/usr/bin/env python3
"""
GPU加速情感检测器
支持ResEmoteNet和FER2013模型，使用GPU加速
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional
import logging
import os
import urllib.request
from pathlib import Path


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


class GPUEmotionDetector:
    """GPU加速情感检测器"""
    
    def __init__(self, model_type='ResEmoteNet', device='auto'):
        """
        初始化GPU情感检测器
        
        Args:
            model_type: 模型类型 ('ResEmoteNet' 或 'FER2013')
            device: 计算设备 ('cuda', 'cpu', 或 'auto')
        """
        self.logger = logging.getLogger(__name__)
        self.model_type = model_type
        
        # 设置设备
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.logger.info(f"使用设备: {self.device}")
        
        # 情感标签
        self.emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
        
        # 面部检测器
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # 加载模型
        self.model = None
        self.load_model()
        
        # 表情历史用于平滑
        self.emotion_history = []
        self.history_size = 5
    
    def load_model(self):
        """加载情感识别模型"""
        try:
            if self.model_type == 'ResEmoteNet':
                self.model = ResEmoteNet(num_classes=7)
                model_path = self.download_resemotenet_weights()
            else:  # FER2013
                self.model = self.create_fer2013_model()
                model_path = self.download_fer2013_weights()
            
            # 加载权重
            if os.path.exists(model_path):
                checkpoint = torch.load(model_path, map_location=self.device)
                if 'state_dict' in checkpoint:
                    self.model.load_state_dict(checkpoint['state_dict'])
                else:
                    self.model.load_state_dict(checkpoint)
                self.logger.info(f"成功加载{self.model_type}模型权重")
            else:
                self.logger.warning(f"未找到模型权重文件，使用随机初始化的权重")
            
            self.model.to(self.device)
            self.model.eval()
            
        except Exception as e:
            self.logger.error(f"加载{self.model_type}模型失败: {e}")
            raise
    
    def create_fer2013_model(self):
        """创建FER2013模型"""
        class FER2013Model(nn.Module):
            def __init__(self):
                super(FER2013Model, self).__init__()
                self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
                self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
                self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
                self.pool = nn.MaxPool2d(2, 2)
                self.dropout1 = nn.Dropout(0.25)
                self.dropout2 = nn.Dropout(0.5)
                self.fc1 = nn.Linear(128 * 6 * 6, 512)
                self.fc2 = nn.Linear(512, 7)
            
            def forward(self, x):
                x = self.pool(F.relu(self.conv1(x)))
                x = self.pool(F.relu(self.conv2(x)))
                x = self.pool(F.relu(self.conv3(x)))
                x = self.dropout1(x)
                x = x.view(-1, 128 * 6 * 6)
                x = F.relu(self.fc1(x))
                x = self.dropout2(x)
                x = self.fc2(x)
                return x
        
        return FER2013Model()
    
    def download_resemotenet_weights(self):
        """下载ResEmoteNet权重（这里使用占位符）"""
        weights_dir = Path("models/resemotenet")
        weights_dir.mkdir(parents=True, exist_ok=True)
        model_path = weights_dir / "resemotenet_weights.pth"
        
        # 这里应该是实际的下载链接，现在创建一个占位符文件
        if not model_path.exists():
            self.logger.info("创建ResEmoteNet占位符权重文件")
            torch.save(self.model.state_dict(), model_path)
        
        return str(model_path)
    
    def download_fer2013_weights(self):
        """下载FER2013权重（这里使用占位符）"""
        weights_dir = Path("models/fer2013")
        weights_dir.mkdir(parents=True, exist_ok=True)
        model_path = weights_dir / "fer2013_weights.pth"
        
        # 这里应该是实际的下载链接，现在创建一个占位符文件
        if not model_path.exists():
            self.logger.info("创建FER2013占位符权重文件")
            torch.save(self.model.state_dict(), model_path)
        
        return str(model_path)
    
    def preprocess_face(self, face_img):
        """预处理面部图像"""
        # 转换为灰度图
        if len(face_img.shape) == 3:
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_img
        
        # 调整大小到48x48
        face_resized = cv2.resize(gray, (48, 48))
        
        # 归一化
        face_normalized = face_resized.astype(np.float32) / 255.0
        
        # 转换为张量
        face_tensor = torch.from_numpy(face_normalized).unsqueeze(0).unsqueeze(0)
        return face_tensor.to(self.device)
    
    def detect_emotion(self, face_img):
        """检测单个面部的情感"""
        try:
            # 预处理
            input_tensor = self.preprocess_face(face_img)
            
            # 推理
            with torch.no_grad():
                outputs = self.model(input_tensor)
                probabilities = F.softmax(outputs, dim=1)
                predicted_emotion = torch.argmax(probabilities, dim=1).item()
            
            # 转换为表情数据
            emotions_dict = {
                'eyeblink_left': 0.0,
                'eyeblink_right': 0.0,
                'mouth_open': 0.0,
                'smile': 0.0
            }
            
            # 根据预测的情感调整表情参数
            emotion_name = self.emotion_labels[predicted_emotion]
            confidence = probabilities[0][predicted_emotion].item()
            
            if emotion_name == 'Happy':
                emotions_dict['smile'] = min(1.0, confidence * 1.5)
            elif emotion_name == 'Surprise':
                emotions_dict['mouth_open'] = min(1.0, confidence * 1.2)
                emotions_dict['eyeblink_left'] = min(1.0, confidence * 0.8)
                emotions_dict['eyeblink_right'] = min(1.0, confidence * 0.8)
            
            # 添加到历史记录用于平滑
            self.emotion_history.append(emotions_dict)
            if len(self.emotion_history) > self.history_size:
                self.emotion_history.pop(0)
            
            # 计算平滑后的结果
            smoothed_emotions = {}
            for key in emotions_dict.keys():
                values = [hist[key] for hist in self.emotion_history]
                smoothed_emotions[key] = np.mean(values)
            
            return smoothed_emotions, emotion_name, confidence
            
        except Exception as e:
            self.logger.error(f"情感检测失败: {e}")
            return {
                'eyeblink_left': 0.0,
                'eyeblink_right': 0.0,
                'mouth_open': 0.0,
                'smile': 0.0
            }, 'Neutral', 0.0
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """处理单帧图像"""
        expressions = {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
        }
        
        try:
            # 转换为灰度图进行面部检测
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(100, 100))
            
            annotated_frame = frame.copy()
            
            if len(faces) > 0:
                # 处理第一个检测到的面部
                (x, y, w, h) = faces[0]
                face_img = frame[y:y+h, x:x+w]
                
                # 检测情感
                expressions, emotion_name, confidence = self.detect_emotion(face_img)
                
                # 绘制面部框和情感信息
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # 显示情感和置信度
                text = f"{emotion_name}: {confidence:.2f}"
                cv2.putText(annotated_frame, text, (x, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # 显示表情参数
                y_offset = y + h + 20
                for expr_name, value in expressions.items():
                    if value > 0.01:  # 只显示有值的表情
                        display_name = {
                            'eyeblink_left': '眨眼',
                            'eyeblink_right': '眨眼',
                            'mouth_open': '张嘴',
                            'smile': '微笑'
                        }.get(expr_name, expr_name)
                        
                        if expr_name == 'eyeblink_right':  # 跳过右眼
                            continue
                            
                        text = f"{display_name}: {value:.2f}"
                        cv2.putText(annotated_frame, text, (x, y_offset), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                        y_offset += 20
            
            return annotated_frame, expressions
            
        except Exception as e:
            self.logger.error(f"处理帧时出错: {e}")
            return frame, expressions
    
    def release(self):
        """释放资源"""
        try:
            if self.model is not None:
                del self.model
                if self.device.type == 'cuda':
                    torch.cuda.empty_cache()
            self.logger.info("GPU情感检测器资源已释放")
        except Exception as e:
            self.logger.error(f"释放资源时出错: {e}")


class GPUFaceCamera:
    """GPU加速面部摄像头"""
    
    def __init__(self, camera_id: int = 0, model_type='ResEmoteNet', device='auto'):
        """初始化GPU摄像头"""
        self.camera_id = camera_id
        self.cap = None
        self.detector = GPUEmotionDetector(model_type=model_type, device=device)
        self.logger = logging.getLogger(__name__)
    
    def start_camera(self) -> bool:
        """启动摄像头"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                self.logger.error(f"无法打开摄像头 {self.camera_id}")
                return False
            
            # 测试读取
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.logger.error(f"摄像头 {self.camera_id} 无法读取画面")
                self.cap.release()
                return False
            
            # 设置分辨率
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.logger.info(f"GPU摄像头 {self.camera_id} 启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动GPU摄像头失败: {e}")
            if self.cap:
                self.cap.release()
            return False
    
    def get_frame_with_expressions(self) -> Tuple[Optional[np.ndarray], Dict[str, float]]:
        """获取带表情数据的帧"""
        if not self.cap or not self.cap.isOpened():
            return None, {'eyeblink_left': 0.0, 'eyeblink_right': 0.0, 'mouth_open': 0.0, 'smile': 0.0}
        
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return None, {'eyeblink_left': 0.0, 'eyeblink_right': 0.0, 'mouth_open': 0.0, 'smile': 0.0}
            
            annotated_frame, expressions = self.detector.process_frame(frame)
            return annotated_frame, expressions
            
        except Exception as e:
            self.logger.error(f"获取帧时出错: {e}")
            return None, {'eyeblink_left': 0.0, 'eyeblink_right': 0.0, 'mouth_open': 0.0, 'smile': 0.0}
    
    def release(self):
        """释放资源"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
            self.detector.release()
            self.logger.info(f"GPU摄像头 {self.camera_id} 资源已释放")
        except Exception as e:
            self.logger.error(f"释放GPU摄像头资源时出错: {e}")