# -*- coding: utf-8 -*-
import cv2
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import time
from tkinter import messagebox


class CameraControl:
    def __init__(self, main_app):
        self.main_app = main_app
        
        # 表情数据缓存和平均计算相关变量
        self.emotion_data_cache = []  # 存储表情数据的缓存
        self.last_emotion_update_time = 0  # 上次更新LLM情感状态的时间
        self.emotion_update_timer = None  # 定时器
        
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
        self.main_app.camera_start_btn = ttk.Button(control_buttons, text=self.main_app.get_text("start_camera"), command=self.toggle_camera_only)
        self.main_app.camera_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 面部识别启动/停止按钮  
        self.main_app.face_detection_btn = ttk.Button(control_buttons, text=self.main_app.get_text("start_face_detection"), 
                                           command=self.toggle_face_detection, state="disabled")
        self.main_app.face_detection_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 截图按钮
        self.main_app.capture_btn = ttk.Button(control_buttons, text=self.main_app.get_text("screenshot"), command=self.capture_screenshot, 
                                     state="disabled")
        self.main_app.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 保存表情数据按钮
        self.main_app.save_expression_btn = ttk.Button(control_buttons, text=self.main_app.get_text("save_expression"), command=self.save_expression_data,
                                            state="disabled")
        self.main_app.save_expression_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 表情更新间隔控制
        interval_frame = ttk.Frame(self.main_app.camera_control_frame)
        interval_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 表情更新间隔标签和滑块
        ttk.Label(interval_frame, text="表情更新间隔:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.main_app.emotion_update_interval_var = tk.DoubleVar(value=3.0)  # 默认3秒
        self.main_app.emotion_interval_scale = ttk.Scale(interval_frame, from_=1.0, to=10.0,
                                                variable=self.main_app.emotion_update_interval_var,
                                                orient='horizontal',
                                                command=self._on_emotion_interval_changed)
        self.main_app.emotion_interval_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.main_app.emotion_interval_label = ttk.Label(interval_frame, text="3.0s")
        self.main_app.emotion_interval_label.pack(side=tk.LEFT)
        
        # 摄像头显示区域
        self.main_app.camera_display_frame = ttk.LabelFrame(parent_frame, text=self.main_app.get_text("camera_feed"), padding="5")
        self.main_app.camera_display_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
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
        self.main_app.expression_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
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
            
            # 设置分辨率
            self.main_app.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.main_app.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.main_app.camera_running = True
            self.main_app.camera_start_btn.config(text="停止摄像头")
            self.main_app.face_detection_btn.config(state="normal")
            self.main_app.capture_btn.config(state="normal")
            self.main_app.save_expression_btn.config(state="normal")
            
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
            self.emotion_data_cache.clear()
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
            
            self.main_app.log("面部识别已停止")
            
        except Exception as e:
            self.main_app.log(f"停止面部识别失败: {e}")
    
    def update_camera_display(self):
        """更新摄像头显示"""
        if not self.main_app.camera_running or not hasattr(self.main_app, 'camera') or not self.main_app.camera:
            return
        
        try:
            ret, frame = self.main_app.camera.read()
            if ret and frame is not None:
                # 处理面部识别
                if self.main_app.face_detection_running:
                    expressions = self.process_face_detection(frame)
                    if expressions:
                        self._update_expression_display(expressions)
                
                # 显示视频帧
                display_frame = cv2.resize(frame, (640, 480))
                frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(img)
                self.main_app.video_label.config(image=photo, text='')
                self.main_app.video_label.image = photo  # 保持引用
                
                # 继续更新
                self.main_app.root.after(30, self.update_camera_display)
            else:
                self.main_app.log("无法读取摄像头画面")
                self.stop_camera_only()
                
        except Exception as e:
            self.main_app.log(f"摄像头显示更新失败: {e}")
            self.stop_camera_only()
    
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
                # 使用简单的OpenCV检测
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(100, 100))
                
                # 绘制面部框
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    cv2.putText(frame, "Face Detected", (x, y-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Simple模式：只显示检测到的面部数量，不生成假数据
                if len(faces) > 0:
                    # 保持默认的表情值，不生成模拟数据
                    pass
            
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
                        
                        # 记录主导情感
                        dominant_emotion = max(avg_emotions.items(), key=lambda x: x[1])
                        if dominant_emotion[1] > 0.3:  # 只有当情感强度超过阈值时才记录
                            self.main_app.log(f"[情感更新] 主导情感: {dominant_emotion[0]} (强度: {dominant_emotion[1]:.2f})")
                        
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
        """简单的视频显示循环（不包含面部识别）"""
        while self.main_app.camera_running and self.main_app.camera and self.main_app.camera.isOpened():
            try:
                ret, frame = self.main_app.camera.read()
                if ret and frame is not None:
                    # 调整图像大小
                    display_frame = cv2.resize(frame, (640, 480))
                    
                    # 如果启用了面部识别，进行处理
                    if self.main_app.face_detection_running:
                        display_frame, expressions = self.process_face_detection(display_frame)
                        # 更新表情显示
                        self.main_app.root.after(0, lambda: self._update_expression_display(expressions))
                    
                    # 转换为显示格式
                    frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(img)
                    
                    # 更新显示
                    self.main_app.current_frame = frame
                    self.main_app.root.after(0, lambda p=photo: self.update_video_display(p))
                    
                time.sleep(0.03)  # 约33fps
                
            except Exception as e:
                if self.main_app.camera_running:
                    self.main_app.log(f"视频循环错误: {e}")
                time.sleep(0.1)
    
    def update_video_display(self, photo):
        """更新视频显示（在主线程中调用）"""
        try:
            if self.main_app.camera_running and photo:
                self.main_app.video_label.config(image=photo, text="")
                self.main_app.video_label.image = photo  # 保持引用防止垃圾回收
            else:
                self.main_app.log("显示更新失败: 摄像头未运行或照片为空")
        except Exception as e:
            self.main_app.log(f"更新显示错误: {e}")
            print(f"更新显示错误: {e}")
    
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