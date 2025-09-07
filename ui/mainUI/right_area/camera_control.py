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

    def setup_camera_area(self, parent_frame):
        """设置摄像头区域"""
        # 摄像头控制面板
        self.main_app.camera_control_frame = ttk.LabelFrame(parent_frame, text=self.main_app.get_text("camera_control"), padding="5")
        self.main_app.camera_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.main_app.camera_control_frame.columnconfigure(0, weight=1)
        
        # 摄像头控制按钮
        control_buttons = ttk.Frame(self.main_app.camera_control_frame)
        control_buttons.pack(fill=tk.X, pady=5)
        
        # 摄像头选择
        self.main_app.camera_label = ttk.Label(control_buttons, text=self.main_app.get_text("camera"))
        self.main_app.camera_label.pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.camera_id_var = tk.StringVar(value="0")
        self.main_app.camera_combo = ttk.Combobox(control_buttons, textvariable=self.main_app.camera_id_var, 
                                        width=15, state="readonly")
        self.main_app.camera_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # 模型选择
        self.main_app.model_label = ttk.Label(control_buttons, text=self.main_app.get_text("model"))
        self.main_app.model_label.pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.model_var = tk.StringVar(value="ResEmoteNet")
        self.main_app.model_combo = ttk.Combobox(control_buttons, textvariable=self.main_app.model_var,
                                  values=["Simple", "ResEmoteNet", "FER2013", "EmoNeXt"], 
                                  width=12, state="readonly")
        self.main_app.model_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.model_combo.bind("<<ComboboxSelected>>", self.on_model_changed)
        
        # 刷新摄像头列表按钮
        self.main_app.refresh_btn = ttk.Button(control_buttons, text=self.main_app.get_text("refresh"), command=self.refresh_camera_list)
        self.main_app.refresh_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 初始化摄像头列表
        self.refresh_camera_list()
        
        # 摄像头启动/停止按钮
        self.main_app.camera_start_btn = ttk.Button(control_buttons, text=self.main_app.get_text("start_camera"), command=self.main_app.toggle_camera_only)
        self.main_app.camera_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 面部识别启动/停止按钮  
        self.main_app.face_detection_btn = ttk.Button(control_buttons, text=self.main_app.get_text("start_face_detection"), 
                                           command=self.main_app.toggle_face_detection, state="disabled")
        self.main_app.face_detection_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 截图按钮
        self.main_app.capture_btn = ttk.Button(control_buttons, text=self.main_app.get_text("screenshot"), command=self.main_app.capture_screenshot, 
                                     state="disabled")
        self.main_app.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 保存表情数据按钮
        self.main_app.save_expression_btn = ttk.Button(control_buttons, text=self.main_app.get_text("save_expression"), command=self.main_app.save_expression_data,
                                            state="disabled")
        self.main_app.save_expression_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 摄像头显示区域
        self.main_app.camera_display_frame = ttk.LabelFrame(parent_frame, text=self.main_app.get_text("camera_feed"), padding="5")
        self.main_app.camera_display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.main_app.camera_display_frame.columnconfigure(0, weight=1)
        self.main_app.camera_display_frame.rowconfigure(0, weight=1)
        
        # 视频显示标签 - 设置固定尺寸和样式
        self.main_app.video_label = tk.Label(self.main_app.camera_display_frame, text=self.main_app.get_text("click_to_start"), 
                                   bg="black", fg="white",
                                   font=("Arial", 12),
                                   width=80, height=30)  # 设置足够的显示空间
        self.main_app.video_label.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        # 表情数据显示区域
        self.main_app.expression_frame = ttk.LabelFrame(parent_frame, text=self.main_app.get_text("realtime_expression"), padding="5")
        self.main_app.expression_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        # 配置表情框架的列权重，避免重叠 - 每列占用3个网格位置
        self.main_app.expression_frame.columnconfigure(2, weight=1)  # 第一列进度条
        self.main_app.expression_frame.columnconfigure(5, weight=1)  # 第二列进度条
        
        # 表情数据标签 - 7种标准情感
        self.main_app.expressions = {
            'angry': 0.0,      # 愤怒
            'disgust': 0.0,    # 厌恶
            'fear': 0.0,       # 恐惧
            'happy': 0.0,      # 高兴
            'sad': 0.0,        # 伤心
            'surprise': 0.0,   # 惊讶
            'neutral': 0.0     # 中立
        }
        
        # 创建表情显示组件
        row = 0
        col = 0
        self.main_app.expression_labels = {}
        self.main_app.expression_progress_bars = {}
        
        for expr_name in self.main_app.expressions.keys():
            # 表情名称
            display_name = {
                'angry': '愤怒',
                'disgust': '厌恶',
                'fear': '恐惧', 
                'happy': '高兴',
                'sad': '伤心',
                'surprise': '惊讶',
                'neutral': '中立'
            }.get(expr_name, expr_name)
            
            # 使用正确的列偏移避免重叠：每列占用3个位置
            base_col = col * 3
            
            ttk.Label(self.main_app.expression_frame, text=f"{display_name}:").grid(
                row=row, column=base_col, sticky=tk.W, padx=(0, 5))
            
            # 数值显示
            value_label = ttk.Label(self.main_app.expression_frame, text="0.00", width=6)
            value_label.grid(row=row, column=base_col+1, sticky=tk.W, padx=(0, 5))
            self.main_app.expression_labels[expr_name] = value_label
            
            # 进度条
            progress = ttk.Progressbar(self.main_app.expression_frame, length=120, mode='determinate')
            progress.grid(row=row, column=base_col+2, sticky=(tk.W, tk.E), padx=(0, 15))
            progress['maximum'] = 100
            self.main_app.expression_progress_bars[expr_name] = progress
            
            col += 1
            if col >= 2:
                col = 0
                row += 1
        
        # 添加分隔线和整体状态显示
        row += 1
        separator = ttk.Separator(self.main_app.expression_frame, orient='horizontal')
        separator.grid(row=row, column=0, columnspan=6, sticky=(tk.W, tk.E), pady=(10, 5))
        
        row += 1
        # 整体情感状态显示
        ttk.Label(self.main_app.expression_frame, text="整体状态:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))
        
        self.main_app.overall_status_label = ttk.Label(self.main_app.expression_frame, text="中立 (0.00)", width=15)
        self.main_app.overall_status_label.grid(row=row, column=1, sticky=tk.W, padx=(0, 5))
        
        self.main_app.overall_status_progress = ttk.Progressbar(self.main_app.expression_frame, length=250, mode='determinate')
        self.main_app.overall_status_progress.grid(row=row, column=2, columnspan=4, sticky=(tk.W, tk.E), padx=(0, 15))
        self.main_app.overall_status_progress['maximum'] = 100