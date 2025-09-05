#!/usr/bin/env python3
"""
简化版面部检测器
使用OpenCV的Haar级联分类器进行面部检测，避免MediaPipe的复杂性
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional
import logging
import os


class SimpleFaceDetector:
    """简化版面部检测器"""
    
    def __init__(self):
        """初始化检测器"""
        self.logger = logging.getLogger(__name__)
        
        # 加载OpenCV预训练的Haar级联分类器
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        self.smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')
        
        # 检查分类器是否加载成功
        if self.face_cascade.empty() or self.eye_cascade.empty() or self.smile_cascade.empty():
            self.logger.error("无法加载Haar级联分类器")
            raise RuntimeError("Haar级联分类器加载失败")
        
        self.logger.info("简化版面部检测器初始化完成")
        
        # 用于计算眨眼的前一帧眼睛数量
        self.previous_eye_count = 2
        self.blink_counter = 0
        self.frame_counter = 0
    
    def detect_faces_and_expressions(self, frame: np.ndarray) -> Dict[str, float]:
        """
        检测面部和表情
        
        Args:
            frame: 输入的BGR图像
            
        Returns:
            包含表情数据的字典
        """
        expressions = {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
        }
        
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 检测面部
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(100, 100))
            
            if len(faces) == 0:
                return expressions
            
            # 取第一个检测到的面部
            (x, y, w, h) = faces[0]
            face_roi_gray = gray[y:y+h, x:x+w]
            face_roi_color = frame[y:y+h, x:x+w]
            
            # 检测眼睛
            eyes = self.eye_cascade.detectMultiScale(face_roi_gray, 1.1, 10, minSize=(20, 20))
            
            # 眨眼检测逻辑
            current_eye_count = len(eyes)
            self.frame_counter += 1
            
            # 简单的眨眼检测：如果眼睛数量从2减少到0或1，认为是眨眼
            if self.previous_eye_count >= 2 and current_eye_count < 2:
                self.blink_counter = 10  # 眨眼持续10帧
            
            if self.blink_counter > 0:
                blink_value = min(1.0, self.blink_counter / 10.0)
                expressions['eyeblink_left'] = blink_value
                expressions['eyeblink_right'] = blink_value
                self.blink_counter -= 1
            
            self.previous_eye_count = current_eye_count
            
            # 微笑检测
            smiles = self.smile_cascade.detectMultiScale(face_roi_gray, 1.8, 20, minSize=(25, 25))
            if len(smiles) > 0:
                expressions['smile'] = min(1.0, len(smiles) * 0.3)
            
            # 简单的嘴巴张开检测（基于面部下半部分的亮度变化）
            mouth_region = face_roi_gray[int(h*0.6):h, int(w*0.25):int(w*0.75)]
            if mouth_region.size > 0:
                mouth_brightness = np.mean(mouth_region)
                face_brightness = np.mean(face_roi_gray)
                
                # 如果嘴部区域比面部平均亮度暗很多，可能是张嘴
                if mouth_brightness < face_brightness * 0.85:
                    expressions['mouth_open'] = min(1.0, (face_brightness - mouth_brightness) / face_brightness * 3)
        
        except Exception as e:
            self.logger.error(f"面部检测时出错: {e}")
        
        return expressions
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        处理单帧图像
        
        Args:
            frame: 输入的BGR图像
            
        Returns:
            (带标注的图像, 表情数据字典)
        """
        expressions = self.detect_faces_and_expressions(frame)
        annotated_frame = self.draw_annotations(frame.copy(), expressions)
        return annotated_frame, expressions
    
    def draw_annotations(self, frame: np.ndarray, expressions: Dict[str, float]) -> np.ndarray:
        """在图像上绘制标注"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(100, 100))
            
            # 绘制面部框
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                
                # 绘制表情数据
                y_offset = y - 10
                for expr_name, value in expressions.items():
                    display_name = {
                        'eyeblink_left': '眨眼',
                        'eyeblink_right': '眨眼',
                        'mouth_open': '张嘴',
                        'smile': '微笑'
                    }.get(expr_name, expr_name)
                    
                    if expr_name == 'eyeblink_right':  # 跳过右眼，只显示一次眨眼
                        continue
                        
                    text = f"{display_name}: {value:.2f}"
                    cv2.putText(frame, text, (x, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    y_offset -= 20
        
        except Exception as e:
            self.logger.error(f"绘制标注时出错: {e}")
        
        return frame
    
    def release(self):
        """释放资源"""
        self.logger.info("简化版面部检测器资源已释放")


class SimpleFaceCamera:
    """简化版面部摄像头"""
    
    def __init__(self, camera_id: int = 0):
        """初始化摄像头"""
        self.camera_id = camera_id
        self.cap = None
        self.detector = SimpleFaceDetector()
        self.logger = logging.getLogger(__name__)
    
    def start_camera(self) -> bool:
        """启动摄像头"""
        try:
            # 使用DirectShow后端，最稳定
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
            
            self.logger.info(f"简化版摄像头 {self.camera_id} 启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动摄像头失败: {e}")
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
            self.logger.info(f"简化版摄像头 {self.camera_id} 资源已释放")
        except Exception as e:
            self.logger.error(f"释放摄像头资源时出错: {e}")