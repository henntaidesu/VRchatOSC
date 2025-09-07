# -*- coding: utf-8 -*-
import cv2
import threading
import tkinter as tk
from tkinter import ttk


class CameraControl:
    def __init__(self, main_app):
        self.main_app = main_app
        
    def detect_available_cameras(self):
        """检测可用的摄像头"""
        available_cameras = []
        detected_signatures = set()  # 用于避免重复检测同一摄像头
        
        # 检查多个摄像头ID
        for i in range(5):  # 减少到检查ID 0-4，提高检测速度
            try:
                # 主要使用DSHOW后端，这在Windows上最可靠
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                
                if cap.isOpened():
                    # 尝试读取一帧来验证摄像头是否可用
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        # 获取摄像头详细信息
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        # 创建摄像头特征签名（基于分辨率）
                        signature = f"{width}x{height}"
                        
                        # 检查是否已经检测过相同分辨率的摄像头
                        if signature not in detected_signatures:
                            detected_signatures.add(signature)
                            
                            # 简化显示信息
                            camera_info = f"摄像头 {i} ({width}x{height})"
                            available_cameras.append((i, camera_info))
                            self.main_app.log(f"检测到摄像头: {camera_info}")
                        else:
                            self.main_app.log(f"跳过重复摄像头 ID {i} (相同分辨率: {signature})")
                
                cap.release()
                    
            except Exception as e:
                # 忽略检测失败的摄像头
                continue
        
        return available_cameras

    def refresh_camera_list(self):
        """刷新摄像头列表"""
        try:
            self.main_app.log("正在检测可用摄像头...")
            
            # 显示检测状态
            self.main_app.camera_combo['values'] = ['正在检测...']
            self.main_app.camera_combo.set('正在检测...')
            self.main_app.root.update()
            
            # 在后台线程中检测摄像头
            def detect_cameras():
                try:
                    available_cameras = self.detect_available_cameras()
                    
                    # 在主线程中更新UI
                    self.main_app.root.after(0, lambda: self.update_camera_list(available_cameras))
                    
                except Exception as e:
                    self.main_app.root.after(0, lambda: self.main_app.log(f"检测摄像头失败: {e}"))
            
            # 启动检测线程
            thread = threading.Thread(target=detect_cameras, daemon=True)
            thread.start()
            
        except Exception as e:
            self.main_app.log(f"刷新摄像头列表失败: {e}")
            self.main_app.camera_combo['values'] = ['检测失败']
            self.main_app.camera_combo.set('检测失败')

    def update_camera_list(self, available_cameras):
        """更新摄像头列表（在主线程中调用）"""
        try:
            if available_cameras:
                # 创建显示列表
                camera_values = [info for _, info in available_cameras]
                self.main_app.camera_combo['values'] = camera_values
                
                # 保存ID映射
                self.main_app.camera_id_mapping = {info: cam_id for cam_id, info in available_cameras}
                
                # 默认选择第一个摄像头
                self.main_app.camera_combo.set(camera_values[0])
                self.main_app.log(f"检测到 {len(available_cameras)} 个可用摄像头")
                
            else:
                no_cameras_text = self.main_app.get_text("no_cameras_available")
                self.main_app.camera_combo['values'] = [no_cameras_text]
                self.main_app.camera_combo.set(no_cameras_text)
                self.main_app.camera_id_mapping = {}
                self.main_app.log(self.main_app.get_text("no_cameras_available"))
                
        except Exception as e:
            self.main_app.log(f"更新摄像头列表失败: {e}")
            self.main_app.camera_combo['values'] = ['更新失败']
            self.main_app.camera_combo.set('更新失败')

    def on_model_changed(self, event=None):
        """模型选择变更处理"""
        self.main_app.emotion_model_type = self.main_app.model_var.get()
        self.main_app.log(f"情感识别模型已切换为: {self.main_app.emotion_model_type}")
        
        # 释放现有的GPU检测器
        if hasattr(self.main_app, 'gpu_detector') and self.main_app.gpu_detector is not None:
            try:
                self.main_app.gpu_detector.release()
                self.main_app.gpu_detector = None
                self.main_app.log("已释放旧的GPU检测器")
            except Exception as e:
                self.main_app.log(f"释放旧GPU检测器时出错: {e}")
        
        # 如果切换到GPU模型，强制重新初始化检测器
        if self.main_app.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
            try:
                # 总是创建新的检测器以确保模型切换生效
                from src.face.gpu_emotion_detector import GPUEmotionDetector
                self.main_app.gpu_detector = GPUEmotionDetector(model_type=self.main_app.emotion_model_type, device='auto')
                self.main_app.log(f"成功初始化GPU情感检测器: {self.main_app.emotion_model_type}")
            except Exception as e:
                import traceback
                self.main_app.log(f"GPU检测器初始化失败 ({self.main_app.emotion_model_type}): {e}")
                self.main_app.log(f"详细错误: {traceback.format_exc()}")
                self.main_app.gpu_detector = None
        
        # 如果面部识别正在运行，需要重启以应用新模型
        if self.main_app.face_detection_running:
            self.main_app.log("检测到模型变更，正在重启面部识别以应用新模型...")
            self.main_app.stop_face_detection()
            # 延迟一点再启动
            self.main_app.root.after(1000, self.main_app.start_face_detection)