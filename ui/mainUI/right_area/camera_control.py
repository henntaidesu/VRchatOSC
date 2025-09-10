# -*- coding: utf-8 -*-
import cv2
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import time
import numpy as np
from tkinter import messagebox


class CameraControl:
    def __init__(self, main_app):
        self.main_app = main_app
        
        # 表情数据缓存和平均计算相关变量
        self.emotion_data_cache = []  # 存储表情数据的缓存
        self.last_emotion_update_time = 0  # 上次更新LLM情感状态的时间
        self.emotion_update_timer = None  # 定时器
        
        # 主导情感更新跟踪
        self.last_dominant_update_time = 0  # 上次主导情感更新的时间
        self.current_dominant_emotion = None  # 当前主导情感信息
        
        # 摄像头信息缓存
        self.detected_cameras_info = {}  # 存储摄像头详细信息
        
    def detect_camera_resolutions(self, camera_id):
        """检测摄像头支持的分辨率"""
        supported_resolutions = []
        
        # 常见分辨率列表（按从小到大排序）
        common_resolutions = [
            (320, 240),   # QVGA
            (640, 480),   # VGA
            (800, 600),   # SVGA
            (1024, 768),  # XGA
            (1280, 720),  # HD 720p
            (1280, 960),  # SXGA-
            (1600, 1200), # UXGA
            (1920, 1080), # Full HD 1080p
            (2560, 1440), # QHD
            (3840, 2160)  # 4K UHD
        ]
        
        try:
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return supported_resolutions
            
            for width, height in common_resolutions:
                # 尝试设置分辨率
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
                # 读取实际设置的分辨率
                actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # 如果实际分辨率与目标分辨率匹配，说明支持
                if actual_width == width and actual_height == height:
                    # 测试是否能实际读取帧
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.shape[:2] == (height, width):
                        supported_resolutions.append((width, height))
            
            cap.release()
            
        except Exception as e:
            print(f"检测摄像头 {camera_id} 分辨率失败: {e}")
        
        return supported_resolutions
    
    def get_camera_info(self, camera_id):
        """获取摄像头详细信息"""
        try:
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return None
            
            # 获取基本信息
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # 测试读取
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return None
            
            cap.release()
            
            # 获取支持的分辨率
            supported_resolutions = self.detect_camera_resolutions(camera_id)
            
            camera_info = {
                'id': camera_id,
                'default_width': width,
                'default_height': height,
                'fps': fps if fps > 0 else 30,  # 如果获取不到FPS，默认30
                'supported_resolutions': supported_resolutions,
                'working': True
            }
            
            return camera_info
            
        except Exception as e:
            print(f"获取摄像头 {camera_id} 信息失败: {e}")
            return None

    def detect_available_cameras(self, log_callback=None):
        """检测可用的摄像头（增强版）"""
        available_cameras = []
        detected_cameras_info = {}
        
        # 使用线程安全的日志记录方式
        def safe_log(message):
            if log_callback:
                log_callback(message)
            else:
                print(message)  # 后备日志方法
        
        safe_log("开始检测摄像头和分辨率...")
        
        # 检查多个摄像头ID
        for i in range(8):  # 扩展到检查更多摄像头
            try:
                safe_log(f"正在检测摄像头 {i}...")
                camera_info = self.get_camera_info(i)
                
                if camera_info:
                    # 获取最大支持分辨率作为默认分辨率
                    if camera_info['supported_resolutions']:
                        # 按分辨率大小排序，选择最大的
                        max_res = max(camera_info['supported_resolutions'], key=lambda res: res[0] * res[1])
                        max_res_str = f"{max_res[0]}x{max_res[1]}"
                        # 更新camera_info中的默认分辨率为最大分辨率
                        camera_info['default_width'] = max_res[0]
                        camera_info['default_height'] = max_res[1]
                        default_res = max_res_str
                    else:
                        default_res = f"{camera_info['default_width']}x{camera_info['default_height']}"
                    
                    supported_count = len(camera_info['supported_resolutions'])
                    
                    if supported_count > 1:
                        display_name = f"摄像头 {i} (最大{default_res}, {supported_count}种分辨率)"
                    else:
                        display_name = f"摄像头 {i} ({default_res})"
                    
                    available_cameras.append((i, display_name))
                    detected_cameras_info[i] = camera_info
                    
                    # 详细日志
                    resolutions_str = ", ".join([f"{w}x{h}" for w, h in camera_info['supported_resolutions']])
                    safe_log(f"[OK] 摄像头 {i}: 最大分辨率{default_res}, FPS:{camera_info['fps']:.1f}")
                    safe_log(f"  支持分辨率: {resolutions_str}")
                    
            except Exception as e:
                # 忽略检测失败的摄像头
                continue
        
        # 保存摄像头信息供后续使用
        self.detected_cameras_info = detected_cameras_info
        
        safe_log(f"检测完成，发现 {len(available_cameras)} 个可用摄像头")
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
                    # 创建线程安全的日志回调
                    log_messages = []
                    def thread_safe_log(message):
                        log_messages.append(message)
                    
                    available_cameras = self.detect_available_cameras(log_callback=thread_safe_log)
                    
                    # 在主线程中更新UI和日志
                    def update_ui_and_logs():
                        # 输出所有日志消息
                        for msg in log_messages:
                            self.main_app.log(msg)
                        # 更新摄像头列表
                        self.update_camera_list(available_cameras)
                    
                    self.main_app.root.after(0, update_ui_and_logs)
                    
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
                
                # 更新分辨率选项
                self.update_resolution_options()
                
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
        self.main_app.camera_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 3))
        self.main_app.camera_control_frame.columnconfigure(0, weight=1)
        
        # 第一行：摄像头控制选择框架
        control_row1 = ttk.Frame(self.main_app.camera_control_frame)
        control_row1.pack(fill=tk.X, pady=(5, 2))
        
        # 摄像头选择
        self.main_app.camera_label = ttk.Label(control_row1, text=self.main_app.get_text("camera"))
        self.main_app.camera_label.pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.camera_id_var = tk.StringVar(value="0")
        self.main_app.camera_combo = ttk.Combobox(control_row1, textvariable=self.main_app.camera_id_var, 
                                        width=15, state="readonly")
        self.main_app.camera_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.camera_combo.bind("<<ComboboxSelected>>", self.on_camera_changed)
        
        # 模型选择
        self.main_app.model_label = ttk.Label(control_row1, text=self.main_app.get_text("model"))
        self.main_app.model_label.pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.model_var = tk.StringVar(value="ResEmoteNet")
        self.main_app.model_combo = ttk.Combobox(control_row1, textvariable=self.main_app.model_var,
                                  values=["Simple", "ResEmoteNet", "FER2013", "EmoNeXt"], 
                                  width=12, state="readonly")
        self.main_app.model_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.model_combo.bind("<<ComboboxSelected>>", self.on_model_changed)
        
        # 刷新摄像头列表按钮
        self.main_app.refresh_btn = ttk.Button(control_row1, text=self.main_app.get_text("refresh"), command=self.refresh_camera_list)
        self.main_app.refresh_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 分辨率选择
        self.main_app.resolution_label = ttk.Label(control_row1, text="分辨率")
        self.main_app.resolution_label.pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.resolution_var = tk.StringVar(value="1920x1080")
        self.main_app.resolution_combo = ttk.Combobox(control_row1, textvariable=self.main_app.resolution_var,
                                        width=10, state="readonly")
        self.main_app.resolution_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.resolution_combo.bind("<<ComboboxSelected>>", self.on_resolution_changed)
        
        # 初始化摄像头列表
        self.refresh_camera_list()
        
        # 第二行：控制按钮框架
        control_row2 = ttk.Frame(self.main_app.camera_control_frame)
        control_row2.pack(fill=tk.X, pady=(2, 5))
        
        # 摄像头启动/停止按钮
        self.main_app.camera_start_btn = ttk.Button(control_row2, text=self.main_app.get_text("start_camera"), command=self.toggle_camera_only)
        self.main_app.camera_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 面部识别启动/停止按钮  
        self.main_app.face_detection_btn = ttk.Button(control_row2, text=self.main_app.get_text("start_face_detection"), 
                                           command=self.toggle_face_detection, state="disabled")
        self.main_app.face_detection_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 截图按钮
        self.main_app.capture_btn = ttk.Button(control_row2, text=self.main_app.get_text("screenshot"), command=self.capture_screenshot, 
                                     state="disabled")
        self.main_app.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 保存表情数据按钮
        self.main_app.save_expression_btn = ttk.Button(control_row2, text=self.main_app.get_text("save_expression"), command=self.save_expression_data,
                                            state="disabled")
        self.main_app.save_expression_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 摄像头参数控制框架（新增的一行）
        camera_params_frame = ttk.Frame(self.main_app.camera_control_frame)
        camera_params_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 对焦按钮
        self.main_app.focus_btn = ttk.Button(camera_params_frame, text="自动对焦", command=self.auto_focus, state="disabled")
        self.main_app.focus_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 变焦控制
        ttk.Label(camera_params_frame, text="变焦:").pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.zoom_var = tk.DoubleVar(value=1.0)
        self.main_app.zoom_scale = ttk.Scale(camera_params_frame, from_=1.0, to=5.0,
                                       variable=self.main_app.zoom_var,
                                       orient='horizontal',
                                       command=self.on_zoom_changed)
        self.main_app.zoom_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.main_app.zoom_label = ttk.Label(camera_params_frame, text="1.0x")
        self.main_app.zoom_label.pack(side=tk.LEFT)
        
        # 表情更新间隔控制
        interval_frame = ttk.Frame(self.main_app.camera_control_frame)
        interval_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 表情更新间隔标签和滑块
        ttk.Label(interval_frame, text="表情更新间隔:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.main_app.emotion_update_interval_var = tk.DoubleVar(value=3.0)  # 默认3秒
        self.main_app.emotion_interval_scale = ttk.Scale(interval_frame, from_=1.0, to=10.0,
                                                variable=self.main_app.emotion_update_interval_var,
                                                orient='horizontal',
                                                command=self._on_emotion_interval_changed)
        self.main_app.emotion_interval_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.main_app.emotion_interval_label = ttk.Label(interval_frame, text=self.main_app.get_text("emotion_interval"))
        self.main_app.emotion_interval_label.pack(side=tk.LEFT)
        
        # 摄像头显示区域 - 调整到更上方位置
        self.main_app.camera_display_frame = ttk.LabelFrame(parent_frame, text=self.main_app.get_text("camera_feed"), padding="2")
        self.main_app.camera_display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(3, 3), ipady=2)
        self.main_app.camera_display_frame.columnconfigure(0, weight=1)
        self.main_app.camera_display_frame.rowconfigure(0, weight=1)
        
        # 视频显示标签 - 修复向下偏移问题
        self.main_app.video_label = tk.Label(self.main_app.camera_display_frame, text=self.main_app.get_text("click_to_start"), 
                                   bg="black", fg="white",
                                   font=("Arial", 12),
                                   anchor="center", justify="center")  # 移除固定宽高，避免布局问题
        self.main_app.video_label.pack(expand=True, fill=tk.BOTH, padx=2, pady=2)  # 减少内边距避免挤压
        
        # 表情数据显示区域
        self.main_app.expression_frame = ttk.LabelFrame(parent_frame, text=self.main_app.get_text("realtime_expression"), padding="5")
        self.main_app.expression_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(3, 10))
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
        
        # 主导情感状态显示
        row += 1
        ttk.Label(self.main_app.expression_frame, text="主导情感:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))
        
        self.main_app.dominant_emotion_label = ttk.Label(self.main_app.expression_frame, text="无数据", width=30)
        self.main_app.dominant_emotion_label.grid(row=row, column=1, columnspan=5, sticky=tk.W, padx=(0, 5))
    
    def toggle_camera_only(self):
        """只切换摄像头状态（不包含面部识别）"""
        if not self.main_app.camera_running:
            self.start_camera_only()
        else:
            self.stop_camera_only()
    
    def toggle_face_detection(self):
        """切换面部识别状态"""
        if not self.main_app.face_detection_running:
            self.start_face_detection()
        else:
            self.stop_face_detection()
    
    def start_camera_only(self):
        """只启动摄像头（不启动面部识别）"""
        try:
            # 获取选中的摄像头信息
            selected_camera = self.main_app.camera_id_var.get()
            
            # 从映射中获取实际的摄像头ID
            if hasattr(self.main_app, 'camera_id_mapping') and selected_camera in self.main_app.camera_id_mapping:
                camera_id = self.main_app.camera_id_mapping[selected_camera]
            else:
                try:
                    camera_id = int(selected_camera.split()[1]) if '摄像头' in selected_camera else int(selected_camera)
                except:
                    camera_id = 0
                    self.main_app.log("无法解析摄像头ID，使用默认摄像头0")
            
            self.main_app.log(f"正在启动摄像头: {selected_camera} (ID: {camera_id})")
            
            # 直接使用OpenCV启动摄像头
            self.main_app.camera = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            
            if not self.main_app.camera.isOpened():
                raise RuntimeError(f"无法打开摄像头 {camera_id}")
            
            # 测试读取
            ret, frame = self.main_app.camera.read()
            if not ret or frame is None:
                raise RuntimeError(f"摄像头 {camera_id} 无法读取画面")
            
            # 设置分辨率为最大支持分辨率
            if camera_id in self.detected_cameras_info:
                camera_info = self.detected_cameras_info[camera_id]
                width = camera_info['default_width']  # 这已经是最大分辨率
                height = camera_info['default_height']
                self.main_app.log(f"设置摄像头分辨率为: {width}x{height}")
                self.main_app.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.main_app.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            else:
                # 后备选项：使用高分辨率
                self.main_app.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                self.main_app.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            
            self.main_app.camera_running = True
            self.main_app.camera_start_btn.config(text="停止摄像头")
            self.main_app.face_detection_btn.config(state="normal")
            self.main_app.capture_btn.config(state="normal")
            self.main_app.save_expression_btn.config(state="normal")
            
            # 启用摄像头控制按钮
            if hasattr(self.main_app, 'focus_btn'):
                self.main_app.focus_btn.config(state="normal")
            
            # 启动视频显示线程
            self.main_app.camera_thread = threading.Thread(target=self.simple_video_loop, daemon=True)
            self.main_app.camera_thread.start()
            
            self.main_app.log(f"摄像头启动成功: {selected_camera}")
            
        except Exception as e:
            self.main_app.log(f"启动摄像头失败: {e}")
            if hasattr(self.main_app, 'camera') and self.main_app.camera:
                self.main_app.camera.release()
                self.main_app.camera = None
            self.main_app.camera_running = False
    
    def start_face_detection(self):
        """启动面部识别"""
        try:
            self.main_app.log(f"正在启动面部识别模型: {self.main_app.emotion_model_type}")
            
            # 如果使用GPU模型，初始化检测器
            if self.main_app.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
                if not hasattr(self.main_app, 'gpu_detector') or self.main_app.gpu_detector is None:
                    try:
                        from src.face.gpu_emotion_detector import GPUEmotionDetector
                        self.main_app.gpu_detector = GPUEmotionDetector(model_type=self.main_app.emotion_model_type, device='auto')
                        self.main_app.log(f"成功初始化GPU情感检测器: {self.main_app.emotion_model_type}")
                    except Exception as e:
                        self.main_app.log(f"GPU检测器初始化失败: {e}")
                        self.main_app.log("将使用Simple模式作为后备")
                        self.main_app.emotion_model_type = 'Simple'
            
            # 这里不需要重新创建摄像头实例，只是设置标志
            self.main_app.face_detection_running = True
            self.main_app.face_detection_btn.config(text="停止面部识别")
            
            # 启动表情更新定时器
            import time
            self.last_emotion_update_time = time.time()
            self.last_dominant_update_time = 0  # 重置主导情感更新时间
            self.emotion_data_cache.clear()
            
            # 重置主导情感显示
            if hasattr(self.main_app, 'dominant_emotion_label'):
                self.main_app.dominant_emotion_label.config(text="等待检测...")
            
            self._start_emotion_update_timer()
            
            self.main_app.log("面部识别启动成功")
            
        except Exception as e:
            self.main_app.log(f"面部识别启动失败: {e}")
    
    def stop_camera_only(self):
        """只停止摄像头"""
        try:
            self.main_app.log("正在停止摄像头...")
            self.main_app.camera_running = False
            
            # 同时停止面部识别
            if self.main_app.face_detection_running:
                self.main_app.face_detection_running = False
                self.main_app.face_detection_btn.config(text=self.main_app.get_text("start_face_detection"), state="disabled")
                
                # 停止表情更新定时器
                if self.emotion_update_timer:
                    self.main_app.root.after_cancel(self.emotion_update_timer)
                    self.emotion_update_timer = None
                
                # 清空缓存
                self.emotion_data_cache.clear()
            
            # 等待线程结束
            if hasattr(self.main_app, 'camera_thread') and self.main_app.camera_thread and self.main_app.camera_thread.is_alive():
                self.main_app.camera_thread.join(timeout=2)
            
            # 释放摄像头
            if hasattr(self.main_app, 'camera') and self.main_app.camera:
                self.main_app.camera.release()
                self.main_app.camera = None
            
            # 释放GPU检测器资源
            if hasattr(self.main_app, 'gpu_detector') and self.main_app.gpu_detector is not None:
                try:
                    self.main_app.gpu_detector.release()
                    self.main_app.gpu_detector = None
                    self.main_app.log("GPU情感检测器资源已释放")
                except Exception as e:
                    self.main_app.log(f"释放GPU检测器资源时出错: {e}")
            
            # 更新UI
            self.main_app.camera_start_btn.config(text=self.main_app.get_text("start_camera"))
            self.main_app.capture_btn.config(state="disabled")
            self.main_app.save_expression_btn.config(state="disabled")
            self.main_app.video_label.config(image="", text=self.main_app.get_text("click_to_start"))
            
            # 禁用摄像头控制按钮
            if hasattr(self.main_app, 'focus_btn'):
                self.main_app.focus_btn.config(state="disabled")
            
            self.main_app.log(self.main_app.get_text("camera_stopped"))
            
        except Exception as e:
            self.main_app.log(f"停止摄像头错误: {e}")
    
    def stop_face_detection(self):
        """停止面部识别"""
        try:
            self.main_app.face_detection_running = False
            self.main_app.face_detection_btn.config(text="启动面部识别")
            
            # 停止表情更新定时器
            if self.emotion_update_timer:
                self.main_app.root.after_cancel(self.emotion_update_timer)
                self.emotion_update_timer = None
            
            # 清空缓存
            self.emotion_data_cache.clear()
            
            # 重置表情数据为默认值
            default_expressions = {
                'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0,
                'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0
            }
            self._update_expression_display(default_expressions)
            
            # 重置主导情感显示
            if hasattr(self.main_app, 'dominant_emotion_label'):
                self.main_app.dominant_emotion_label.config(text="无数据")
            
            # 重置时间戳
            self.last_dominant_update_time = 0
            self.current_dominant_emotion = None
            
            self.main_app.log("面部识别已停止")
            
        except Exception as e:
            self.main_app.log(f"停止面部识别失败: {e}")
    
    
    def capture_screenshot(self):
        """截图功能"""
        if not self.main_app.camera_running or not hasattr(self.main_app, 'camera') or not self.main_app.camera:
            return
        
        try:
            ret, frame = self.main_app.camera.read()
            if ret and frame is not None:
                import os
                from datetime import datetime
                
                # 创建截图目录
                screenshot_dir = "screenshots"
                if not os.path.exists(screenshot_dir):
                    os.makedirs(screenshot_dir)
                
                # 生成文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.jpg"
                filepath = os.path.join(screenshot_dir, filename)
                
                # 保存图片
                cv2.imwrite(filepath, frame)
                self.main_app.log(f"截图已保存: {filepath}")
                
        except Exception as e:
            self.main_app.log(f"截图失败: {e}")
    
    def save_expression_data(self):
        """保存表情数据"""
        if not hasattr(self.main_app, 'expressions'):
            return
        
        try:
            import json
            import os
            from datetime import datetime
            
            # 创建数据目录
            data_dir = "expression_data"
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"expressions_{timestamp}.json"
            filepath = os.path.join(data_dir, filename)
            
            # 保存数据
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.main_app.expressions, f, ensure_ascii=False, indent=2)
            
            self.main_app.log(f"表情数据已保存: {filepath}")
            
        except Exception as e:
            self.main_app.log(f"保存表情数据失败: {e}")
    
    def process_face_detection(self, frame):
        """处理面部识别"""
        expressions = {
            'angry': 0.0,      # 愤怒
            'disgust': 0.0,    # 厌恶
            'fear': 0.0,       # 恐惧
            'happy': 0.0,      # 高兴
            'sad': 0.0,        # 伤心
            'surprise': 0.0,   # 惊讶
            'neutral': 0.0     # 中立
        }
        
        try:
            if self.main_app.emotion_model_type == 'Simple':
                # 使用优化的OpenCV检测
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                
                # 使用与GPU模型相同的优化参数
                faces = face_cascade.detectMultiScale(
                    gray, 
                    scaleFactor=1.1,        # 更精细的尺度步长
                    minNeighbors=5,         # 增加最小邻居数，减少误检
                    minSize=(60, 60),       # 增大最小面部尺寸，过滤小物体
                    maxSize=(400, 400),     # 适当限制最大尺寸
                    flags=cv2.CASCADE_SCALE_IMAGE  # 使用更稳定的检测方式
                )
                
                # 验证并绘制面部框
                valid_faces = []
                for (x, y, w, h) in faces:
                    # 基本有效性检查
                    if self._is_valid_simple_face(gray, x, y, w, h):
                        valid_faces.append((x, y, w, h))
                        
                        # 绘制更明显的面部框
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
                        cv2.putText(frame, "Face Detected (Simple)", (x, y-15), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        
                        # 显示面部尺寸信息
                        size_text = f"Size: {w}x{h}"
                        cv2.putText(frame, size_text, (x, y + h + 20), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                
                # Simple模式：只显示检测到的面部数量，不生成假数据
                if len(valid_faces) > 0:
                    # 在右上角显示检测统计
                    stats_text = f"Faces: {len(valid_faces)}"
                    cv2.putText(frame, stats_text, (frame.shape[1] - 120, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            elif self.main_app.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
                # 使用GPU加速的情感识别模型
                if hasattr(self.main_app, 'gpu_detector') and self.main_app.gpu_detector is not None:
                    try:
                        annotated_frame, expressions = self.main_app.gpu_detector.process_frame(frame)
                        return annotated_frame, expressions
                    except Exception as gpu_e:
                        import traceback
                        self.main_app.log(f"GPU情感识别处理错误 ({self.main_app.emotion_model_type}): {gpu_e}")
                        self.main_app.log(f"详细错误信息: {traceback.format_exc()}")
                        # 回退到简单模式
                        return self.process_simple_detection(frame)
                else:
                    # 如果GPU检测器未初始化，尝试创建
                    try:
                        from src.face.gpu_emotion_detector import GPUEmotionDetector
                        self.main_app.gpu_detector = GPUEmotionDetector(model_type=self.main_app.emotion_model_type, device='auto')
                        self.main_app.log(f"成功初始化GPU情感检测器: {self.main_app.emotion_model_type}")
                        annotated_frame, expressions = self.main_app.gpu_detector.process_frame(frame)
                        return annotated_frame, expressions
                    except Exception as init_e:
                        import traceback
                        self.main_app.log(f"GPU情感检测器初始化失败 ({self.main_app.emotion_model_type}): {init_e}")
                        self.main_app.log(f"详细错误信息: {traceback.format_exc()}")
                        self.main_app.log("回退到简单模式")
                        return self.process_simple_detection(frame)
            
        except Exception as e:
            self.main_app.log(f"面部识别处理错误: {e}")
        
        return frame, expressions
    
    def _update_expression_display(self, expressions):
        """更新表情显示（在主线程中调用）"""
        try:
            # 更新表情数据
            self.main_app.expressions.update(expressions)
            
            # 更新UI显示
            for expr_name, value in expressions.items():
                if expr_name in self.main_app.expression_labels:
                    self.main_app.expression_labels[expr_name].config(text=f"{value:.2f}")
                if expr_name in self.main_app.expression_progress_bars:
                    self.main_app.expression_progress_bars[expr_name]['value'] = value * 100
            
            # 更新整体状态
            self._update_overall_status(expressions)
            
            # 将表情数据添加到缓存（用于平均计算）
            self._add_emotion_to_cache(expressions)
            
        except Exception as e:
            self.main_app.log(f"更新表情显示失败: {e}")
    
    def _on_emotion_interval_changed(self, value):
        """表情更新间隔滑块变化回调"""
        try:
            interval = float(value)
            self.main_app.emotion_interval_label.config(text=f"{interval:.1f}s")
            
            # 重启定时器（如果正在运行）
            if self.emotion_update_timer:
                self.main_app.root.after_cancel(self.emotion_update_timer)
                self.emotion_update_timer = None
            
            # 清空缓存重新开始
            self.emotion_data_cache.clear()
            import time
            self.last_emotion_update_time = time.time()
            
            # 启动新的定时器
            self._start_emotion_update_timer()
            
            self.main_app.log(f"表情更新间隔已设置为: {interval:.1f}秒")
            
        except Exception as e:
            self.main_app.log(f"更新表情间隔设置失败: {e}")
    
    def _start_emotion_update_timer(self):
        """启动表情更新定时器"""
        try:
            if hasattr(self.main_app, 'face_detection_running') and self.main_app.face_detection_running:
                interval_ms = int(self.main_app.emotion_update_interval_var.get() * 1000)
                self.emotion_update_timer = self.main_app.root.after(interval_ms, self._process_emotion_average)
        except Exception as e:
            self.main_app.log(f"启动表情定时器失败: {e}")
    
    def _process_emotion_average(self):
        """处理表情数据平均值并更新LLM"""
        try:
            if self.emotion_data_cache:
                # 计算平均表情数据
                avg_emotions = self._calculate_average_emotions()
                
                # 更新LLM的情感状态
                if hasattr(self.main_app, 'llm_processor') and self.main_app.llm_processor:
                    try:
                        self.main_app.llm_processor.update_emotion_state(avg_emotions)
                        
                        # 记录主导情感和时间间隔
                        import time
                        current_time = time.time()
                        dominant_emotion = max(avg_emotions.items(), key=lambda x: x[1])
                        
                        if dominant_emotion[1] > 0.3:  # 只有当情感强度超过阈值时才记录
                            # 计算时间间隔
                            interval = current_time - self.last_dominant_update_time if self.last_dominant_update_time > 0 else 0
                            
                            # 更新主导情感显示
                            self._update_dominant_emotion_display(dominant_emotion, interval)
                            
                            # 记录日志
                            self.main_app.log(f"[情感更新] 主导情感: {dominant_emotion[0]}, 强度: {dominant_emotion[1]:.2f}")
                            
                            # 更新时间戳
                            self.last_dominant_update_time = current_time
                        
                    except Exception as llm_e:
                        print(f"更新LLM情感状态失败: {llm_e}")
                
                # 清空缓存准备下一轮
                self.emotion_data_cache.clear()
                import time
                self.last_emotion_update_time = time.time()
            
            # 继续下一轮定时器
            self._start_emotion_update_timer()
            
        except Exception as e:
            self.main_app.log(f"处理表情平均值失败: {e}")
    
    def _calculate_average_emotions(self):
        """计算缓存中表情数据的平均值"""
        if not self.emotion_data_cache:
            return {'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0, 
                   'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0}
        
        # 计算各个情感的平均值
        avg_emotions = {}
        emotion_names = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
        
        for emotion in emotion_names:
            values = [data.get(emotion, 0.0) for data in self.emotion_data_cache]
            avg_emotions[emotion] = sum(values) / len(values) if values else 0.0
        
        return avg_emotions
    
    def _add_emotion_to_cache(self, emotions):
        """将表情数据添加到缓存中"""
        try:
            import time
            
            # 添加时间戳
            emotion_data = emotions.copy()
            emotion_data['timestamp'] = time.time()
            
            # 添加到缓存
            self.emotion_data_cache.append(emotion_data)
            
            # 限制缓存大小（防止内存过多占用）
            max_cache_size = 1000  # 最多保存1000帧数据
            if len(self.emotion_data_cache) > max_cache_size:
                self.emotion_data_cache.pop(0)
            
        except Exception as e:
            print(f"添加表情数据到缓存失败: {e}")
    
    def _resize_frame_keep_aspect_ratio(self, frame, target_size):
        """
        保持宽高比缩放图像，防止变形
        
        Args:
            frame: 输入图像 (numpy array)
            target_size: 目标尺寸 (width, height)
        
        Returns:
            调整大小后的图像，保持宽高比，空白区域用黑色填充
        """
        try:
            target_width, target_height = target_size
            
            # 检查输入frame是否有效
            if frame is None:
                return np.zeros((target_height, target_width, 3), dtype=np.uint8)
            
            # 检查frame是否为空数组
            if hasattr(frame, 'size') and frame.size == 0:
                return np.zeros((target_height, target_width, 3), dtype=np.uint8)
            
            # 检查frame形状
            if len(frame.shape) < 2:
                return np.zeros((target_height, target_width, 3), dtype=np.uint8)
                
            height, width = frame.shape[:2]
            
            # 检查原始尺寸是否有效
            if width <= 0 or height <= 0:
                return np.zeros((target_height, target_width, 3), dtype=np.uint8)
            
            # 确保frame是3通道BGR格式
            if len(frame.shape) == 2:  # 灰度图
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif len(frame.shape) == 3 and frame.shape[2] == 4:  # RGBA
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # 计算缩放比例，选择较小的比例以确保完整显示
            scale_w = target_width / width
            scale_h = target_height / height
            scale = min(scale_w, scale_h)
            
            # 如果原图已经很小，限制最大缩放倍数避免过度放大
            if scale > 3.0:
                scale = 3.0
            
            # 计算缩放后的新尺寸
            new_width = max(1, int(width * scale))
            new_height = max(1, int(height * scale))
            
            # 缩放图像
            resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # 创建目标尺寸的黑色背景
            result = np.zeros((target_height, target_width, 3), dtype=np.uint8)
            
            # 计算居中位置 - 优先上下居中
            x_offset = (target_width - new_width) // 2
            y_offset = (target_height - new_height) // 2
            
            # 确保偏移量不为负数
            x_offset = max(0, x_offset)
            y_offset = max(0, y_offset)
            
            # 如果图像比目标区域小，确保垂直居中
            if new_height < target_height:
                y_offset = (target_height - new_height) // 2
            
            # 确保不越界
            end_y = min(target_height, y_offset + new_height)
            end_x = min(target_width, x_offset + new_width)
            
            # 将缩放后的图像放到中心位置
            result[y_offset:end_y, x_offset:end_x] = resized_frame[:end_y-y_offset, :end_x-x_offset]
            
            return result
            
        except Exception as e:
            # 静默处理异常，返回黑色背景
            return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
    
    def _update_overall_status(self, expressions):
        """更新整体情感状态显示"""
        try:
            # 找到最强烈的情感
            max_emotion = max(expressions, key=expressions.get)
            max_value = expressions[max_emotion]
            
            # 情感中文名称映射
            emotion_names = {
                'angry': '愤怒', 'disgust': '厌恶', 'fear': '恐惧',
                'happy': '高兴', 'sad': '伤心', 'surprise': '惊讶', 'neutral': '中立'
            }
            
            emotion_name_cn = emotion_names.get(max_emotion, max_emotion)
            
            # 更新标签和进度条
            if hasattr(self.main_app, 'overall_status_label'):
                self.main_app.overall_status_label.config(text=f"{emotion_name_cn} ({max_value:.2f})")
            if hasattr(self.main_app, 'overall_status_progress'):
                self.main_app.overall_status_progress['value'] = max_value * 100
            
        except Exception as e:
            self.main_app.log(f"更新整体状态失败: {e}")
    
    def _update_dominant_emotion_display(self, dominant_emotion, interval):
        """更新主导情感显示"""
        try:
            emotion_name, intensity = dominant_emotion
            
            # 情感中文名称映射
            emotion_names = {
                'angry': '愤怒', 'disgust': '厌恶', 'fear': '恐惧',
                'happy': '高兴', 'sad': '伤心', 'surprise': '惊讶', 'neutral': '中立'
            }
            
            emotion_name_cn = emotion_names.get(emotion_name, emotion_name)
            
            # 格式化时间间隔
            if interval > 0:
                interval_text = f"间隔: {interval:.1f}秒"
            else:
                interval_text = "首次更新"
            
            # 更新显示文本
            display_text = f"{emotion_name_cn} (强度: {intensity:.2f}) - {interval_text}"
            
            # 更新UI
            if hasattr(self.main_app, 'dominant_emotion_label'):
                self.main_app.dominant_emotion_label.config(text=display_text)
            
            # 保存当前信息
            self.current_dominant_emotion = {
                'name': emotion_name,
                'name_cn': emotion_name_cn,
                'intensity': intensity,
                'interval': interval
            }
            
        except Exception as e:
            self.main_app.log(f"更新主导情感显示失败: {e}")
    
    def send_expressions_to_vrchat(self, expressions):
        """发送表情数据到VRChat"""
        try:
            if self.main_app.client and self.main_app.is_connected and hasattr(self.main_app.client, 'osc_client'):
                # VRChat表情参数映射 - 7种标准情感
                vrchat_params = {
                    'angry': '/avatar/parameters/FaceAngry',
                    'disgust': '/avatar/parameters/FaceDisgust',
                    'fear': '/avatar/parameters/FaceFear',
                    'happy': '/avatar/parameters/FaceHappy',
                    'sad': '/avatar/parameters/FaceSad',
                    'surprise': '/avatar/parameters/FaceSurprise',
                    'neutral': '/avatar/parameters/FaceNeutral'
                }
                
                # 发送每个表情参数
                for expr_name, value in expressions.items():
                    if expr_name in vrchat_params:
                        param_address = vrchat_params[expr_name]
                        # 确保值在0-1范围内
                        clamped_value = max(0.0, min(1.0, value))
                        self.main_app.client.osc_client.send_parameter(param_address, clamped_value)
                        
        except Exception as e:
            # 静默处理错误，避免日志过多
            current_time = time.time()
            if hasattr(self.main_app, 'last_expression_error_time'):
                # 只每10秒记录一次错误
                if current_time - self.main_app.last_expression_error_time > 10:
                    self.main_app.log(f"表情数据发送错误: {e}")
                    self.main_app.last_expression_error_time = current_time
            else:
                self.main_app.last_expression_error_time = current_time
                self.main_app.log(f"表情数据发送错误: {e}")
    
    def simple_video_loop(self):
        """简单的视频显示循环（统一使用保持宽高比的显示方式）"""
        frame_count = 0
        last_error_time = 0
        
        while self.main_app.camera_running and self.main_app.camera and self.main_app.camera.isOpened():
            try:
                ret, frame = self.main_app.camera.read()
                if ret and frame is not None and frame.size > 0:
                    frame_count += 1
                    
                    # 如果启用了面部识别，进行处理
                    if self.main_app.face_detection_running:
                        try:
                            display_frame, expressions = self.process_face_detection(frame)
                            # 更新表情显示
                            self.main_app.root.after(0, lambda e=expressions: self._update_expression_display(e))
                        except Exception as face_e:
                            display_frame = frame
                            if time.time() - last_error_time > 5:  # 每5秒最多报告一次错误
                                self.main_app.log(f"面部检测错误: {face_e}")
                                last_error_time = time.time()
                    else:
                        display_frame = frame
                    
                    # 应用数字变焦
                    if hasattr(self.main_app, 'current_zoom_level') and self.main_app.current_zoom_level > 1.0:
                        display_frame = self.apply_digital_zoom_to_frame(display_frame, self.main_app.current_zoom_level)
                    
                    # 使用保持宽高比的缩放方式
                    display_frame = self._resize_frame_keep_aspect_ratio(display_frame, (640, 480))
                    
                    # 确保显示帧有效
                    if display_frame is not None and display_frame.size > 0:
                        # 转换为显示格式
                        frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(frame_rgb)
                        photo = ImageTk.PhotoImage(img)
                        
                        # 更新显示
                        self.main_app.current_frame = frame
                        self.main_app.root.after(0, lambda p=photo: self.update_video_display(p))
                    
                else:
                    # 如果读取失败，等待更长时间
                    time.sleep(0.1)
                    continue
                    
                time.sleep(0.03)  # 约33fps
                
            except Exception as e:
                if self.main_app.camera_running:
                    # 限制错误日志频率
                    current_time = time.time()
                    if current_time - last_error_time > 3:  # 每3秒最多报告一次错误
                        self.main_app.log(f"视频循环错误: {e}")
                        last_error_time = current_time
                time.sleep(0.1)
    
    def update_video_display(self, photo):
        """更新视频显示（在主线程中调用）"""
        try:
            if self.main_app.camera_running and photo and hasattr(self.main_app, 'video_label'):
                # 确保video_label存在且有效
                if self.main_app.video_label.winfo_exists():
                    self.main_app.video_label.config(image=photo, text="")
                    self.main_app.video_label.image = photo  # 保持引用防止垃圾回收
        except Exception as e:
            # 静默处理显示更新错误，避免日志过多
            pass
    
    def process_simple_detection(self, frame):
        """简单的面部检测处理（作为GPU模式的后备）"""
        expressions = {
            'angry': 0.0,      # 愤怒
            'disgust': 0.0,    # 厌恶
            'fear': 0.0,       # 恐惧
            'happy': 0.0,      # 高兴
            'sad': 0.0,        # 伤心
            'surprise': 0.0,   # 惊讶
            'neutral': 0.0     # 中立
        }
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(100, 100))
            
            # 绘制面部框和更新表情数据
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, "Face Detected (Simple)", (x, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # 简单模式回退：只显示面部检测，不生成假表情数据
            if len(faces) > 0:
                # 保持默认表情值，不生成模拟数据
                pass
                
        except Exception as e:
            self.main_app.log(f"简单面部检测错误: {e}")
        
        return frame, expressions
    
    def open_camera_window(self):
        """打开摄像头窗口（保留原功能作为备选）"""
        try:
            from ui.camera_window import CameraWindow
            CameraWindow(self.main_app.root)
        except Exception as e:
            messagebox.showerror("摄像头错误", f"无法打开摄像头窗口: {e}")
            self.main_app.log(f"打开摄像头窗口失败: {e}")
    
    def update_resolution_options(self):
        """更新分辨率选项"""
        try:
            # 获取当前选中的摄像头
            selected_camera = self.main_app.camera_id_var.get()
            
            if hasattr(self.main_app, 'camera_id_mapping') and selected_camera in self.main_app.camera_id_mapping:
                camera_id = self.main_app.camera_id_mapping[selected_camera]
                
                # 获取支持的分辨率
                if camera_id in self.detected_cameras_info:
                    camera_info = self.detected_cameras_info[camera_id]
                    supported_resolutions = camera_info.get('supported_resolutions', [])
                    
                    if supported_resolutions:
                        # 转换为字符串格式并按分辨率大小排序
                        resolution_strings = [f"{w}x{h}" for w, h in supported_resolutions]
                        resolution_strings.sort(key=lambda x: int(x.split('x')[0]) * int(x.split('x')[1]), reverse=True)
                        
                        self.main_app.resolution_combo['values'] = resolution_strings
                        # 默认选择最高分辨率
                        if resolution_strings:
                            self.main_app.resolution_combo.set(resolution_strings[0])
                    else:
                        # 使用默认分辨率列表
                        default_resolutions = ['1920x1080', '1280x720', '800x600', '640x480']
                        self.main_app.resolution_combo['values'] = default_resolutions
                        self.main_app.resolution_combo.set('1920x1080')
                else:
                    # 使用默认分辨率列表
                    default_resolutions = ['1920x1080', '1280x720', '800x600', '640x480']
                    self.main_app.resolution_combo['values'] = default_resolutions
                    self.main_app.resolution_combo.set('1920x1080')
            else:
                # 使用默认分辨率列表
                default_resolutions = ['1920x1080', '1280x720', '800x600', '640x480']
                self.main_app.resolution_combo['values'] = default_resolutions
                self.main_app.resolution_combo.set('1920x1080')
                
        except Exception as e:
            self.main_app.log(f"更新分辨率选项失败: {e}")
    
    def on_camera_changed(self, event=None):
        """摄像头选择变更处理"""
        try:
            # 更新对应的分辨率选项
            self.update_resolution_options()
            self.main_app.log(f"已切换到摄像头: {self.main_app.camera_id_var.get()}")
        except Exception as e:
            self.main_app.log(f"摄像头切换失败: {e}")
    
    def on_resolution_changed(self, event=None):
        """分辨率变更处理"""
        try:
            if self.main_app.camera_running and hasattr(self.main_app, 'camera') and self.main_app.camera:
                resolution_str = self.main_app.resolution_var.get()
                width, height = map(int, resolution_str.split('x'))
                
                self.main_app.log(f"正在设置分辨率为: {width}x{height}")
                
                # 设置摄像头分辨率
                self.main_app.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.main_app.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
                # 验证设置是否成功
                actual_width = int(self.main_app.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.main_app.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                if actual_width == width and actual_height == height:
                    self.main_app.log(f"分辨率设置成功: {actual_width}x{actual_height}")
                else:
                    self.main_app.log(f"分辨率设置部分成功: 期望{width}x{height}, 实际{actual_width}x{actual_height}")
                    
        except Exception as e:
            self.main_app.log(f"设置分辨率失败: {e}")
    
    def auto_focus(self):
        """自动对焦"""
        try:
            if self.main_app.camera_running and hasattr(self.main_app, 'camera') and self.main_app.camera:
                self.main_app.log("正在执行自动对焦...")
                
                # 尝试设置自动对焦
                # 注意：不是所有摄像头都支持程序化对焦控制
                success1 = self.main_app.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                
                # 某些摄像头需要触发对焦
                success2 = self.main_app.camera.set(cv2.CAP_PROP_FOCUS, 0)
                
                if success1 or success2:
                    self.main_app.log("自动对焦命令已发送")
                else:
                    self.main_app.log("此摄像头可能不支持程序化对焦控制")
                    
                # 等待对焦完成（读取几帧让对焦生效）
                for i in range(10):
                    ret, frame = self.main_app.camera.read()
                    if not ret:
                        break
                    time.sleep(0.1)
                
                self.main_app.log("对焦操作完成")
                
        except Exception as e:
            self.main_app.log(f"自动对焦失败: {e}")
    
    def on_zoom_changed(self, value):
        """变焦滑块变化处理"""
        try:
            zoom_level = float(value)
            self.main_app.zoom_label.config(text=f"{zoom_level:.1f}x")
            
            # 注意：这里实现的是数字变焦（软件裁剪），不是光学变焦
            # 光学变焦需要摄像头硬件支持，大多数网络摄像头不支持
            if hasattr(self.main_app, 'current_zoom_level'):
                self.main_app.current_zoom_level = zoom_level
            else:
                self.main_app.current_zoom_level = zoom_level
                
            # 如果摄像头正在运行，应用变焦
            if self.main_app.camera_running:
                self.apply_digital_zoom(zoom_level)
                
        except Exception as e:
            self.main_app.log(f"设置变焦失败: {e}")
    
    def apply_digital_zoom(self, zoom_level):
        """应用数字变焦（在process_face_detection方法中处理）"""
        # 这个方法设置变焦级别，实际的变焦处理在视频循环中进行
        pass
    
    def apply_digital_zoom_to_frame(self, frame, zoom_level):
        """对单帧图像应用数字变焦"""
        try:
            if zoom_level <= 1.0 or frame is None:
                return frame
            
            height, width = frame.shape[:2]
            
            # 计算裁剪区域（从中心裁剪）
            crop_width = int(width / zoom_level)
            crop_height = int(height / zoom_level)
            
            # 确保裁剪尺寸不会过小
            crop_width = max(crop_width, 50)
            crop_height = max(crop_height, 50)
            
            # 计算裁剪的起始位置（居中）
            start_x = (width - crop_width) // 2
            start_y = (height - crop_height) // 2
            
            # 裁剪图像
            cropped_frame = frame[start_y:start_y+crop_height, start_x:start_x+crop_width]
            
            # 将裁剪后的图像放大回原始尺寸
            zoomed_frame = cv2.resize(cropped_frame, (width, height), interpolation=cv2.INTER_LINEAR)
            
            return zoomed_frame
            
        except Exception as e:
            # 如果变焦失败，返回原始帧
            return frame
    
    def _is_valid_simple_face(self, gray_frame, x, y, w, h):
        """简单模式的面部区域验证"""
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
            if texture_variance < 50:  # 纹理过于单一，可能是误检
                return False
            
            return True
            
        except Exception:
            return False