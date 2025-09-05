#!/usr/bin/env python3
"""
GPU加速情感检测器 - 统一接口
支持ResEmoteNet、FER2013、EmoNeXt等多种模型
"""

import cv2
import numpy as np
import torch
from typing import Dict, Tuple, Optional
import logging


class GPUEmotionDetector:
    """GPU加速情感检测器 - 统一接口"""
    
    def __init__(self, model_type='ResEmoteNet', device='auto'):
        """
        初始化GPU情感检测器
        
        Args:
            model_type: 模型类型 ('ResEmoteNet', 'FER2013', 'EmoNeXt')
            device: 计算设备 ('cuda', 'cpu', 或 'auto')
        """
        self.logger = logging.getLogger(__name__)
        self.model_type = model_type
        
        # 设置设备
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.logger.info(f"GPU情感检测器使用设备: {self.device}")
        self.logger.info(f"加载模型类型: {self.model_type}")
        
        # 初始化具体的模型检测器
        self.detector = None
        self._initialize_detector()
    
    def _initialize_detector(self):
        """初始化具体的模型检测器"""
        try:
            if self.model_type == 'ResEmoteNet':
                from .models.resemotenet import ResEmoteNetDetector
                self.detector = ResEmoteNetDetector(device=self.device)
                
            elif self.model_type == 'FER2013':
                from .models.fer2013 import FER2013Detector
                self.detector = FER2013Detector(device=self.device)
                
            elif self.model_type == 'EmoNeXt':
                from .models.emonext import EmoNeXtDetector
                self.detector = EmoNeXtDetector(device=self.device)
                
            else:
                raise ValueError(f"不支持的模型类型: {self.model_type}")
            
            self.logger.info(f"成功初始化{self.model_type}检测器")
            
        except Exception as e:
            self.logger.error(f"初始化{self.model_type}检测器失败: {e}")
            raise
    
    def detect_emotion(self, face_img):
        """检测单个面部的情感"""
        if self.detector is None:
            self.logger.error("检测器未初始化")
            return self._get_default_result()
        
        try:
            return self.detector.detect_emotion_single_face(face_img)
        except Exception as e:
            self.logger.error(f"情感检测失败: {e}")
            return self._get_default_result()
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """处理单帧图像"""
        if self.detector is None:
            self.logger.error("检测器未初始化")
            return frame, self._get_default_expressions()
        
        try:
            return self.detector.process_frame(frame)
        except Exception as e:
            self.logger.error(f"帧处理失败: {e}")
            return frame, self._get_default_expressions()
    
    def _get_default_expressions(self):
        """获取默认表情参数"""
        return {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
        }
    
    def _get_default_result(self):
        """获取默认检测结果"""
        return self._get_default_expressions(), 'Neutral', 0.0
    
    def switch_model(self, new_model_type):
        """切换模型类型"""
        if new_model_type == self.model_type:
            self.logger.info(f"模型类型已经是 {new_model_type}，无需切换")
            return
        
        try:
            # 释放当前模型
            if self.detector is not None:
                self.detector.release()
                self.detector = None
            
            # 切换到新模型
            self.model_type = new_model_type
            self.logger.info(f"正在切换到模型: {self.model_type}")
            
            # 初始化新模型
            self._initialize_detector()
            
            self.logger.info(f"成功切换到 {self.model_type} 模型")
            
        except Exception as e:
            self.logger.error(f"模型切换失败: {e}")
            raise
    
    def get_model_info(self):
        """获取当前模型信息"""
        return {
            'model_type': self.model_type,
            'device': str(self.device),
            'is_initialized': self.detector is not None
        }
    
    def release(self):
        """释放资源"""
        try:
            if self.detector is not None:
                self.detector.release()
                self.detector = None
            
            if self.device.type == 'cuda':
                torch.cuda.empty_cache()
            
            self.logger.info(f"GPU情感检测器 ({self.model_type}) 资源已释放")
            
        except Exception as e:
            self.logger.error(f"释放GPU情感检测器资源时出错: {e}")


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