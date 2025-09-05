#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型摄像头查看器
支持放大缩小和人脸自动聚焦功能
"""

import cv2
import numpy as np
import mediapipe as mp
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import Optional, Tuple, List
import logging


class EnhancedCameraViewer:
    """增强型摄像头查看器"""
    
    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id
        self.cap = None
        
        # 缩放参数
        self.zoom_factor = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 5.0
        self.zoom_step = 0.1
        
        # 人脸检测
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5)
        
        # 人脸聚焦参数
        self.auto_focus_enabled = False
        self.face_center = None
        self.frame_center = None
        self.smooth_factor = 0.1  # 平滑移动因子
        
        # 图像校正参数
        self.image_correction_enabled = False
        self.face_angle = 0.0  # 人脸倾斜角度
        self.smooth_angle_factor = 0.2  # 角度平滑因子
        
        # 显示参数
        self.display_width = 800
        self.display_height = 600
        
        # 线程控制
        self.running = False
        self.camera_thread = None
        
        self.logger = logging.getLogger(__name__)
        
        # 创建GUI
        self.setup_gui()
    
    def setup_gui(self):
        """设置GUI界面"""
        self.root = tk.Tk()
        self.root.title("增强型摄像头查看器")
        self.root.geometry("300x400")
        
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 摄像头控制
        camera_frame = ttk.LabelFrame(main_frame, text="摄像头控制", padding="5")
        camera_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(camera_frame, text="启动摄像头", 
                  command=self.start_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(camera_frame, text="停止摄像头", 
                  command=self.stop_camera).pack(side=tk.LEFT, padx=5)
        
        # 缩放控制
        zoom_frame = ttk.LabelFrame(main_frame, text="缩放控制", padding="5")
        zoom_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(zoom_frame, text="缩放倍数:").pack()
        self.zoom_var = tk.StringVar(value=f"{self.zoom_factor:.1f}x")
        self.zoom_label = ttk.Label(zoom_frame, textvariable=self.zoom_var, 
                                   font=('Arial', 12, 'bold'))
        self.zoom_label.pack(pady=5)
        
        zoom_buttons = ttk.Frame(zoom_frame)
        zoom_buttons.pack()
        
        ttk.Button(zoom_buttons, text="放大 (+)", 
                  command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_buttons, text="缩小 (-)", 
                  command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_buttons, text="重置", 
                  command=self.reset_zoom).pack(side=tk.LEFT, padx=2)
        
        # 缩放滑块
        self.zoom_scale = tk.Scale(zoom_frame, from_=self.min_zoom, to=self.max_zoom,
                                  resolution=0.1, orient=tk.HORIZONTAL,
                                  command=self.on_zoom_scale_change)
        self.zoom_scale.set(self.zoom_factor)
        self.zoom_scale.pack(fill=tk.X, pady=5)
        
        # 人脸聚焦控制
        focus_frame = ttk.LabelFrame(main_frame, text="人脸聚焦", padding="5")
        focus_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.auto_focus_var = tk.BooleanVar()
        ttk.Checkbutton(focus_frame, text="自动聚焦人脸", 
                       variable=self.auto_focus_var,
                       command=self.toggle_auto_focus).pack()
        
        ttk.Button(focus_frame, text="手动聚焦当前人脸", 
                  command=self.manual_focus_face).pack(pady=5)
        ttk.Button(focus_frame, text="重置视图中心", 
                  command=self.reset_view_center).pack()
        
        # 图像校正控制
        correction_frame = ttk.LabelFrame(main_frame, text="图像校正", padding="5")
        correction_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.correction_var = tk.BooleanVar()
        ttk.Checkbutton(correction_frame, text="自动校正人脸角度", 
                       variable=self.correction_var,
                       command=self.toggle_image_correction).pack()
        
        # 角度显示
        self.angle_var = tk.StringVar(value="角度: 0.0°")
        ttk.Label(correction_frame, textvariable=self.angle_var).pack(pady=2)
        
        correction_buttons = ttk.Frame(correction_frame)
        correction_buttons.pack()
        
        ttk.Button(correction_buttons, text="顺时针", 
                  command=self.rotate_clockwise).pack(side=tk.LEFT, padx=2)
        ttk.Button(correction_buttons, text="逆时针", 
                  command=self.rotate_counterclockwise).pack(side=tk.LEFT, padx=2)
        ttk.Button(correction_buttons, text="重置角度", 
                  command=self.reset_rotation).pack(side=tk.LEFT, padx=2)
        
        # 显示设置
        display_frame = ttk.LabelFrame(main_frame, text="显示设置", padding="5")
        display_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(display_frame, text="显示尺寸:").pack()
        size_frame = ttk.Frame(display_frame)
        size_frame.pack()
        
        ttk.Button(size_frame, text="800x600", 
                  command=lambda: self.set_display_size(800, 600)).pack(side=tk.LEFT, padx=2)
        ttk.Button(size_frame, text="640x480", 
                  command=lambda: self.set_display_size(640, 480)).pack(side=tk.LEFT, padx=2)
        ttk.Button(size_frame, text="1024x768", 
                  command=lambda: self.set_display_size(1024, 768)).pack(side=tk.LEFT, padx=2)
        
        # 状态显示
        status_frame = ttk.LabelFrame(main_frame, text="状态信息", padding="5")
        status_frame.pack(fill=tk.X)
        
        self.status_var = tk.StringVar(value="摄像头未启动")
        ttk.Label(status_frame, textvariable=self.status_var).pack()
        
        # 绑定键盘事件
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.focus_set()
        
        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def start_camera(self):
        """启动摄像头"""
        if self.running:
            self.logger.warning("摄像头已在运行中")
            return
        
        try:
            # 尝试不同的后端
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
            
            for backend in backends:
                self.cap = cv2.VideoCapture(self.camera_id, backend)
                if self.cap.isOpened():
                    # 测试读取帧
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        self.frame_center = (frame.shape[1] // 2, frame.shape[0] // 2)
                        break
                    else:
                        self.cap.release()
                        self.cap = None
                else:
                    if self.cap:
                        self.cap.release()
                        self.cap = None
            
            if not self.cap or not self.cap.isOpened():
                messagebox.showerror("错误", "无法打开摄像头")
                return
            
            # 设置摄像头参数
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            
            # 启动摄像头线程
            self.running = True
            self.camera_thread = threading.Thread(target=self.camera_loop, daemon=True)
            self.camera_thread.start()
            
            self.status_var.set("摄像头运行中")
            self.logger.info("摄像头启动成功")
            
        except Exception as e:
            self.logger.error(f"启动摄像头失败: {e}")
            messagebox.showerror("错误", f"启动摄像头失败: {e}")
    
    def stop_camera(self):
        """停止摄像头"""
        self.running = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        cv2.destroyAllWindows()
        
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=1)
        
        self.status_var.set("摄像头已停止")
        self.logger.info("摄像头已停止")
    
    def camera_loop(self):
        """摄像头主循环"""
        window_name = "Enhanced Camera Viewer"
        
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue
            
            try:
                # 检测人脸
                faces = self.detect_faces(frame)
                
                # 应用人脸聚焦
                if self.auto_focus_enabled and faces:
                    self.apply_face_focus(faces, frame.shape)
                
                # 应用图像校正
                if self.image_correction_enabled and faces:
                    frame = self.apply_image_correction(frame, faces)
                
                # 应用缩放和平移
                processed_frame = self.apply_zoom_and_pan(frame)
                
                # 绘制人脸框
                processed_frame = self.draw_face_boxes(processed_frame, faces)
                
                # 添加UI信息
                processed_frame = self.add_ui_overlay(processed_frame)
                
                # 调整显示尺寸
                display_frame = cv2.resize(processed_frame, 
                                         (self.display_width, self.display_height))
                
                cv2.imshow(window_name, display_frame)
                
                # 处理按键
                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    break
                elif key == ord('+') or key == ord('='):
                    self.zoom_in()
                elif key == ord('-'):
                    self.zoom_out()
                elif key == ord('r'):
                    self.reset_zoom()
                elif key == ord('f'):
                    self.manual_focus_face()
                elif key == ord('a'):
                    self.toggle_auto_focus()
                elif key == ord('c'):
                    self.reset_view_center()
                elif key == ord('t'):  # Toggle correction
                    self.toggle_image_correction()
                elif key == ord('q'):  # Rotate clockwise
                    self.rotate_clockwise()
                elif key == ord('e'):  # Rotate counterclockwise  
                    self.rotate_counterclockwise()
                    
            except Exception as e:
                self.logger.error(f"处理帧时出错: {e}")
                continue
        
        cv2.destroyWindow(window_name)
    
    def detect_faces(self, frame) -> List[dict]:
        """检测人脸"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)
        
        faces = []
        if results.detections:
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                h, w = frame.shape[:2]
                
                face_info = {
                    'bbox': bbox,
                    'center_x': int((bbox.xmin + bbox.width / 2) * w),
                    'center_y': int((bbox.ymin + bbox.height / 2) * h),
                    'width': int(bbox.width * w),
                    'height': int(bbox.height * h),
                    'confidence': detection.score[0]
                }
                faces.append(face_info)
        
        return faces
    
    def calculate_face_angle(self, faces: List[dict], frame: np.ndarray) -> float:
        """计算人脸倾斜角度"""
        if not faces:
            return 0.0
        
        # 使用最大的人脸进行角度计算
        largest_face = max(faces, key=lambda f: f['width'] * f['height'])
        
        # 使用MediaPipe Face Mesh获得更精确的关键点
        try:
            import mediapipe as mp
            mp_face_mesh = mp.solutions.face_mesh
            
            with mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as face_mesh:
                
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb_frame)
                
                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0]
                    h, w = frame.shape[:2]
                    
                    # 关键点：左眼角(33)、右眼角(263)
                    left_eye = landmarks.landmark[33]
                    right_eye = landmarks.landmark[263]
                    
                    # 转换为像素坐标
                    left_eye_pos = (int(left_eye.x * w), int(left_eye.y * h))
                    right_eye_pos = (int(right_eye.x * w), int(right_eye.y * h))
                    
                    # 计算角度
                    delta_x = right_eye_pos[0] - left_eye_pos[0]
                    delta_y = right_eye_pos[1] - left_eye_pos[1]
                    angle = np.degrees(np.arctan2(delta_y, delta_x))
                    
                    return angle
        
        except Exception as e:
            self.logger.warning(f"无法使用Face Mesh计算角度: {e}")
        
        # 备用方法：使用人脸检测框的几何中心
        bbox = largest_face['bbox']
        # 简化的角度估计，这里返回0，实际应用中可以用其他方法
        return 0.0
    
    def apply_image_correction(self, frame: np.ndarray, faces: List[dict]) -> np.ndarray:
        """应用图像校正"""
        if not faces:
            return frame
        
        # 计算人脸角度
        detected_angle = self.calculate_face_angle(faces, frame)
        
        # 平滑角度变化
        if abs(detected_angle) > 1.0:  # 只在角度变化显著时才调整
            target_angle = -detected_angle  # 反向旋转来校正
            if self.face_angle == 0.0:
                self.face_angle = target_angle
            else:
                self.face_angle += (target_angle - self.face_angle) * self.smooth_angle_factor
        
        # 更新角度显示
        self.angle_var.set(f"角度: {self.face_angle:.1f}°")
        
        # 应用旋转
        if abs(self.face_angle) > 0.5:  # 小于0.5度的旋转忽略
            frame = self.rotate_image(frame, self.face_angle)
        
        return frame
    
    def rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """旋转图像"""
        if abs(angle) < 0.1:
            return image
        
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        
        # 获取旋转矩阵
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # 计算新的边界框
        cos_val = np.abs(rotation_matrix[0, 0])
        sin_val = np.abs(rotation_matrix[0, 1])
        new_w = int((h * sin_val) + (w * cos_val))
        new_h = int((h * cos_val) + (w * sin_val))
        
        # 调整旋转矩阵的平移部分
        rotation_matrix[0, 2] += (new_w / 2) - center[0]
        rotation_matrix[1, 2] += (new_h / 2) - center[1]
        
        # 执行旋转
        rotated = cv2.warpAffine(image, rotation_matrix, (new_w, new_h), 
                               borderMode=cv2.BORDER_REFLECT)
        
        # 裁剪回原始尺寸
        y_start = (new_h - h) // 2
        x_start = (new_w - w) // 2
        
        if y_start >= 0 and x_start >= 0:
            rotated = rotated[y_start:y_start+h, x_start:x_start+w]
        else:
            # 如果旋转后尺寸小于原图，居中放置
            result = np.zeros_like(image)
            h_rot, w_rot = rotated.shape[:2]
            y_offset = max(0, (h - h_rot) // 2)
            x_offset = max(0, (w - w_rot) // 2)
            result[y_offset:y_offset+h_rot, x_offset:x_offset+w_rot] = rotated
            rotated = result
        
        return rotated
    
    def apply_face_focus(self, faces: List[dict], frame_shape: Tuple[int, int, int]):
        """应用人脸自动聚焦"""
        if not faces:
            return
        
        # 找到最大的人脸
        largest_face = max(faces, key=lambda f: f['width'] * f['height'])
        
        # 更新面部中心
        new_face_center = (largest_face['center_x'], largest_face['center_y'])
        
        if self.face_center is None:
            self.face_center = new_face_center
        else:
            # 平滑移动
            self.face_center = (
                int(self.face_center[0] + (new_face_center[0] - self.face_center[0]) * self.smooth_factor),
                int(self.face_center[1] + (new_face_center[1] - self.face_center[1]) * self.smooth_factor)
            )
        
        # 根据人脸大小自动调整缩放
        face_area = largest_face['width'] * largest_face['height']
        frame_area = frame_shape[1] * frame_shape[0]
        face_ratio = face_area / frame_area
        
        # 目标人脸占比为15-25%
        target_ratio = 0.2
        if face_ratio < 0.1:
            # 人脸太小，放大
            desired_zoom = min(self.max_zoom, self.zoom_factor * 1.02)
            self.set_zoom(desired_zoom)
        elif face_ratio > 0.3:
            # 人脸太大，缩小
            desired_zoom = max(self.min_zoom, self.zoom_factor * 0.98)
            self.set_zoom(desired_zoom)
    
    def apply_zoom_and_pan(self, frame: np.ndarray) -> np.ndarray:
        """应用缩放和平移"""
        h, w = frame.shape[:2]
        
        # 计算缩放后的尺寸
        new_w = int(w * self.zoom_factor)
        new_h = int(h * self.zoom_factor)
        
        # 缩放图像
        if self.zoom_factor != 1.0:
            frame = cv2.resize(frame, (new_w, new_h))
        
        # 计算裁剪中心
        if self.auto_focus_enabled and self.face_center:
            # 以人脸为中心
            center_x = int(self.face_center[0] * self.zoom_factor)
            center_y = int(self.face_center[1] * self.zoom_factor)
        else:
            # 以原始中心为中心
            center_x = new_w // 2
            center_y = new_h // 2
        
        # 计算裁剪区域
        crop_w = min(w, new_w)
        crop_h = min(h, new_h)
        
        x1 = max(0, center_x - crop_w // 2)
        y1 = max(0, center_y - crop_h // 2)
        x2 = min(new_w, x1 + crop_w)
        y2 = min(new_h, y1 + crop_h)
        
        # 调整起始位置以确保完整裁剪
        if x2 - x1 < crop_w:
            x1 = max(0, x2 - crop_w)
        if y2 - y1 < crop_h:
            y1 = max(0, y2 - crop_h)
        
        # 裁剪图像
        cropped = frame[y1:y2, x1:x2]
        
        # 如果裁剪后尺寸不足，填充黑色
        if cropped.shape[0] < h or cropped.shape[1] < w:
            result = np.zeros((h, w, 3), dtype=np.uint8)
            y_offset = (h - cropped.shape[0]) // 2
            x_offset = (w - cropped.shape[1]) // 2
            result[y_offset:y_offset+cropped.shape[0], 
                   x_offset:x_offset+cropped.shape[1]] = cropped
            return result
        
        return cropped
    
    def draw_face_boxes(self, frame: np.ndarray, faces: List[dict]) -> np.ndarray:
        """绘制人脸框"""
        for face in faces:
            bbox = face['bbox']
            h, w = frame.shape[:2]
            
            x1 = int(bbox.xmin * w)
            y1 = int(bbox.ymin * h)
            x2 = int((bbox.xmin + bbox.width) * w)
            y2 = int((bbox.ymin + bbox.height) * h)
            
            # 绘制人脸框
            color = (0, 255, 0) if self.auto_focus_enabled else (255, 0, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # 绘制置信度
            confidence_text = f"{face['confidence']:.2f}"
            cv2.putText(frame, confidence_text, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return frame
    
    def add_ui_overlay(self, frame: np.ndarray) -> np.ndarray:
        """添加UI覆盖信息"""
        h, w = frame.shape[:2]
        
        # 添加缩放信息
        zoom_text = f"Zoom: {self.zoom_factor:.1f}x"
        cv2.putText(frame, zoom_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 添加人脸聚焦状态
        focus_text = "Auto Focus: ON" if self.auto_focus_enabled else "Auto Focus: OFF"
        cv2.putText(frame, focus_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if self.auto_focus_enabled else (0, 0, 255), 2)
        
        # 添加图像校正状态
        correction_text = "Correction: ON" if self.image_correction_enabled else "Correction: OFF"
        cv2.putText(frame, correction_text, (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if self.image_correction_enabled else (0, 0, 255), 2)
        
        # 添加角度信息
        if self.image_correction_enabled:
            angle_text = f"Angle: {self.face_angle:.1f}°"
            cv2.putText(frame, angle_text, (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # 添加快捷键提示
        shortcuts = [
            "ESC: Exit",
            "+/-: Zoom",
            "R: Reset",
            "F: Focus Face",
            "A: Toggle Auto",
            "C: Reset Center",
            "T: Toggle Correction",
            "Q/E: Rotate"
        ]
        
        for i, shortcut in enumerate(shortcuts):
            cv2.putText(frame, shortcut, (w - 150, 30 + i * 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        return frame
    
    def zoom_in(self):
        """放大"""
        new_zoom = min(self.max_zoom, self.zoom_factor + self.zoom_step)
        self.set_zoom(new_zoom)
    
    def zoom_out(self):
        """缩小"""
        new_zoom = max(self.min_zoom, self.zoom_factor - self.zoom_step)
        self.set_zoom(new_zoom)
    
    def reset_zoom(self):
        """重置缩放"""
        self.set_zoom(1.0)
    
    def set_zoom(self, zoom: float):
        """设置缩放倍数"""
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, zoom))
        self.zoom_var.set(f"{self.zoom_factor:.1f}x")
        self.zoom_scale.set(self.zoom_factor)
    
    def on_zoom_scale_change(self, value):
        """缩放滑块变化事件"""
        self.zoom_factor = float(value)
        self.zoom_var.set(f"{self.zoom_factor:.1f}x")
    
    def toggle_auto_focus(self):
        """切换自动聚焦"""
        self.auto_focus_enabled = self.auto_focus_var.get()
        status = "启用" if self.auto_focus_enabled else "禁用"
        self.logger.info(f"人脸自动聚焦: {status}")
    
    def manual_focus_face(self):
        """手动聚焦人脸"""
        # 这将在下一帧中触发人脸聚焦
        self.face_center = None
        self.logger.info("手动聚焦人脸")
    
    def reset_view_center(self):
        """重置视图中心"""
        self.face_center = None
        if self.frame_center:
            self.face_center = self.frame_center
        self.logger.info("重置视图中心")
    
    def toggle_image_correction(self):
        """切换图像校正"""
        self.image_correction_enabled = self.correction_var.get()
        status = "启用" if self.image_correction_enabled else "禁用"
        if not self.image_correction_enabled:
            self.face_angle = 0.0  # 重置角度
            self.angle_var.set("角度: 0.0°")
        self.logger.info(f"图像校正: {status}")
    
    def rotate_clockwise(self):
        """顺时针旋转"""
        self.face_angle = (self.face_angle + 5.0) % 360
        if self.face_angle > 180:
            self.face_angle -= 360
        self.angle_var.set(f"角度: {self.face_angle:.1f}°")
        self.logger.info(f"手动顺时针旋转: {self.face_angle:.1f}°")
    
    def rotate_counterclockwise(self):
        """逆时针旋转"""
        self.face_angle = (self.face_angle - 5.0) % 360
        if self.face_angle > 180:
            self.face_angle -= 360
        self.angle_var.set(f"角度: {self.face_angle:.1f}°")
        self.logger.info(f"手动逆时针旋转: {self.face_angle:.1f}°")
    
    def reset_rotation(self):
        """重置旋转角度"""
        self.face_angle = 0.0
        self.angle_var.set("角度: 0.0°")
        self.logger.info("重置旋转角度")
    
    def set_display_size(self, width: int, height: int):
        """设置显示尺寸"""
        self.display_width = width
        self.display_height = height
        self.logger.info(f"显示尺寸设置为: {width}x{height}")
    
    def on_key_press(self, event):
        """键盘按键事件"""
        key = event.keysym.lower()
        if key == 'plus' or key == 'equal':
            self.zoom_in()
        elif key == 'minus':
            self.zoom_out()
        elif key == 'r':
            self.reset_zoom()
        elif key == 'f':
            self.manual_focus_face()
        elif key == 'a':
            self.auto_focus_var.set(not self.auto_focus_var.get())
            self.toggle_auto_focus()
        elif key == 'c':
            self.reset_view_center()
        elif key == 't':
            self.correction_var.set(not self.correction_var.get())
            self.toggle_image_correction()
        elif key == 'q':
            self.rotate_clockwise()
        elif key == 'e':
            self.rotate_counterclockwise()
    
    def on_closing(self):
        """窗口关闭事件"""
        self.stop_camera()
        self.face_detection.close()
        self.root.destroy()
    
    def run(self):
        """运行应用"""
        self.root.mainloop()


def main():
    """主函数"""
    logging.basicConfig(level=logging.INFO)
    
    import sys
    camera_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    viewer = EnhancedCameraViewer(camera_id)
    viewer.run()


if __name__ == "__main__":
    main()