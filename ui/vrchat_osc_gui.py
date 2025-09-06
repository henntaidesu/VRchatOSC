#!/usr/bin/env python3
"""
VRChat OSC Client GUI
基于Tkinter的图形用户界面
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import sys
import os
import numpy as np
import soundfile as sf
import cv2
from PIL import Image, ImageTk
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vrchat_controller import VRChatController
from src.config_manager import config_manager
from .settings_window import SettingsWindow
from src.face.simple_face_detector import SimpleFaceCamera
from src.face.gpu_emotion_detector import GPUFaceCamera
from .languages.language_dict import get_text, get_language_display_names, DISPLAY_TO_LANGUAGE_MAP
from src.VOICEVOX.voicevox_tts import VOICEVOXClient, get_voicevox_client
from src.llm.voice_llm_handler import VoiceLLMHandler, VoiceLLMResponse
from src.avatar import AvatarController
from src.avatar.single_ai_vrc_manager import SingleAIVRCManager


class VRChatOSCGUI:
    """VRChat OSC GUI界面类"""
    
    def __init__(self):
        # 加载配置
        self.config = config_manager
        
        self.root = tk.Tk()
        self.root.title("VRChat OSC 通信工具")
        
        # 设置窗口大小以适应新的左中右三列布局 (400px + 600px + 600px + 间距和padding)
        window_width = 1650  # 400 + 600 + 600 + 间距padding约50px
        window_height = self.config.window_height
        window_size = f"{window_width}x{window_height}"
        self.root.geometry(window_size)
        self.root.resizable(True, True)
        
        # OSC客户端
        self.client = None
        self.is_connected = False
        self.is_listening = False
        
        # 从配置文件加载设置变量
        self.host_var = tk.StringVar(value=self.config.osc_host)
        self.send_port_var = tk.StringVar(value=str(self.config.osc_send_port))
        self.receive_port_var = tk.StringVar(value=str(self.config.osc_receive_port))
        self.language_var = tk.StringVar(value=self.config.voice_language)
        self.device_var = tk.StringVar(value=self.config.voice_device)
        self.ui_language = tk.StringVar(value=self.config.ui_language)  # 界面语言：zh=中文, ja=日语
        
        # 语音文件相关变量
        self.uploaded_audio_data = None
        self.uploaded_audio_sample_rate = None
        self.uploaded_filename = None
        
        # 摄像头相关变量
        self.camera = None
        self.camera_running = False
        self.face_detection_running = False
        self.current_frame = None
        self.camera_thread = None
        
        # Avatar控制器 - 统一管理虚拟人物控制
        self.avatar_controller = AvatarController(character_data_file="data/vrc_characters.json")
        
        # 单AI角色VRC管理器
        self.single_ai_manager = None  # 延迟初始化，等待VOICEVOX连接
        
        # 为了兼容性保留的变量（逐步迁移到avatar_controller）
        self.character_window = None  # 角色管理窗口引用
        self.camera_id_mapping = {}  # 摄像头显示名称到ID的映射
        self.emotion_model_type = 'ResEmoteNet'  # 默认使用ResEmoteNet情感识别模型
        
        # VOICEVOX相关变量
        self.voicevox_client = None
        self.voicevox_connected = False
        
        # LLM相关变量
        self.llm_handler = None
        self.llm_enabled = True
        
        
        self.setup_ui()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def get_text(self, key):
        """获取当前语言的文本"""
        return get_text(self.ui_language.get(), key, key)
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)  # 左侧控制面板，固定宽度
        main_frame.columnconfigure(1, weight=0)  # 中间VOICEVOX控制区域，固定宽度
        main_frame.columnconfigure(2, weight=0)  # 右侧摄像头区域，固定宽度
        
        # 配置主框架行权重
        main_frame.rowconfigure(0, weight=1)  # 主内容区域可扩展
        
        # 创建左中右三个主要区域
        left_frame = ttk.Frame(main_frame, width=400)  # 左侧VOICEVOX专用区域
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 5))
        left_frame.grid_propagate(False)  # 防止子组件改变frame大小
        
        # 中间区域 - 原左侧控制面板内容
        center_frame = ttk.Frame(main_frame, width=600)  # 中间控制面板区域
        center_frame.grid(row=0, column=1, sticky=(tk.W, tk.N, tk.S), padx=(5, 5))
        center_frame.grid_propagate(False)  # 防止子组件改变frame大小
        
        right_frame = ttk.Frame(main_frame, width=600)  # 右侧摄像头区域
        right_frame.grid(row=0, column=2, sticky=(tk.W, tk.N, tk.S), padx=(5, 0))
        right_frame.grid_propagate(False)  # 防止子组件改变frame大小
        
        # 配置三个区域的权重
        left_frame.columnconfigure(0, weight=1)
        center_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)  # 摄像头显示区域可扩展
        
        # 连接设置框架 - 放在中间区域
        self.connection_frame = ttk.LabelFrame(center_frame, text=self.get_text("connection_settings"), padding="5")
        self.connection_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 主机地址
        ttk.Label(self.connection_frame, text=self.get_text("host_address")).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(self.connection_frame, textvariable=self.host_var, width=15).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 发送端口
        ttk.Label(self.connection_frame, text=self.get_text("send_port")).grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        ttk.Entry(self.connection_frame, textvariable=self.send_port_var, width=8).grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 接收端口
        ttk.Label(self.connection_frame, text=self.get_text("receive_port")).grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        ttk.Entry(self.connection_frame, textvariable=self.receive_port_var, width=8).grid(row=0, column=5, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 界面语言选择
        ttk.Label(self.connection_frame, text=self.get_text("ui_language")).grid(row=0, column=6, sticky=tk.W, padx=(10, 5))
        
        # 创建语言选择变量
        self.ui_language_display = tk.StringVar()
        
        # 获取可用的语言显示名称
        display_names = get_language_display_names()
        
        # 设置当前语言的显示
        current_lang = self.ui_language.get()
        for display_name, lang_code in DISPLAY_TO_LANGUAGE_MAP.items():
            if lang_code == current_lang:
                self.ui_language_display.set(display_name)
                break
        
        self.ui_language_combo = ttk.Combobox(self.connection_frame, textvariable=self.ui_language_display,
                                            values=display_names, width=8, state="readonly")
        self.ui_language_combo.grid(row=0, column=7, padx=(0, 10))
        self.ui_language_combo.bind("<<ComboboxSelected>>", self.on_language_changed)
        
        # 连接按钮
        self.connect_btn = ttk.Button(self.connection_frame, text=self.get_text("connect"), command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=8, padx=(10, 0))
        
        # 第二行：高级设置按钮
        self.advanced_settings_btn = ttk.Button(self.connection_frame, text=self.get_text("advanced_settings"), command=self.open_settings_window)
        self.advanced_settings_btn.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)
        
        # 配置连接框架的列权重
        self.connection_frame.columnconfigure(1, weight=1)
        self.connection_frame.columnconfigure(3, weight=1)
        self.connection_frame.columnconfigure(5, weight=1)
        
        # 消息发送框架 - 放在中间区域
        self.message_frame = ttk.LabelFrame(center_frame, text=self.get_text("message_send"), padding="5")
        self.message_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.message_frame.columnconfigure(0, weight=1)
        
        # 文字消息输入
        text_frame = ttk.Frame(self.message_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        text_frame.columnconfigure(0, weight=1)
        
        self.message_entry = ttk.Entry(text_frame, font=("", 10))
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.message_entry.bind("<Return>", lambda e: self.send_text_message())
        
        self.send_text_btn = ttk.Button(text_frame, text=self.get_text("send_text"), command=self.send_text_message)
        self.send_text_btn.grid(row=0, column=1)
        
        # 语音设置框架
        voice_frame = ttk.Frame(self.message_frame)
        voice_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # 第一行：语言选择、设备选择、开始监听、上传语音
        self.recognition_language_label = ttk.Label(voice_frame, text=self.get_text("recognition_language"))
        self.recognition_language_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.language_combo = ttk.Combobox(voice_frame, textvariable=self.language_var, 
                                    values=["zh-CN", "ja-JP"], 
                                    width=10, state="readonly")
        self.language_combo.grid(row=0, column=1, padx=(0, 10))
        
        self.compute_device_label = ttk.Label(voice_frame, text=self.get_text("compute_device"))
        self.compute_device_label.grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
        self.device_combo = ttk.Combobox(voice_frame, textvariable=self.device_var,
                                   values=["auto", "cuda", "cpu"],
                                   width=10, state="readonly")
        self.device_combo.grid(row=0, column=3, padx=(0, 10))
        
        # 开始监听按钮
        self.listen_btn = ttk.Button(voice_frame, text=self.get_text("start_listening"), command=self.toggle_voice_listening)
        self.listen_btn.grid(row=0, column=4, padx=(10, 5))
        
        # 语音文件上传按钮
        self.upload_voice_btn = ttk.Button(voice_frame, text=self.get_text("upload_voice"), command=self.upload_voice_file)
        self.upload_voice_btn.grid(row=0, column=5, padx=(0, 5))
        
        
        # 第二行：调试和模式控制
        debug_frame = ttk.Frame(self.message_frame)
        debug_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # 调试模式开关
        self.debug_var = tk.BooleanVar(value=self.config.osc_debug_mode)
        self.debug_check = ttk.Checkbutton(debug_frame, text=self.get_text("debug"), 
                                     variable=self.debug_var, command=self.toggle_debug_mode)
        self.debug_check.grid(row=0, column=0, padx=(0, 10))
        
        # 强制备用模式开关
        self.fallback_var = tk.BooleanVar(value=self.config.use_fallback_mode)
        self.fallback_check = ttk.Checkbutton(debug_frame, text=self.get_text("force_fallback_mode"), 
                                        variable=self.fallback_var, command=self.toggle_fallback_mode)
        self.fallback_check.grid(row=0, column=1, padx=(0, 10))
        
        # 禁用备用模式开关
        self.disable_fallback_var = tk.BooleanVar(value=self.config.disable_fallback_mode)
        self.disable_fallback_check = ttk.Checkbutton(debug_frame, text=self.get_text("disable_fallback_mode"), 
                                                 variable=self.disable_fallback_var, command=self.toggle_disable_fallback_mode)
        self.disable_fallback_check.grid(row=0, column=2, padx=(0, 10))
        
        # 高级设置按钮
        self.settings_btn = ttk.Button(debug_frame, text=self.get_text("settings"), command=self.open_settings)
        self.settings_btn.grid(row=0, column=3, padx=(0, 5))
        
        # 状态显示按钮
        self.status_btn = ttk.Button(debug_frame, text=self.get_text("show_status"), command=self.show_debug_status)
        self.status_btn.grid(row=0, column=4, padx=(0, 5))
        
        # 摄像头按钮 - 现在用于在主界面显示/隐藏摄像头区域
        self.camera_btn = ttk.Button(debug_frame, text=self.get_text("camera_window"), command=self.open_camera_window)
        self.camera_btn.grid(row=0, column=5, padx=(0, 5))
        
        # 语音阈值设置
        threshold_frame = ttk.Frame(self.message_frame)
        threshold_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.voice_threshold_label = ttk.Label(threshold_frame, text=self.get_text("voice_threshold"))
        self.voice_threshold_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.threshold_var = tk.DoubleVar(value=self.config.voice_threshold)
        self.threshold_scale = ttk.Scale(threshold_frame, from_=0.005, to=0.05, 
                                   variable=self.threshold_var, orient='horizontal',
                                   command=self.update_voice_threshold)
        self.threshold_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.threshold_label = ttk.Label(threshold_frame, text=f"{self.config.voice_threshold:.3f}")
        self.threshold_label.grid(row=0, column=2, padx=(0, 15))
        
        # 断句检测设置
        # TODO: Add sentence pause threshold to language files
        ttk.Label(threshold_frame, text="断句间隔:").grid(row=0, column=3, sticky=tk.W, padx=(0, 5))
        self.pause_var = tk.DoubleVar(value=self.config.sentence_pause_threshold)
        self.pause_scale = ttk.Scale(threshold_frame, from_=0.2, to=1.0, 
                               variable=self.pause_var, orient='horizontal',
                               command=self.update_pause_threshold)
        self.pause_scale.grid(row=0, column=4, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.pause_label = ttk.Label(threshold_frame, text=f"{self.config.sentence_pause_threshold:.1f}s")
        self.pause_label.grid(row=0, column=5)
        
        threshold_frame.columnconfigure(1, weight=1)
        threshold_frame.columnconfigure(4, weight=1)
        
        
        # 参数设置框架 - 放在中间区域
        self.param_frame = ttk.LabelFrame(center_frame, text=self.get_text("avatar_params"), padding="5")
        self.param_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.param_frame.columnconfigure(0, weight=1)
        self.param_frame.columnconfigure(2, weight=1)
        
        # 参数名输入
        self.param_name_label = ttk.Label(self.param_frame, text=self.get_text("param_name"))
        self.param_name_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.param_name_entry = ttk.Entry(self.param_frame, width=20)
        self.param_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 参数值输入
        self.param_value_label = ttk.Label(self.param_frame, text=self.get_text("param_value"))
        self.param_value_label.grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.param_value_entry = ttk.Entry(self.param_frame, width=15)
        self.param_value_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 10))
        self.param_value_entry.bind("<Return>", lambda e: self.send_parameter())
        
        # 发送参数按钮
        self.send_param_btn = ttk.Button(self.param_frame, text=self.get_text("send_param"), command=self.send_parameter)
        self.send_param_btn.grid(row=0, column=4)
        
        # 日志显示框架 - 放在中间区域
        self.log_frame = ttk.LabelFrame(center_frame, text=self.get_text("log"), padding="5")
        self.log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        
        # 配置左侧框架行权重
        left_frame.rowconfigure(3, weight=1)
        
        # 日志文本框 - 减小高度为语音识别框让出空间
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=10, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清空日志按钮
        self.clear_log_btn = ttk.Button(self.log_frame, text=self.get_text("clear_log"), command=self.clear_log)
        self.clear_log_btn.grid(row=1, column=0, pady=(5, 0))
        
        # 语音识别输出框架 - 放在中间区域
        self.speech_frame = ttk.LabelFrame(center_frame, text=self.get_text("speech_output"), padding="5")
        self.speech_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.speech_frame.columnconfigure(0, weight=1)
        self.speech_frame.rowconfigure(0, weight=1)
        
        # 配置中间框架行权重 - 为语音识别框分配空间
        center_frame.rowconfigure(3, weight=2)  # 日志框权重
        center_frame.rowconfigure(4, weight=3)  # 语音识别框更大权重
        
        # 语音识别文本框
        self.speech_text = scrolledtext.ScrolledText(self.speech_frame, height=8, font=("", 12), wrap=tk.WORD)
        self.speech_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置语音识别输出的颜色标签
        self.speech_text.tag_config(self.get_text("continuous_listening"), foreground="#2196F3")  # 蓝色
        self.speech_text.tag_config(self.get_text("voice_recording"), foreground="#4CAF50")  # 绿色  
        self.speech_text.tag_config(self.get_text("voice_sending"), foreground="#FF9800")  # 橙色
        self.speech_text.tag_config("AI回复", foreground="#9C27B0")    # 紫色
        self.speech_text.tag_config(self.get_text("timestamp"), foreground="#666666")   # 灰色
        
        # 语音识别框按钮行
        speech_button_frame = ttk.Frame(self.speech_frame)
        speech_button_frame.grid(row=1, column=0, pady=(5, 0), sticky=(tk.W, tk.E))
        
        # 清空语音识别按钮
        self.clear_speech_btn = ttk.Button(speech_button_frame, text=self.get_text("clear_speech"), command=self.clear_speech_output)
        self.clear_speech_btn.grid(row=0, column=0, padx=(0, 5))
        
        # 保存语音记录按钮
        self.save_speech_btn = ttk.Button(speech_button_frame, text=self.get_text("save_speech"), command=self.save_speech_output)
        self.save_speech_btn.grid(row=0, column=1, padx=(5, 0))
        
        # 左侧VOICEVOX专用区域
        self.setup_voicevox_area(left_frame)
        
        # 右侧摄像头区域
        self.setup_camera_area(right_frame)
        
        # 状态栏 - 跨越整个底部
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, text=self.get_text("disconnected"), foreground="red")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 进度条（默认隐藏）
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        self.progress_bar.grid_remove()  # 初始隐藏
        
        # 初始状态设置
        self.update_ui_state(False)
        
        # 初始化VOICEVOX
        self.init_voicevox()
        
        # 初始化LLM处理器
        self.init_llm_handler()
    
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
                            self.log(f"检测到摄像头: {camera_info}")
                        else:
                            self.log(f"跳过重复摄像头 ID {i} (相同分辨率: {signature})")
                
                cap.release()
                    
            except Exception as e:
                # 忽略检测失败的摄像头
                continue
        
        return available_cameras
    
    def refresh_camera_list(self):
        """刷新摄像头列表"""
        try:
            self.log("正在检测可用摄像头...")
            
            # 显示检测状态
            self.camera_combo['values'] = ['正在检测...']
            self.camera_combo.set('正在检测...')
            self.root.update()
            
            # 在后台线程中检测摄像头
            def detect_cameras():
                try:
                    available_cameras = self.detect_available_cameras()
                    
                    # 在主线程中更新UI
                    self.root.after(0, lambda: self.update_camera_list(available_cameras))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"检测摄像头失败: {e}"))
            
            # 启动检测线程
            import threading
            thread = threading.Thread(target=detect_cameras, daemon=True)
            thread.start()
            
        except Exception as e:
            self.log(f"刷新摄像头列表失败: {e}")
            self.camera_combo['values'] = ['检测失败']
            self.camera_combo.set('检测失败')
    
    def update_camera_list(self, available_cameras):
        """更新摄像头列表（在主线程中调用）"""
        try:
            if available_cameras:
                # 创建显示列表
                camera_values = [info for _, info in available_cameras]
                self.camera_combo['values'] = camera_values
                
                # 保存ID映射
                self.camera_id_mapping = {info: cam_id for cam_id, info in available_cameras}
                
                # 默认选择第一个摄像头
                self.camera_combo.set(camera_values[0])
                self.log(f"检测到 {len(available_cameras)} 个可用摄像头")
                
            else:
                no_cameras_text = self.get_text("no_cameras_available")
                self.camera_combo['values'] = [no_cameras_text]
                self.camera_combo.set(no_cameras_text)
                self.camera_id_mapping = {}
                self.log(self.get_text("no_cameras_available"))
                
        except Exception as e:
            self.log(f"更新摄像头列表失败: {e}")
            self.camera_combo['values'] = ['更新失败']
            self.camera_combo.set('更新失败')
    
    def on_model_changed(self, event=None):
        """模型选择变更处理"""
        self.emotion_model_type = self.model_var.get()
        self.log(f"情感识别模型已切换为: {self.emotion_model_type}")
        
        # 释放现有的GPU检测器
        if hasattr(self, 'gpu_detector') and self.gpu_detector is not None:
            try:
                self.gpu_detector.release()
                self.gpu_detector = None
                self.log("已释放旧的GPU检测器")
            except Exception as e:
                self.log(f"释放旧GPU检测器时出错: {e}")
        
        # 如果切换到GPU模型，强制重新初始化检测器
        if self.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
            try:
                # 总是创建新的检测器以确保模型切换生效
                from src.face.gpu_emotion_detector import GPUEmotionDetector
                self.gpu_detector = GPUEmotionDetector(model_type=self.emotion_model_type, device='auto')
                self.log(f"成功初始化GPU情感检测器: {self.emotion_model_type}")
            except Exception as e:
                import traceback
                self.log(f"GPU检测器初始化失败 ({self.emotion_model_type}): {e}")
                self.log(f"详细错误: {traceback.format_exc()}")
                self.gpu_detector = None
        
        # 如果面部识别正在运行，需要重启以应用新模型
        if self.face_detection_running:
            self.log("检测到模型变更，正在重启面部识别以应用新模型...")
            self.stop_face_detection()
            # 延迟一点再启动
            self.root.after(1000, self.start_face_detection)
    
    def setup_voicevox_area(self, parent_frame):
        """设置VOICEVOX控制区域"""
        # VOICEVOX控制面板 - 占用整个左侧区域
        self.voicevox_control_frame = ttk.LabelFrame(parent_frame, text=self.get_text("character"), padding="5")
        self.voicevox_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        self.voicevox_control_frame.columnconfigure(0, weight=1)
        self.voicevox_control_frame.rowconfigure(2, weight=1)  # 为未来扩展留出空间
        
        # 第一行：期数和角色选择（合并到一行）
        character_frame = ttk.Frame(self.voicevox_control_frame)
        character_frame.pack(fill=tk.X, pady=(0, 5))
        
        # VOICEVOX期数选择
        ttk.Label(character_frame, text="期数:", width=6).pack(side=tk.LEFT, padx=(0, 5))
        self.voicevox_period_var = tk.StringVar(value="1期")
        self.voicevox_period_combo = ttk.Combobox(character_frame, textvariable=self.voicevox_period_var,
                                                values=["1期", "2期", "3期"],
                                                width=8, state="readonly")
        self.voicevox_period_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.voicevox_period_combo.bind("<<ComboboxSelected>>", self.on_voicevox_period_changed)
        
        # VOICEVOX角色选择
        ttk.Label(character_frame, text="角色:", width=6).pack(side=tk.LEFT, padx=(0, 5))
        self.voicevox_character_var = tk.StringVar(value="ずんだもん - ノーマル")
        self.voicevox_character_combo = ttk.Combobox(character_frame, textvariable=self.voicevox_character_var,
                                                   width=20, state="readonly")
        self.voicevox_character_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.voicevox_character_combo.bind("<<ComboboxSelected>>", self.on_voicevox_character_changed)
        
        
        # VOICEVOX连接状态
        self.voicevox_status_label = ttk.Label(character_frame, text=self.get_text("disconnected"), foreground="red")
        self.voicevox_status_label.pack(side=tk.RIGHT)
        
        # 第三行：控制按钮
        control_frame = ttk.Frame(self.voicevox_control_frame)
        control_frame.pack(fill=tk.X, pady=(5, 0))
        
        # VOICEVOX测试按钮
        self.voicevox_test_btn = ttk.Button(control_frame, text=self.get_text("voice_test"), command=self.test_voicevox)
        self.voicevox_test_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # VOICEVOX启用开关
        self.voicevox_enabled_var = tk.BooleanVar(value=True)
        self.voicevox_enabled_check = ttk.Checkbutton(control_frame, text="启用VOICEVOX", 
                                                    variable=self.voicevox_enabled_var)
        self.voicevox_enabled_check.pack(side=tk.LEFT, padx=(10, 0))
        
        # LLM启用开关
        self.llm_enabled_var = tk.BooleanVar(value=True)
        self.llm_enabled_check = ttk.Checkbutton(control_frame, text="启用AI对话", 
                                               variable=self.llm_enabled_var, 
                                               command=self.toggle_llm_enabled)
        self.llm_enabled_check.pack(side=tk.LEFT, padx=(10, 0))
        
        # 第四行：语音参数控制
        params_frame = ttk.LabelFrame(self.voicevox_control_frame, text=self.get_text("voice_params"), padding="5")
        params_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 语速控制
        speed_frame = ttk.Frame(params_frame)
        speed_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(speed_frame, text="语速:", width=8).pack(side=tk.LEFT)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = ttk.Scale(speed_frame, from_=0.5, to=2.0, variable=self.speed_var,
                                   orient=tk.HORIZONTAL, command=self.on_speed_changed)
        self.speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.speed_label = ttk.Label(speed_frame, text="1.00", width=5)
        self.speed_label.pack(side=tk.RIGHT)
        
        # 音高控制  
        pitch_frame = ttk.Frame(params_frame)
        pitch_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(pitch_frame, text="音高:", width=8).pack(side=tk.LEFT)
        self.pitch_var = tk.DoubleVar(value=0.0)
        self.pitch_scale = ttk.Scale(pitch_frame, from_=-0.15, to=0.15, variable=self.pitch_var,
                                   orient=tk.HORIZONTAL, command=self.on_pitch_changed)
        self.pitch_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.pitch_label = ttk.Label(pitch_frame, text="0.00", width=5)
        self.pitch_label.pack(side=tk.RIGHT)
        
        # 抑扬顿挫控制
        intonation_frame = ttk.Frame(params_frame)
        intonation_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(intonation_frame, text="抑扬:", width=8).pack(side=tk.LEFT)
        self.intonation_var = tk.DoubleVar(value=1.0)
        self.intonation_scale = ttk.Scale(intonation_frame, from_=0.0, to=2.0, variable=self.intonation_var,
                                        orient=tk.HORIZONTAL, command=self.on_intonation_changed)
        self.intonation_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.intonation_label = ttk.Label(intonation_frame, text="1.00", width=5)
        self.intonation_label.pack(side=tk.RIGHT)
        
        # 音量控制
        volume_frame = ttk.Frame(params_frame)
        volume_frame.pack(fill=tk.X, pady=(0, 0))
        ttk.Label(volume_frame, text="音量:", width=8).pack(side=tk.LEFT)
        self.volume_var = tk.DoubleVar(value=1.0)
        self.volume_scale = ttk.Scale(volume_frame, from_=0.0, to=2.0, variable=self.volume_var,
                                    orient=tk.HORIZONTAL, command=self.on_volume_changed)
        self.volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.volume_label = ttk.Label(volume_frame, text="1.00", width=5)
        self.volume_label.pack(side=tk.RIGHT)
        
        # 角色管理区域 - 直接在左侧VOICEVOX区域下方
        self.setup_character_management_area(self.voicevox_control_frame)

    def setup_character_management_area(self, parent_frame):
        """设置角色管理区域"""
        # 使用Notebook创建选项卡
        character_notebook = ttk.Notebook(parent_frame)
        character_notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # AI角色管理选项卡
        ai_frame = ttk.Frame(character_notebook)
        character_notebook.add(ai_frame, text="AI角色")
        
        # 位置标记选项卡
        position_frame = ttk.Frame(character_notebook)
        character_notebook.add(position_frame, text="位置标记")
        
        # 设置AI角色管理界面
        self.setup_ai_character_interface(ai_frame)
        
        # 设置位置标记界面（原来的功能）
        self.setup_position_marker_interface(position_frame)
    
    def setup_ai_character_interface(self, parent_frame):
        """设置AI角色管理界面"""
        # 当前激活的AI角色显示
        status_frame = ttk.LabelFrame(parent_frame, text="AI角色状态", padding="5")
        status_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.active_ai_label = ttk.Label(status_frame, text="当前激活: 无", foreground="blue")
        self.active_ai_label.pack(side=tk.LEFT)
        
        # AI角色控制
        control_frame = ttk.LabelFrame(parent_frame, text="AI角色控制", padding="5")
        control_frame.pack(fill=tk.X, pady=(5, 5))
        
        # 激活/停用按钮
        self.activate_ai_btn = ttk.Button(control_frame, text="激活", command=self.toggle_ai_character, width=8)
        self.activate_ai_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 创建新AI角色区域
        create_frame = ttk.LabelFrame(parent_frame, text="创建AI角色", padding="5")
        create_frame.pack(fill=tk.X, pady=(5, 5))
        create_frame.columnconfigure(1, weight=1)
        
        # AI角色名称输入
        ttk.Label(create_frame, text="名称:", width=6).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.new_ai_name_entry = ttk.Entry(create_frame, width=12)
        self.new_ai_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # 人格选择
        ttk.Label(create_frame, text="人格:", width=6).grid(row=0, column=2, sticky=tk.W, padx=(5, 5))
        self.ai_personality_var = tk.StringVar(value="friendly")
        self.ai_personality_combo = ttk.Combobox(create_frame, textvariable=self.ai_personality_var,
                                               values=["friendly", "shy", "energetic", "calm", "playful"],
                                               width=10, state="readonly")
        self.ai_personality_combo.grid(row=0, column=3, padx=(0, 5))
        
        # 创建按钮
        self.create_ai_btn = ttk.Button(create_frame, text="创建", command=self.create_ai_character, width=8)
        self.create_ai_btn.grid(row=0, column=4)
        
        # VRC OSC连接控制区域
        vrc_control_frame = ttk.LabelFrame(parent_frame, text="VRC OSC连接", padding="5")
        vrc_control_frame.pack(fill=tk.X, pady=(5, 5))
        
        # OSC连接状态和控制
        osc_status_row = ttk.Frame(vrc_control_frame)
        osc_status_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(osc_status_row, text="OSC状态:", width=8).pack(side=tk.LEFT)
        self.ai_osc_status_label = ttk.Label(osc_status_row, text="未连接", foreground="red")
        self.ai_osc_status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.ai_osc_connect_btn = ttk.Button(osc_status_row, text="连接VRC", command=self.toggle_ai_osc_connection, width=8)
        self.ai_osc_connect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # VRC消息发送区域
        vrc_message_frame = ttk.LabelFrame(parent_frame, text="VRC消息控制", padding="5")
        vrc_message_frame.pack(fill=tk.X, pady=(5, 5))
        
        # 文本消息发送
        text_message_row = ttk.Frame(vrc_message_frame)
        text_message_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(text_message_row, text="发送文本:", width=8).pack(side=tk.LEFT)
        self.ai_text_entry = ttk.Entry(text_message_row)
        self.ai_text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.ai_text_entry.bind("<Return>", lambda e: self.ai_send_text_message())
        
        self.ai_send_text_btn = ttk.Button(text_message_row, text="发送", command=self.ai_send_text_message, width=6)
        self.ai_send_text_btn.pack(side=tk.LEFT)
        
        # 语音文件上传
        voice_upload_row = ttk.Frame(vrc_message_frame)
        voice_upload_row.pack(fill=tk.X, pady=(0, 5))
        
        self.ai_upload_voice_btn = ttk.Button(voice_upload_row, text="上传语音文件", command=self.ai_upload_voice_file, width=12)
        self.ai_upload_voice_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.ai_voice_file_label = ttk.Label(voice_upload_row, text="未选择文件", foreground="gray")
        self.ai_voice_file_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # VOICEVOX语音控制
        voicevox_control_row = ttk.Frame(vrc_message_frame)
        voicevox_control_row.pack(fill=tk.X, pady=(5, 0))
        
        self.ai_voicevox_generate_btn = ttk.Button(voicevox_control_row, text="生成并发送语音", command=self.ai_generate_and_send_voice, width=15)
        self.ai_voicevox_generate_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(voicevox_control_row, text="内容:", width=5).pack(side=tk.LEFT)
        self.ai_voicevox_text_entry = ttk.Entry(voicevox_control_row)
        self.ai_voicevox_text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.ai_voicevox_text_entry.bind("<Return>", lambda e: self.ai_generate_and_send_voice())
        
        # AI行为控制区域
        behavior_frame = ttk.LabelFrame(parent_frame, text="AI行为控制", padding="5")
        behavior_frame.pack(fill=tk.X, pady=(5, 5))
        
        # 控制按钮行
        button_row = ttk.Frame(behavior_frame)
        button_row.pack(fill=tk.X)
        
        self.ai_greet_btn = ttk.Button(button_row, text="AI打招呼", command=self.ai_greet, width=10)
        self.ai_greet_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.ai_speak_btn = ttk.Button(button_row, text="AI说话", command=self.ai_speak_custom, width=10)
        self.ai_speak_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 自定义说话文本输入
        speak_frame = ttk.Frame(behavior_frame)
        speak_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(speak_frame, text="AI说话内容:", width=10).pack(side=tk.LEFT)
        self.ai_speak_entry = ttk.Entry(speak_frame)
        self.ai_speak_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.ai_speak_entry.bind("<Return>", lambda e: self.ai_speak_custom())
        
        # 语音队列状态显示
        queue_frame = ttk.LabelFrame(parent_frame, text="语音队列状态", padding="5")
        queue_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.ai_voice_queue_text = tk.Text(queue_frame, height=4, width=40, state='disabled', wrap=tk.WORD)
        queue_scrollbar = ttk.Scrollbar(queue_frame, orient="vertical", command=self.ai_voice_queue_text.yview)
        self.ai_voice_queue_text.configure(yscrollcommand=queue_scrollbar.set)
        
        self.ai_voice_queue_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        queue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 初始化AI角色界面状态
        self.update_ai_character_status()
    
    def setup_position_marker_interface(self, parent_frame):
        """设置位置标记界面（原角色管理功能）"""
        # 当前位置显示行
        pos_frame = ttk.Frame(parent_frame)
        pos_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(pos_frame, text=self.get_text("character_position") + ":", width=8).pack(side=tk.LEFT)
        self.current_pos_label = ttk.Label(pos_frame, text="(0.00, 0.00, 0.00)", foreground="blue")
        self.current_pos_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # 位置标记添加区域
        add_frame = ttk.LabelFrame(parent_frame, text="添加位置标记", padding="3")
        add_frame.pack(fill=tk.X, pady=(5, 5))
        add_frame.columnconfigure(1, weight=1)
        
        # 标记名称输入
        ttk.Label(add_frame, text="标记名称:", width=8).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.character_name_entry = ttk.Entry(add_frame, width=12)
        self.character_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # 使用当前位置按钮
        self.use_current_pos_btn = ttk.Button(add_frame, text=self.get_text("update_position"), 
                                            command=self.use_current_position, width=8)
        self.use_current_pos_btn.grid(row=0, column=2, padx=(0, 5))
        
        # 添加按钮
        self.add_character_btn = ttk.Button(add_frame, text="添加标记", 
                                          command=self.add_character, width=8)
        self.add_character_btn.grid(row=0, column=3)
        
        # 坐标输入行
        coord_frame = ttk.Frame(add_frame)
        coord_frame.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(5, 0))
        coord_frame.columnconfigure(1, weight=1)
        coord_frame.columnconfigure(3, weight=1)
        coord_frame.columnconfigure(5, weight=1)
        
        ttk.Label(coord_frame, text="X:", width=2).grid(row=0, column=0, sticky=tk.W)
        self.character_x_entry = ttk.Entry(coord_frame, width=6)
        self.character_x_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Label(coord_frame, text="Y:", width=2).grid(row=0, column=2, sticky=tk.W)
        self.character_y_entry = ttk.Entry(coord_frame, width=6)
        self.character_y_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Label(coord_frame, text="Z:", width=2).grid(row=0, column=4, sticky=tk.W)
        self.character_z_entry = ttk.Entry(coord_frame, width=6)
        self.character_z_entry.grid(row=0, column=5, sticky=(tk.W, tk.E))
        
        # 位置标记列表区域
        list_frame = ttk.LabelFrame(parent_frame, text="位置标记列表", padding="3")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # 位置标记距离显示列表
        self.character_distance_text = tk.Text(list_frame, height=6, width=35, state='disabled', wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.character_distance_text.yview)
        self.character_distance_text.configure(yscrollcommand=scrollbar.set)
        
        self.character_distance_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 删除标记按钮行
        delete_frame = ttk.Frame(list_frame)
        delete_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        self.remove_character_btn = ttk.Button(delete_frame, text="删除标记", 
                                             command=self.remove_character, width=12)
        self.remove_character_btn.pack(side=tk.LEFT)
        
        ttk.Label(delete_frame, text="(输入标记名称)", foreground="gray").pack(side=tk.LEFT, padx=(10, 0))

    def setup_camera_area(self, parent_frame):
        """设置摄像头区域"""
        # 摄像头控制面板
        self.camera_control_frame = ttk.LabelFrame(parent_frame, text=self.get_text("camera_control"), padding="5")
        self.camera_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.camera_control_frame.columnconfigure(0, weight=1)
        
        # 摄像头控制按钮
        control_buttons = ttk.Frame(self.camera_control_frame)
        control_buttons.pack(fill=tk.X, pady=5)
        
        # 摄像头选择
        self.camera_label = ttk.Label(control_buttons, text=self.get_text("camera"))
        self.camera_label.pack(side=tk.LEFT, padx=(0, 5))
        self.camera_id_var = tk.StringVar(value="0")
        self.camera_combo = ttk.Combobox(control_buttons, textvariable=self.camera_id_var, 
                                        width=15, state="readonly")
        self.camera_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # 模型选择
        self.model_label = ttk.Label(control_buttons, text=self.get_text("model"))
        self.model_label.pack(side=tk.LEFT, padx=(0, 5))
        self.model_var = tk.StringVar(value="ResEmoteNet")
        self.model_combo = ttk.Combobox(control_buttons, textvariable=self.model_var,
                                  values=["Simple", "ResEmoteNet", "FER2013", "EmoNeXt"], 
                                  width=12, state="readonly")
        self.model_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_changed)
        
        # 刷新摄像头列表按钮
        self.refresh_btn = ttk.Button(control_buttons, text=self.get_text("refresh"), command=self.refresh_camera_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 初始化摄像头列表
        self.refresh_camera_list()
        
        # 摄像头启动/停止按钮
        self.camera_start_btn = ttk.Button(control_buttons, text=self.get_text("start_camera"), command=self.toggle_camera_only)
        self.camera_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 面部识别启动/停止按钮  
        self.face_detection_btn = ttk.Button(control_buttons, text=self.get_text("start_face_detection"), 
                                           command=self.toggle_face_detection, state="disabled")
        self.face_detection_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 截图按钮
        self.capture_btn = ttk.Button(control_buttons, text=self.get_text("screenshot"), command=self.capture_screenshot, 
                                     state="disabled")
        self.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 保存表情数据按钮
        self.save_expression_btn = ttk.Button(control_buttons, text=self.get_text("save_expression"), command=self.save_expression_data,
                                            state="disabled")
        self.save_expression_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 摄像头显示区域
        self.camera_display_frame = ttk.LabelFrame(parent_frame, text=self.get_text("camera_feed"), padding="5")
        self.camera_display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.camera_display_frame.columnconfigure(0, weight=1)
        self.camera_display_frame.rowconfigure(0, weight=1)
        
        # 视频显示标签 - 设置固定尺寸和样式
        self.video_label = tk.Label(self.camera_display_frame, text=self.get_text("click_to_start"), 
                                   bg="black", fg="white",
                                   font=("Arial", 12),
                                   width=80, height=30)  # 设置足够的显示空间
        self.video_label.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        # 表情数据显示区域
        self.expression_frame = ttk.LabelFrame(parent_frame, text=self.get_text("realtime_expression"), padding="5")
        self.expression_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        # 配置表情框架的列权重，避免重叠 - 每列占用3个网格位置
        self.expression_frame.columnconfigure(2, weight=1)  # 第一列进度条
        self.expression_frame.columnconfigure(5, weight=1)  # 第二列进度条
        
        # 表情数据标签 - 7种标准情感
        self.expressions = {
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
        self.expression_labels = {}
        self.expression_progress_bars = {}
        
        for expr_name in self.expressions.keys():
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
            
            ttk.Label(self.expression_frame, text=f"{display_name}:").grid(
                row=row, column=base_col, sticky=tk.W, padx=(0, 5))
            
            # 数值显示
            value_label = ttk.Label(self.expression_frame, text="0.00", width=6)
            value_label.grid(row=row, column=base_col+1, sticky=tk.W, padx=(0, 5))
            self.expression_labels[expr_name] = value_label
            
            # 进度条
            progress = ttk.Progressbar(self.expression_frame, length=120, mode='determinate')
            progress.grid(row=row, column=base_col+2, sticky=(tk.W, tk.E), padx=(0, 15))
            progress['maximum'] = 100
            self.expression_progress_bars[expr_name] = progress
            
            col += 1
            if col >= 2:
                col = 0
                row += 1
        
        # 添加分隔线和整体状态显示
        row += 1
        separator = ttk.Separator(self.expression_frame, orient='horizontal')
        separator.grid(row=row, column=0, columnspan=6, sticky=(tk.W, tk.E), pady=(10, 5))
        
        row += 1
        # 整体情感状态显示
        ttk.Label(self.expression_frame, text="整体状态:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))
        
        self.overall_status_label = ttk.Label(self.expression_frame, text="中立 (0.00)", width=15)
        self.overall_status_label.grid(row=row, column=1, sticky=tk.W, padx=(0, 5))
        
        self.overall_status_progress = ttk.Progressbar(self.expression_frame, length=250, mode='determinate')
        self.overall_status_progress.grid(row=row, column=2, columnspan=4, sticky=(tk.W, tk.E), padx=(0, 15))
        self.overall_status_progress['maximum'] = 100
    
    def log(self, message: str):
        """添加日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_log(log_message))
    
    def _update_log(self, message: str):
        """更新日志显示（在主线程中调用）"""
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
    
    def add_speech_output(self, text: str, source: str = None):
        """添加语音识别输出"""
        timestamp = time.strftime("%H:%M:%S")
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_speech_output(timestamp, source, text))
    
    def _update_speech_output(self, timestamp: str, source: str, text: str):
        """更新语音识别输出显示（在主线程中调用）"""
        # 插入时间戳（灰色）
        start_pos = self.speech_text.index(tk.END + "-1c")
        self.speech_text.insert(tk.END, f"[{timestamp}] ")
        self.speech_text.tag_add(self.get_text("timestamp"), start_pos, self.speech_text.index(tk.END + "-1c"))
        
        # 插入来源标签（彩色）
        start_pos = self.speech_text.index(tk.END + "-1c")
        self.speech_text.insert(tk.END, f"[{source}] ")
        self.speech_text.tag_add(source, start_pos, self.speech_text.index(tk.END + "-1c"))
        
        # 插入语音内容（黑色）
        self.speech_text.insert(tk.END, f"{text}\n")
        
        # 滚动到底部
        self.speech_text.see(tk.END)
        
        # 限制最大行数，防止内存占用过多
        lines = self.speech_text.get(1.0, tk.END).split('\n')
        if len(lines) > 500:  # 保留最近500条记录
            # 删除前100行
            for i in range(100):
                self.speech_text.delete(1.0, "2.0")
    
    def clear_speech_output(self):
        """清空语音识别输出"""
        self.speech_text.delete(1.0, tk.END)
    
    def save_speech_output(self):
        """保存语音识别输出到文件"""
        try:
            import tkinter.filedialog as filedialog
            
            filename = filedialog.asksaveasfilename(
                title=self.get_text("save_speech_record"),
                defaultextension=".txt",
                filetypes=[(self.get_text("text_files"), "*.txt"), (self.get_text("all_files"), "*.*")]
            )
            
            if filename:
                content = self.speech_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log(f"语音记录已保存到: {filename}")
                
        except Exception as e:
            messagebox.showerror(self.get_text("save_error"), f"{self.get_text('cannot_load_audio_file')}: {e}")
            self.log(f"保存语音记录失败: {e}")
    
    def update_ui_state(self, connected: bool):
        """更新UI状态"""
        self.is_connected = connected
        
        if connected:
            self.connect_btn.config(text=self.get_text("disconnect"))
            self.status_label.config(text=self.get_text("connected"), foreground="green")
            # 启用功能按钮
            self.listen_btn.config(state="normal")
            self.upload_voice_btn.config(state="normal")
        else:
            self.connect_btn.config(text=self.get_text("connect"))
            self.status_label.config(text=self.get_text("disconnected"), foreground="red")
            # 禁用功能按钮
            self.listen_btn.config(state="disabled")
            self.upload_voice_btn.config(state="disabled")
            
            # 停止语音监听
            if self.is_listening:
                self.is_listening = False
                self.listen_btn.config(text=self.get_text("start_listening"))
    
    def toggle_connection(self):
        """切换连接状态"""
        if not self.is_connected:
            self.connect_to_vrchat()
        else:
            self.disconnect_from_vrchat()
    
    def connect_to_vrchat(self):
        """连接到VRChat"""
        try:
            host = self.host_var.get().strip()
            send_port = int(self.send_port_var.get())
            receive_port = int(self.receive_port_var.get())
            device = self.device_var.get()
            
            # 禁用连接按钮并显示加载状态
            self.connect_btn.config(text="连接中...", state="disabled")
            self.progress_bar.grid()  # 显示进度条
            self.progress_bar.start()  # 开始进度条动画
            self.log("开始连接VRChat...")
            self.log(f"正在加载语音识别模型 ({device})...")
            self.log("提示：首次加载可能需要较长时间，请耐心等待...")
            
            # 在后台线程中连接，避免界面卡顿
            def connect_thread():
                try:
                    # 创建OSC客户端，传递参数（如果与配置不同）
                    use_config_host = host == self.config.osc_host
                    use_config_ports = (send_port == self.config.osc_send_port and 
                                       receive_port == self.config.osc_receive_port)
                    use_config_device = device == self.config.voice_device
                    
                    # 只传递与配置不同的参数
                    self.client = VRChatController(
                        host=None if use_config_host else host,
                        send_port=None if use_config_ports else send_port,
                        receive_port=None if use_config_ports else receive_port,
                        speech_device=None if use_config_device else device
                    )
                    
                    # 设置回调函数
                    self.client.set_status_change_callback(self.on_status_change)
                    self.client.set_voice_result_callback(self.on_voice_result)
                    
                    # 应用默认设置
                    if hasattr(self.client, 'set_disable_fallback_mode'):
                        self.client.set_disable_fallback_mode(self.disable_fallback_var.get())
                    
                    # 启动服务器
                    success = self.client.start_osc_server()
                    
                    if success:
                        # 在主线程中更新UI
                        self.root.after(0, lambda: self._connection_success(host, send_port))
                    else:
                        self.root.after(0, lambda: self._connection_failed("OSC服务器启动失败"))
                        
                except Exception as e:
                    self.root.after(0, lambda: self._connection_failed(str(e)))
            
            # 启动连接线程
            threading.Thread(target=connect_thread, daemon=True).start()
            
        except ValueError:
            self.connect_btn.config(text="连接", state="normal")
            self.progress_bar.stop()
            self.progress_bar.grid_remove()
            messagebox.showerror(self.get_text("error"), self.get_text("port_must_be_number"))
        except Exception as e:
            self.connect_btn.config(text="连接", state="normal")
            self.progress_bar.stop()
            self.progress_bar.grid_remove()
            messagebox.showerror(self.get_text("connection_error"), f"{self.get_text('cannot_connect_vrchat')}: {e}")
            self.log(f"连接失败: {e}")
    
    def _connection_success(self, host: str, send_port: int):
        """连接成功的UI更新"""
        # 隐藏进度条
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        
        # 设置Avatar控制器
        if self.client:
            # 设置Avatar控制器的OSC客户端（VRChatController）
            self.avatar_controller.set_osc_client(self.client)
            
            # 通过VRChatController设置位置回调
            self.client.set_position_callback(self.update_player_position)
        
        self.update_ui_state(True)
        self.log(f"已连接到VRChat OSC服务器 {host}:{send_port}")
        self.log("语音识别模型加载完成！")
        self.log(self.get_text("voice_recognition_ready"))
    
    def _connection_failed(self, error_msg: str):
        """连接失败的UI更新"""
        # 隐藏进度条
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        
        self.connect_btn.config(text="连接", state="normal")
        messagebox.showerror(self.get_text("connection_error"), f"{self.get_text('cannot_connect_vrchat')}: {error_msg}")
        self.log(f"连接失败: {error_msg}")
    
    def disconnect_from_vrchat(self):
        """断开VRChat连接"""
        try:
            if self.client:
                # 停止语音监听
                if self.is_listening:
                    self.client.stop_voice_listening()
                    self.is_listening = False
                    self.listen_btn.config(text="开始监听")
                    self.log("已停止语音监听")
                
                # 停止OSC服务器
                self.client.stop_osc_server()
                self.log("OSC服务器已停止")
                
                # 清理资源
                self.client.cleanup()
                self.client = None
            
            self.update_ui_state(False)
            self.log("[成功] 已断开VRChat连接")
            
        except Exception as e:
            self.log(f"[错误] 断开连接时出错: {e}")
            # 即使出错也要更新UI状态
            self.update_ui_state(False)
    
    def send_text_message(self):
        """发送文字消息"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            return
        
        message = self.message_entry.get().strip()
        if not message:
            return
        
        try:
            self.client.send_text_message(message)
            self.log(f"[发送文字] {message}")
            self.message_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror(self.get_text("send_error"), f"{self.get_text('send_message_failed')}: {e}")
            self.log(f"发送消息失败: {e}")
    
    def toggle_voice_listening(self):
        """切换语音监听状态"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            return
        
        if not self.is_listening:
            self.start_voice_listening()
        else:
            self.stop_voice_listening()
    
    def start_voice_listening(self):
        """开始语音监听"""
        try:
            # 检查语音引擎是否就绪
            if not self.client.speech_engine.is_model_loaded():
                messagebox.showerror(self.get_text("voice_recognition_error"), self.get_text("voice_model_not_loaded"))
                self.log("语音识别模型未加载")
                return
            
            def voice_callback(text):
                if text and text.strip():
                    # 显示在专门的语音识别输出框
                    self.add_speech_output(text, "持续监听")
                    # 发送到VRChat
                    self.client.send_text_message(f"[语音] {text}")
                    # 记录到日志
                    self.log(f"[持续语音] {text}")
                    
                    # 如果启用了LLM处理，发送到LLM
                    if self.llm_enabled and self.llm_handler and self.llm_handler.is_client_ready():
                        request_id = self.llm_handler.submit_voice_text(text)
                        if request_id:
                            self.log(f"[LLM] 已提交语音到AI处理: {text[:50]}...")
                        else:
                            self.log("[LLM] 提交语音到AI失败")
                    
                    # 调用原有的语音结果处理
                    if hasattr(self, 'on_voice_result'):
                        self.on_voice_result(text)
            
            # 设置语音结果回调
            self.client.set_voice_result_callback(voice_callback)
            
            # 启动语音监听
            success = self.client.start_voice_listening(self.language_var.get())
            
            if success:
                self.is_listening = True
                self.listen_btn.config(text="停止监听", style="Accent.TButton")
                self.log("开始VRChat语音状态监听...")
                self.log("提示：只有当VRChat检测到你说话时才会进行语音识别")
            else:
                self.log("启动语音监听失败")
                messagebox.showerror(self.get_text("voice_recognition_error"), self.get_text("voice_listening_failed"))
            
        except Exception as e:
            messagebox.showerror(self.get_text("voice_recognition_error"), f"{self.get_text('voice_listening_failed')}: {e}")
            self.log(f"启动语音监听失败: {e}")
    
    def stop_voice_listening(self):
        """停止语音监听"""
        try:
            self.is_listening = False
            if self.client:
                self.client.stop_voice_listening()
            self.listen_btn.config(text="开始监听", style="TButton")
            self.log("停止持续语音识别")
            
        except Exception as e:
            self.log(f"停止语音监听时出错: {e}")
    
    def send_parameter(self):
        """发送Avatar参数"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            return
        
        param_name = self.param_name_entry.get().strip()
        param_value_str = self.param_value_entry.get().strip()
        
        if not param_name or not param_value_str:
            messagebox.showwarning("警告", "参数名和值不能为空")
            return
        
        try:
            # 尝试转换参数值类型
            param_value = param_value_str
            if param_value_str.lower() in ['true', 'false']:
                param_value = param_value_str.lower() == 'true'
            elif '.' in param_value_str:
                try:
                    param_value = float(param_value_str)
                except ValueError:
                    pass
            else:
                try:
                    param_value = int(param_value_str)
                except ValueError:
                    pass
            
            self.client.send_parameter(param_name, param_value)
            self.log(f"[发送参数] {param_name} = {param_value}")
            
            # 清空输入框
            self.param_name_entry.delete(0, tk.END)
            self.param_value_entry.delete(0, tk.END)
            
        except Exception as e:
            messagebox.showerror("发送错误", f"发送参数失败: {e}")
            self.log(f"发送参数失败: {e}")
    
    def on_status_change(self, status_type: str, data):
        """处理状态变化"""
        if status_type == "parameter":
            param_name, value = data
            self.log(f"[收到参数] {param_name} = {value}")
        elif status_type == "message":
            msg_type, content = data
            self.log(f"[收到消息] {msg_type}: {content}")
        elif status_type == "vrc_speaking":
            self.log(f"[VRC语音状态] {'说话中' if data else '静音'}")
    
    def on_voice_result(self, text: str):
        """处理语音识别结果"""
        # 这个方法现在主要用于兼容性，实际显示已经在各个回调中处理
        pass
    
    def update_voice_threshold(self, value):
        """更新语音阈值"""
        threshold = float(value)
        if self.client:
            self.client.set_voice_threshold(threshold)
        self.threshold_label.config(text=f"{threshold:.3f}")
        self.log(f"语音阈值已设置为: {threshold:.3f}")
    
    def update_pause_threshold(self, value):
        """更新断句间隔阈值"""
        threshold = float(value)
        if self.client and hasattr(self.client, 'set_sentence_pause_threshold'):
            self.client.set_sentence_pause_threshold(threshold)
        # 同时更新配置
        self.config.set('Recording', 'sentence_pause_threshold', threshold)
        self.pause_label.config(text=f"{threshold:.1f}s")
        self.log(f"断句间隔已设置为: {threshold:.1f}秒")
    
    def open_settings(self):
        """打开高级设置窗口"""
        SettingsWindow(self.root, callback=self.on_settings_changed)
    
    def on_settings_changed(self, apply_only=False):
        """设置更改后的回调"""
        try:
            # 更新当前界面的变量
            self.host_var.set(self.config.osc_host)
            self.send_port_var.set(str(self.config.osc_send_port))
            self.receive_port_var.set(str(self.config.osc_receive_port))
            self.language_var.set(self.config.voice_language)
            self.device_var.set(self.config.voice_device)
            
            # 更新阈值显示
            self.threshold_var.set(self.config.voice_threshold)
            self.threshold_label.config(text=f"{self.config.voice_threshold:.3f}")
            self.pause_var.set(self.config.sentence_pause_threshold)
            self.pause_label.config(text=f"{self.config.sentence_pause_threshold:.1f}s")
            
            # 更新复选框状态
            self.debug_var.set(self.config.osc_debug_mode)
            self.fallback_var.set(self.config.use_fallback_mode)
            self.disable_fallback_var.set(self.config.disable_fallback_mode)
            
            # 如果有活动连接，应用新设置
            if self.is_connected and self.client:
                # 应用语音设置
                self.client.set_voice_threshold(self.config.voice_threshold)
                self.client.set_sentence_pause_threshold(self.config.sentence_pause_threshold)
                
                # 应用模式设置
                self.client.set_fallback_mode(self.config.use_fallback_mode)
                self.client.set_disable_fallback_mode(self.config.disable_fallback_mode)
                self.client.set_debug_mode(self.config.osc_debug_mode)
                
            # 更新窗口大小（如果需要）
            current_geometry = self.root.geometry()
            new_size = f"{self.config.window_width}x{self.config.window_height}"
            if new_size not in current_geometry:
                self.root.geometry(new_size)
            
            action = "应用" if apply_only else "保存"
            self.log(f"[成功] 设置已{action}并生效")
            
        except Exception as e:
            self.log(f"[错误] 应用设置时出错: {e}")
    
    def update_voice_threshold(self, value):
        """更新语音阈值"""
        threshold = float(value)
        if self.client:
            self.client.set_voice_threshold(threshold)
        # 同时更新配置
        self.config.set('Voice', 'voice_threshold', threshold)
        self.threshold_label.config(text=f"{threshold:.3f}")
        self.log(f"语音阈值已设置为: {threshold:.3f}")
    
    def open_settings_window(self):
        """打开高级设置窗口"""
        try:
            from ui.settings_window import SettingsWindow
            
            # 创建设置窗口，传入回调函数
            settings_window = SettingsWindow(self.root, self.on_settings_saved)
            
        except ImportError as e:
            messagebox.showerror("错误", f"无法加载设置窗口: {e}")
        except Exception as e:
            messagebox.showerror("错误", f"打开设置窗口失败: {e}")
    
    def on_settings_saved(self):
        """设置保存后的回调函数"""
        try:
            # 重新加载配置
            self.load_settings()
            self.log("高级设置已保存并应用")
            
            # 如果需要，可以在这里更新UI或重启某些功能
            # 例如重新初始化某些组件
            
        except Exception as e:
            self.log(f"应用高级设置时出错: {e}")
    
    def on_closing(self):
        """窗口关闭事件处理"""
        try:
            if self.camera_running:
                self.stop_camera_only()
            if self.is_listening:
                self.stop_voice_listening()
            if self.is_connected:
                self.disconnect_from_vrchat()
            
            # 清理AI角色管理器
            if self.single_ai_manager:
                print("正在清理AI角色管理器...")
                self.single_ai_manager.cleanup()
                
            self.root.destroy()
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            self.root.destroy()
    
    def upload_voice_file(self):
        """上传语音文件"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            return
        
        # 选择文件
        file_path = filedialog.askopenfilename(
            title=self.get_text("upload_voice"),
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.flac *.ogg *.m4a"),
                ("WAV文件", "*.wav"),
                ("MP3文件", "*.mp3"),
                ("FLAC文件", "*.flac"),
                ("所有文件", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            self.log(f"加载音频文件: {os.path.basename(file_path)}")
            
            # 读取音频文件
            audio_data, sample_rate = sf.read(file_path)
            
            # 转换为单声道（如果是立体声）
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            # 转换为float32格式
            audio_data = audio_data.astype(np.float32)
            
            # 保存上传的音频数据
            self.uploaded_audio_data = audio_data
            self.uploaded_audio_sample_rate = sample_rate
            self.uploaded_filename = os.path.basename(file_path)
            
            duration = len(audio_data) / sample_rate
            self.log(f"[成功] 音频文件加载成功: {self.uploaded_filename}")
            self.log(f"   时长: {duration:.2f}秒, 采样率: {sample_rate}Hz")
            
            # 直接识别并发送音频文件
            self.log(f"开始识别音频文件: {self.uploaded_filename}")
            
            def recognize_and_send():
                try:
                    # 识别音频文件
                    text = self.client.speech_engine.recognize_audio(
                        audio_data, sample_rate, self.language_var.get()
                    )
                    
                    if text and text.strip():
                        # 显示在语音识别输出框
                        self.add_speech_output(text, f"文件: {self.uploaded_filename}")
                        # 发送到VRChat
                        self.client.send_text_message(f"[音频文件] {text}")
                        # 记录到日志
                        self.log(f"[成功] 音频文件识别并发送: {text}")
                        
                        # 如果启用了LLM处理，发送到LLM
                        if self.llm_enabled and self.llm_handler and self.llm_handler.is_client_ready():
                            request_id = self.llm_handler.submit_voice_text(text)
                            if request_id:
                                self.log(f"[LLM] 已提交音频文件到AI处理: {text[:50]}...")
                            else:
                                self.log("[LLM] 提交音频文件到AI失败")
                    else:
                        self.log("[错误] 音频文件识别失败")
                        
                except Exception as e:
                    self.log(f"[错误] 音频文件识别出错: {e}")
                    messagebox.showerror("识别错误", f"音频识别失败: {e}")
            
            # 在后台线程中进行识别
            threading.Thread(target=recognize_and_send, daemon=True).start()
            
        except Exception as e:
            self.log(f"[错误] 音频文件加载失败: {e}")
            messagebox.showerror("文件错误", f"无法加载音频文件: {e}")
    
    def toggle_debug_mode(self):
        """切换调试模式"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            self.debug_var.set(False)
            return
        
        debug_enabled = self.debug_var.get()
        self.client.set_debug_mode(debug_enabled)
        status = "启用" if debug_enabled else "禁用"
        self.log(f"OSC调试模式已{status}")
    
    def toggle_fallback_mode(self):
        """切换强制备用模式"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            self.fallback_var.set(False)
            return
        
        # 如果启用强制备用模式，自动禁用"禁用备用模式"
        if self.fallback_var.get():
            self.disable_fallback_var.set(False)
            if hasattr(self.client, 'set_disable_fallback_mode'):
                self.client.set_disable_fallback_mode(False)
        
        fallback_enabled = self.fallback_var.get()
        self.client.set_fallback_mode(fallback_enabled)
        status = "启用" if fallback_enabled else "禁用"
        self.log(f"强制备用模式已{status}")
    
    def toggle_disable_fallback_mode(self):
        """切换禁用备用模式"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            self.disable_fallback_var.set(False)
            return
        
        # 如果禁用备用模式，自动禁用"强制备用模式"
        if self.disable_fallback_var.get():
            self.fallback_var.set(False)
            self.client.set_fallback_mode(False)
        
        disable_enabled = self.disable_fallback_var.get()
        if hasattr(self.client, 'set_disable_fallback_mode'):
            self.client.set_disable_fallback_mode(disable_enabled)
            status = "禁用" if disable_enabled else "启用"
            self.log(f"备用模式已{status}")
            
            if disable_enabled:
                self.log("注意：系统将只依赖VRChat语音状态，请确保VRChat OSC功能正常")
    
    def show_debug_status(self):
        """显示调试状态信息"""
        if not self.is_connected:
            messagebox.showwarning(self.get_text("warning"), self.get_text("please_connect_first"))
            return
        
        try:
            # 获取详细状态信息
            status = self.client.get_status()
            debug_info = self.client.get_debug_info()
            diagnosis = self.client.osc_client.get_vrchat_connection_diagnosis()
            
            # 创建状态信息窗口
            status_window = tk.Toplevel(self.root)
            status_window.title("系统状态信息")
            status_window.geometry("600x500")
            status_window.resizable(True, True)
            
            # 创建文本框显示状态
            status_text = scrolledtext.ScrolledText(status_window, font=("Consolas", 9))
            status_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 格式化状态信息
            status_info = "=== VRChat OSC 系统状态 ===\n\n"
            
            # 基本状态
            status_info += "【连接状态】\n"
            status_info += f"OSC服务器: {'运行中' if status['osc_connected'] else '未运行'}\n"
            status_info += f"VRChat语音状态: {'说话中' if status['vrc_speaking'] else '静音'}\n"
            status_info += f"VRChat语音强度: {status['vrc_voice_level']:.4f}\n"
            status_info += f"语音监听: {'运行中' if status['voice_listening'] else '未运行'}\n"
            status_info += f"语音引擎: {'就绪' if status['speech_engine_ready'] else '未就绪'}\n\n"
            
            # 模式状态
            status_info += "【录制模式】\n"
            status_info += f"备用模式激活: {'是' if status['fallback_mode_active'] else '否'}\n"
            status_info += f"强制备用模式: {'是' if status['use_fallback_mode'] else '否'}\n\n"
            
            # VRChat参数
            status_info += "【检测到的VRChat语音参数】\n"
            if status['received_voice_parameters']:
                for param in status['received_voice_parameters']:
                    status_info += f"- {param}\n"
            else:
                status_info += "未检测到任何VRChat语音参数\n"
            status_info += "\n"
            
            # 监听的参数列表
            status_info += "【监听的参数列表】\n"
            for param in debug_info['osc']['monitoring_parameters']:
                status_info += f"- {param}\n"
            status_info += "\n"
            
            # 语音引擎信息
            status_info += "【语音引擎】\n"
            status_info += f"计算设备: {debug_info['speech_engine']['device']}\n"
            status_info += f"语音阈值: {debug_info['speech_engine']['voice_threshold']}\n"
            status_info += f"模型已加载: {'是' if debug_info['speech_engine']['model_loaded'] else '否'}\n\n"
            
            # 调试信息
            status_info += "【调试设置】\n"
            status_info += f"OSC调试模式: {'启用' if debug_info['osc']['debug_mode'] else '禁用'}\n"
            status_info += f"VRChat检测超时: {debug_info['controller']['vrc_detection_timeout']}秒\n\n"
            
            # VRChat连接诊断
            status_info += "【VRChat连接诊断】\n"
            if diagnosis['status'] == 'working':
                status_info += "[成功] VRChat OSC连接正常\n"
            elif diagnosis['status'] == 'no_vrchat_data':
                status_info += "[错误] 未检测到VRChat数据\n"
                status_info += "\n[搜索] 可能原因:\n"
                for issue in diagnosis['issues']:
                    status_info += f"• {issue}\n"
                status_info += "\n[建议] 建议解决方案:\n"
                for suggestion in diagnosis['suggestions']:
                    status_info += f"• {suggestion}\n"
            elif diagnosis['status'] == 'receiving_data_but_no_voice':
                status_info += "[警告] 收到VRChat数据但无语音状态\n"
                status_info += "\n[建议] 建议:\n"
                for suggestion in diagnosis['suggestions']:
                    status_info += f"• {suggestion}\n"
            else:
                status_info += "❓ 连接状态未知\n"
            
            status_text.insert(tk.END, status_info)
            status_text.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("错误", f"获取状态信息失败: {e}")
            self.log(f"显示状态失败: {e}")
    
    def on_language_changed(self, event=None):
        """语言选择框改变事件"""
        selected_display = self.ui_language_display.get()
        selected_lang = DISPLAY_TO_LANGUAGE_MAP.get(selected_display, "zh")
        
        # 更新内部语言变量
        self.ui_language.set(selected_lang)
        
        # 更新窗口标题
        self.root.title(self.get_text("title"))
        
        # 更新所有界面框架标题
        self.connection_frame.config(text=self.get_text("connection_settings"))
        self.message_frame.config(text=self.get_text("message_send"))
        self.param_frame.config(text=self.get_text("avatar_params"))
        self.log_frame.config(text=self.get_text("log"))
        self.speech_frame.config(text=self.get_text("speech_output"))
        
        # 更新摄像头区域文本
        if hasattr(self, 'camera_control_frame'):
            self.camera_control_frame.config(text=self.get_text("camera_control"))
            self.camera_display_frame.config(text=self.get_text("camera_feed"))
            self.expression_frame.config(text=self.get_text("realtime_expression"))
        
        # 更新所有标签文本
        if hasattr(self, 'text_message_label'):
            self.text_message_label.config(text=self.get_text("text_message"))
        if hasattr(self, 'recognition_language_label'):
            self.recognition_language_label.config(text=self.get_text("recognition_language"))
        if hasattr(self, 'compute_device_label'):
            self.compute_device_label.config(text=self.get_text("compute_device"))
        if hasattr(self, 'voice_threshold_label'):
            self.voice_threshold_label.config(text=self.get_text("voice_threshold"))
        if hasattr(self, 'param_name_label'):
            self.param_name_label.config(text=self.get_text("param_name"))
        if hasattr(self, 'param_value_label'):
            self.param_value_label.config(text=self.get_text("param_value"))
        
        # 更新摄像头控制标签
        if hasattr(self, 'camera_label'):
            self.camera_label.config(text=self.get_text("camera"))
            self.model_label.config(text=self.get_text("model"))
        
        # 更新所有按钮文本
        if self.is_connected:
            self.connect_btn.config(text=self.get_text("disconnect"))
        else:
            self.connect_btn.config(text=self.get_text("connect"))
            
        if self.is_listening:
            self.listen_btn.config(text=self.get_text("stop_listening"))
        else:
            self.listen_btn.config(text=self.get_text("start_listening"))
            
        # 更新新添加的按钮和标签
        if hasattr(self, 'advanced_settings_btn'):
            self.advanced_settings_btn.config(text=self.get_text("advanced_settings"))
        if hasattr(self, 'fallback_check'):
            self.fallback_check.config(text=self.get_text("force_fallback_mode"))
        if hasattr(self, 'disable_fallback_check'):
            self.disable_fallback_check.config(text=self.get_text("disable_fallback_mode"))
        if hasattr(self, 'save_expression_btn'):
            self.save_expression_btn.config(text=self.get_text("save_expression"))
        if hasattr(self, 'voicevox_control_frame'):
            self.voicevox_control_frame.config(text=self.get_text("character"))
        if hasattr(self, 'voicevox_test_btn'):
            self.voicevox_test_btn.config(text=self.get_text("voice_test"))
        
        # 更新状态标签
        if hasattr(self, 'status_label'):
            if self.is_connected:
                self.status_label.config(text=self.get_text("connected"))
            else:
                self.status_label.config(text=self.get_text("disconnected"))
        if hasattr(self, 'voicevox_status_label') and hasattr(self, 'voicevox_status_label'):
            # VOICEVOX状态根据实际连接状态更新
            pass
        
        if hasattr(self, 'send_text_btn'):
            self.send_text_btn.config(text=self.get_text("send_text"))
        if hasattr(self, 'upload_voice_btn'):
            self.upload_voice_btn.config(text=self.get_text("upload_voice"))
        if hasattr(self, 'record_voice_btn'):
            self.record_voice_btn.config(text=self.get_text("record_voice"))
        if hasattr(self, 'debug_check'):
            self.debug_check.config(text=self.get_text("debug"))
        if hasattr(self, 'status_btn'):
            self.status_btn.config(text=self.get_text("show_status"))
        if hasattr(self, 'camera_btn'):
            self.camera_btn.config(text=self.get_text("camera_window"))
        if hasattr(self, 'settings_btn'):
            self.settings_btn.config(text=self.get_text("settings"))
        if hasattr(self, 'send_param_btn'):
            self.send_param_btn.config(text=self.get_text("send_param"))
        # 更新角色管理区域组件
        if hasattr(self, 'add_character_btn'):
            self.add_character_btn.config(text=self.get_text("add_character"))
        if hasattr(self, 'remove_character_btn'):
            self.remove_character_btn.config(text=self.get_text("remove_character"))
        if hasattr(self, 'use_current_pos_btn'):
            self.use_current_pos_btn.config(text=self.get_text("update_position"))
        if hasattr(self, 'clear_log_btn'):
            self.clear_log_btn.config(text=self.get_text("clear_log"))
        if hasattr(self, 'clear_speech_btn'):
            self.clear_speech_btn.config(text=self.get_text("clear_speech"))
        if hasattr(self, 'save_speech_btn'):
            self.save_speech_btn.config(text=self.get_text("save_speech"))
        
        # 更新摄像头控制按钮
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.config(text=self.get_text("refresh"))
        if hasattr(self, 'camera_start_btn'):
            if self.camera_running:
                self.camera_start_btn.config(text=self.get_text("stop_camera"))
            else:
                self.camera_start_btn.config(text=self.get_text("start_camera"))
        if hasattr(self, 'face_detection_btn'):
            if self.face_detection_running:
                self.face_detection_btn.config(text=self.get_text("stop_face_detection"))
            else:
                self.face_detection_btn.config(text=self.get_text("start_face_detection"))
        if hasattr(self, 'capture_btn'):
            self.capture_btn.config(text=self.get_text("screenshot"))
        
        # 更新摄像头显示区域文本
        if hasattr(self, 'video_label') and not self.camera_running:
            self.video_label.config(text=self.get_text("click_to_start"))
        
        # 重新构建表情数据标签（因为标签名称需要更新）
        if hasattr(self, 'expression_labels'):
            self.refresh_expression_labels()
        
        # 记录语言切换
        self.log(f"界面语言已切换为: {selected_display}")
    
    def refresh_expression_labels(self):
        """刷新表情数据标签的文本"""
        # 销毁现有的表情显示组件
        for widget in self.expression_frame.winfo_children():
            widget.destroy()
        
        # 重新创建表情显示组件
        row = 0
        col = 0
        self.expression_labels = {}
        self.expression_progress_bars = {}
        
        for expr_name in self.expressions.keys():
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
            
            ttk.Label(self.expression_frame, text=f"{display_name}:").grid(
                row=row, column=base_col, sticky=tk.W, padx=(0, 5))
            
            # 数值显示
            value_label = ttk.Label(self.expression_frame, text="0.00", width=6)
            value_label.grid(row=row, column=base_col+1, sticky=tk.W, padx=(0, 5))
            self.expression_labels[expr_name] = value_label
            
            # 进度条
            progress = ttk.Progressbar(self.expression_frame, length=120, mode='determinate')
            progress.grid(row=row, column=base_col+2, sticky=(tk.W, tk.E), padx=(0, 15))
            progress['maximum'] = 100
            self.expression_progress_bars[expr_name] = progress
            
            col += 1
            if col >= 2:
                col = 0
                row += 1
        
        # 添加分隔线和整体状态显示
        row += 1
        separator = ttk.Separator(self.expression_frame, orient='horizontal')
        separator.grid(row=row, column=0, columnspan=6, sticky=(tk.W, tk.E), pady=(10, 5))
        
        row += 1
        # 整体情感状态显示
        ttk.Label(self.expression_frame, text="整体状态:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))
        
        self.overall_status_label = ttk.Label(self.expression_frame, text="中立 (0.00)", width=15)
        self.overall_status_label.grid(row=row, column=1, sticky=tk.W, padx=(0, 5))
        
        self.overall_status_progress = ttk.Progressbar(self.expression_frame, length=250, mode='determinate')
        self.overall_status_progress.grid(row=row, column=2, columnspan=4, sticky=(tk.W, tk.E), padx=(0, 15))
        self.overall_status_progress['maximum'] = 100
    
    def toggle_camera_only(self):
        """只切换摄像头状态（不包含面部识别）"""
        if not self.camera_running:
            self.start_camera_only()
        else:
            self.stop_camera_only()
    
    def toggle_face_detection(self):
        """切换面部识别状态"""
        if not self.face_detection_running:
            self.start_face_detection()
        else:
            self.stop_face_detection()
    
    def start_camera_only(self):
        """只启动摄像头（不启动面部识别）"""
        try:
            # 获取选中的摄像头信息
            selected_camera = self.camera_id_var.get()
            
            # 从映射中获取实际的摄像头ID
            if hasattr(self, 'camera_id_mapping') and selected_camera in self.camera_id_mapping:
                camera_id = self.camera_id_mapping[selected_camera]
            else:
                try:
                    camera_id = int(selected_camera.split()[1]) if '摄像头' in selected_camera else int(selected_camera)
                except:
                    camera_id = 0
                    self.log("无法解析摄像头ID，使用默认摄像头0")
            
            self.log(f"正在启动摄像头: {selected_camera} (ID: {camera_id})")
            
            # 直接使用OpenCV启动摄像头
            self.camera = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            
            if not self.camera.isOpened():
                raise RuntimeError(f"无法打开摄像头 {camera_id}")
            
            # 测试读取
            ret, frame = self.camera.read()
            if not ret or frame is None:
                raise RuntimeError(f"摄像头 {camera_id} 无法读取画面")
            
            # 设置分辨率
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.camera_running = True
            self.camera_start_btn.config(text="停止摄像头")
            self.face_detection_btn.config(state="normal")
            self.capture_btn.config(state="normal")
            self.save_expression_btn.config(state="normal")
            
            # 启动简单的视频显示线程
            self.camera_thread = threading.Thread(target=self.simple_video_loop, daemon=True)
            self.camera_thread.start()
            
            self.log(self.get_text("camera_start_success"))
            
        except Exception as e:
            self.log(f"摄像头启动失败: {e}")
            if self.camera:
                self.camera.release()
                self.camera = None
    
    def simple_video_loop(self):
        """简单的视频显示循环（不包含面部识别）"""
        while self.camera_running and self.camera and self.camera.isOpened():
            try:
                ret, frame = self.camera.read()
                if ret and frame is not None:
                    # 调整图像大小
                    display_frame = cv2.resize(frame, (640, 480))
                    
                    # 如果启用了面部识别，进行处理
                    if self.face_detection_running:
                        display_frame, expressions = self.process_face_detection(display_frame)
                        # 更新表情显示
                        self.root.after(0, lambda: self._update_expression_display(expressions))
                    
                    # 转换为显示格式
                    frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(img)
                    
                    # 更新显示
                    self.current_frame = frame
                    self.root.after(0, lambda p=photo: self.update_video_display(p))
                    
                time.sleep(0.03)  # 约33fps
                
            except Exception as e:
                if self.camera_running:
                    self.log(f"视频循环错误: {e}")
                time.sleep(0.1)
    
    def start_face_detection(self):
        """启动面部识别"""
        try:
            self.log(f"正在启动面部识别模型: {self.emotion_model_type}")
            
            # 如果使用GPU模型，初始化检测器
            if self.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
                if not hasattr(self, 'gpu_detector') or self.gpu_detector is None:
                    try:
                        from src.face.gpu_emotion_detector import GPUEmotionDetector
                        self.gpu_detector = GPUEmotionDetector(model_type=self.emotion_model_type, device='auto')
                        self.log(f"成功初始化GPU情感检测器: {self.emotion_model_type}")
                    except Exception as e:
                        self.log(f"GPU检测器初始化失败: {e}")
                        self.log("将使用Simple模式作为后备")
                        self.emotion_model_type = 'Simple'
            
            # 这里不需要重新创建摄像头实例，只是设置标志
            self.face_detection_running = True
            self.face_detection_btn.config(text="停止面部识别")
            
            self.log("面部识别启动成功")
            
        except Exception as e:
            self.log(f"面部识别启动失败: {e}")
    
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
            if self.emotion_model_type == 'Simple':
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
            
            elif self.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
                # 使用GPU加速的情感识别模型
                if hasattr(self, 'gpu_detector') and self.gpu_detector is not None:
                    try:
                        annotated_frame, expressions = self.gpu_detector.process_frame(frame)
                        return annotated_frame, expressions
                    except Exception as gpu_e:
                        import traceback
                        self.log(f"GPU情感识别处理错误 ({self.emotion_model_type}): {gpu_e}")
                        self.log(f"详细错误信息: {traceback.format_exc()}")
                        # 回退到简单模式
                        return self.process_simple_detection(frame)
                else:
                    # 如果GPU检测器未初始化，尝试创建
                    try:
                        from src.face.gpu_emotion_detector import GPUEmotionDetector
                        self.gpu_detector = GPUEmotionDetector(model_type=self.emotion_model_type, device='auto')
                        self.log(f"成功初始化GPU情感检测器: {self.emotion_model_type}")
                        annotated_frame, expressions = self.gpu_detector.process_frame(frame)
                        return annotated_frame, expressions
                    except Exception as init_e:
                        import traceback
                        self.log(f"GPU情感检测器初始化失败 ({self.emotion_model_type}): {init_e}")
                        self.log(f"详细错误信息: {traceback.format_exc()}")
                        self.log("回退到简单模式")
                        return self.process_simple_detection(frame)
            
        except Exception as e:
            self.log(f"面部识别处理错误: {e}")
        
        return frame, expressions
    
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
            self.log(f"简单面部检测错误: {e}")
        
        return frame, expressions
    
    def stop_camera_only(self):
        """只停止摄像头"""
        try:
            self.log("正在停止摄像头...")
            self.camera_running = False
            
            # 同时停止面部识别
            if self.face_detection_running:
                self.face_detection_running = False
                self.face_detection_btn.config(text=self.get_text("start_face_detection"), state="disabled")
            
            # 等待线程结束
            if self.camera_thread and self.camera_thread.is_alive():
                self.camera_thread.join(timeout=2)
            
            # 释放摄像头
            if self.camera:
                self.camera.release()
                self.camera = None
            
            # 释放GPU检测器资源
            if hasattr(self, 'gpu_detector') and self.gpu_detector is not None:
                try:
                    self.gpu_detector.release()
                    self.gpu_detector = None
                    self.log("GPU情感检测器资源已释放")
                except Exception as e:
                    self.log(f"释放GPU检测器资源时出错: {e}")
            
            # 更新UI
            self.camera_start_btn.config(text=self.get_text("start_camera"))
            self.capture_btn.config(state="disabled")
            self.save_expression_btn.config(state="disabled")
            self.video_label.config(image="", text=self.get_text("click_to_start"))
            
            self.log(self.get_text("camera_stopped"))
            
        except Exception as e:
            self.log(f"停止摄像头错误: {e}")
    
    def stop_face_detection(self):
        """停止面部识别"""
        try:
            self.face_detection_running = False
            self.face_detection_btn.config(text="启动面部识别")
            self.log("面部识别已停止")
            
        except Exception as e:
            self.log(f"停止面部识别错误: {e}")
    
    
    def update_video_display(self, photo):
        """更新视频显示（在主线程中调用）"""
        try:
            if self.camera_running and photo:
                self.video_label.config(image=photo, text="")
                self.video_label.image = photo  # 保持引用防止垃圾回收
            else:
                self.log("显示更新失败: 摄像头未运行或照片为空")
        except Exception as e:
            self.log(f"更新显示错误: {e}")
            print(f"更新显示错误: {e}")
    
    
    def _update_expression_display(self, expressions):
        """更新表情显示（在主线程中调用）"""
        try:
            for expr_name, value in expressions.items():
                if expr_name in self.expression_labels:
                    # 更新数值显示
                    self.expression_labels[expr_name].config(text=f"{value:.2f}")
                    
                    # 更新进度条
                    progress_value = min(100, max(0, value * 100))
                    self.expression_progress_bars[expr_name]['value'] = progress_value
            
            # 更新整体情感状态
            self._update_overall_status(expressions)
            
            # 发送表情数据到VRChat OSC（如果连接已建立）
            self.send_expressions_to_vrchat(expressions)
            
        except Exception as e:
            print(f"更新表情显示错误: {e}")
    
    def _update_overall_status(self, expressions):
        """更新整体情感状态显示"""
        try:
            if hasattr(self, 'overall_status_label') and hasattr(self, 'overall_status_progress'):
                # 找出最强的情感（排除中立）
                non_neutral_expressions = {k: v for k, v in expressions.items() if k != 'neutral'}
                
                if non_neutral_expressions:
                    # 获取最强情感
                    dominant_emotion = max(non_neutral_expressions.items(), key=lambda x: x[1])
                    emotion_name, intensity = dominant_emotion
                    
                    # 如果最强情感的强度很低，显示中立状态
                    if intensity < 0.1:
                        display_name = self.get_text("neutral")
                        display_intensity = expressions.get('neutral', 0.0)
                    else:
                        # 情感名称映射
                        emotion_names = {
                            'angry': '愤怒',
                            'disgust': '厌恶',
                            'fear': '恐惧',
                            'happy': '高兴',
                            'sad': '伤心',
                            'surprise': '惊讶',
                            'neutral': '中立'
                        }
                        display_name = emotion_names.get(emotion_name, emotion_name)
                        display_intensity = intensity
                else:
                    # 所有情感都为0，显示中立
                    display_name = self.get_text("neutral")
                    display_intensity = expressions.get('neutral', 0.0)
                
                # 更新显示
                self.overall_status_label.config(text=f"{display_name} ({display_intensity:.2f})")
                progress_value = min(100, max(0, display_intensity * 100))
                self.overall_status_progress['value'] = progress_value
                
        except Exception as e:
            print(f"更新整体状态错误: {e}")
    
    def send_expressions_to_vrchat(self, expressions):
        """将表情数据发送到VRChat OSC"""
        try:
            if self.client and self.is_connected and hasattr(self.client, 'osc_client'):
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
                        self.client.osc_client.send_parameter(param_address, clamped_value)
                        
        except Exception as e:
            # 静默处理错误，避免日志过多
            import time
            current_time = time.time()
            if hasattr(self, 'last_expression_error_time'):
                # 只每10秒记录一次错误
                if current_time - self.last_expression_error_time > 10:
                    self.log(f"表情数据发送错误: {e}")
                    self.last_expression_error_time = current_time
            else:
                self.last_expression_error_time = current_time
                self.log(f"表情数据发送错误: {e}")
    
    def capture_screenshot(self):
        """截图功能"""
        try:
            if self.current_frame is not None:
                # 生成文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"face_capture_{timestamp}.png"
                
                # 保存截图
                cv2.imwrite(filename, self.current_frame)
                
                messagebox.showinfo("截图成功", f"截图已保存为: {filename}")
                self.log(f"截图已保存: {filename}")
            else:
                messagebox.showwarning("警告", "没有可用的画面进行截图")
                
        except Exception as e:
            messagebox.showerror("截图错误", f"截图失败: {e}")
            self.log(f"截图错误: {e}")
    
    def save_expression_data(self):
        """保存当前表情数据"""
        try:
            # 生成文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"expression_data_{timestamp}.txt"
            
            # 保存表情数据
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("VRChat OSC 表情数据导出\n")
                f.write(f"时间戳: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 40 + "\n\n")
                
                f.write("当前表情参数:\n")
                for expr_name, value in self.expressions.items():
                    display_name = {
                        'angry': '愤怒',
                        'disgust': '厌恶',
                        'fear': '恐惧', 
                        'happy': '高兴',
                        'sad': '伤心',
                        'surprise': '惊讶',
                        'neutral': '中立'
                    }.get(expr_name, expr_name)
                    
                    f.write(f"  {display_name}: {value:.3f}\n")
                
                f.write("\nVRChat OSC 参数地址:\n")
                vrchat_params = {
                    'angry': '/avatar/parameters/FaceAngry',
                    'disgust': '/avatar/parameters/FaceDisgust',
                    'fear': '/avatar/parameters/FaceFear',
                    'happy': '/avatar/parameters/FaceHappy',
                    'sad': '/avatar/parameters/FaceSad',
                    'surprise': '/avatar/parameters/FaceSurprise',
                    'neutral': '/avatar/parameters/FaceNeutral'
                }
                
                for expr_name, value in self.expressions.items():
                    if expr_name in vrchat_params:
                        param_address = vrchat_params[expr_name]
                        f.write(f"  {param_address}: {value:.3f}\n")
            
            messagebox.showinfo("保存成功", f"表情数据已保存到: {filename}")
            self.log(f"表情数据已保存: {filename}")
            
        except Exception as e:
            messagebox.showerror("保存错误", f"保存表情数据失败: {e}")
            self.log(f"保存表情数据错误: {e}")
    
    def open_camera_window(self):
        """打开摄像头窗口（保留原功能作为备选）"""
        try:
            from .camera_window import CameraWindow
            CameraWindow(self.root)
        except Exception as e:
            messagebox.showerror("摄像头错误", f"无法打开摄像头窗口: {e}")
            self.log(f"打开摄像头窗口失败: {e}")
    
    def init_voicevox(self):
        """初始化VOICEVOX客户端"""
        def init_in_background():
            try:
                self.voicevox_client = get_voicevox_client()
                if self.voicevox_client.test_connection():
                    self.voicevox_connected = True
                    # 获取角色列表
                    speakers_list = self.voicevox_client.get_speakers_list()
                    speaker_names = [speaker['display'] for speaker in speakers_list]
                    
                    # 更新UI（必须在主线程中执行）
                    self.root.after(0, lambda: self.update_voicevox_ui(speaker_names, True))
                    self.log("VOICEVOX连接成功")
                else:
                    self.root.after(0, lambda: self.update_voicevox_ui([], False))
                    self.log("VOICEVOX连接失败")
            except Exception as e:
                self.log(f"初始化VOICEVOX失败: {e}")
                self.root.after(0, lambda: self.update_voicevox_ui([], False))
        
        # 在后台线程中初始化，避免阻塞UI
        threading.Thread(target=init_in_background, daemon=True).start()
    
    def update_voicevox_ui(self, speaker_names, connected):
        """更新VOICEVOX UI状态"""
        try:
            if connected:
                # 连接成功时，更新Avatar控制器的VOICEVOX客户端
                self.avatar_controller.set_voicevox_client(self.voicevox_client)
                
                # 初始化单AI角色管理器
                self.init_single_ai_manager()
                
                # 初始化期数选择为1期，并加载对应角色
                current_period = self.voicevox_period_var.get()
                period_speakers = self.voicevox_client.get_speakers_by_period(current_period)
                
                if period_speakers:
                    speaker_values = [speaker['display'] for speaker in period_speakers]
                    self.voicevox_character_combo['values'] = speaker_values
                    # 设置默认角色
                    if "ずんだもん - ノーマル" in speaker_values:
                        self.voicevox_character_combo.set("ずんだもん - ノーマル")
                    else:
                        self.voicevox_character_combo.set(speaker_values[0])
                else:
                    self.voicevox_character_combo['values'] = []
                    
                self.voicevox_status_label.config(text="已连接", foreground="green")
                self.voicevox_test_btn.config(state="normal")
            else:
                self.voicevox_character_combo['values'] = []
                self.voicevox_status_label.config(text="未连接", foreground="red")  
                self.voicevox_test_btn.config(state="disabled")
        except Exception as e:
            self.log(f"更新VOICEVOX UI失败: {e}")
    
    def on_voicevox_character_changed(self, event=None):
        """VOICEVOX角色选择变化时的回调"""
        if not self.voicevox_client or not self.voicevox_connected:
            return
            
        try:
            selected_display = self.voicevox_character_var.get()
            speakers_list = self.voicevox_client.get_speakers_list()
            
            # 找到对应的角色信息
            for speaker in speakers_list:
                if speaker['display'] == selected_display:
                    self.voicevox_client.set_speaker(
                        speaker['speaker_id'], 
                        speaker['name'], 
                        speaker['style']
                    )
                    self.log(f"切换VOICEVOX角色: {selected_display}")
                    break
        except Exception as e:
            self.log(f"切换VOICEVOX角色失败: {e}")
    
    def on_voicevox_period_changed(self, event=None):
        """VOICEVOX期数选择变化时的回调"""
        if not self.voicevox_client or not self.voicevox_connected:
            return
            
        try:
            selected_period = self.voicevox_period_var.get()
            # 获取指定期数的角色列表
            period_speakers = self.voicevox_client.get_speakers_by_period(selected_period)
            
            # 更新角色选择框
            if period_speakers:
                speaker_values = [speaker['display'] for speaker in period_speakers]
                self.voicevox_character_combo['values'] = speaker_values
                # 默认选择第一个角色
                self.voicevox_character_combo.set(speaker_values[0])
                
                # 自动设置第一个角色
                first_speaker = period_speakers[0]
                self.voicevox_client.set_speaker(
                    first_speaker['speaker_id'],
                    first_speaker['name'],
                    first_speaker['style']
                )
                self.log(f"切换到{selected_period}，角色: {speaker_values[0]}")
            else:
                self.voicevox_character_combo['values'] = []
                self.voicevox_character_combo.set("")
                self.log(f"未找到{selected_period}的角色")
                
        except Exception as e:
            self.log(f"切换VOICEVOX期数失败: {e}")
    
    def on_speed_changed(self, value):
        """语速滑块变化回调"""
        speed_value = float(value)
        self.speed_label.config(text=f"{speed_value:.2f}")
        if self.voicevox_client:
            self.voicevox_client.set_voice_parameters(speed_scale=speed_value)
    
    def on_pitch_changed(self, value):
        """音高滑块变化回调"""
        pitch_value = float(value)
        self.pitch_label.config(text=f"{pitch_value:.3f}")
        if self.voicevox_client:
            self.voicevox_client.set_voice_parameters(pitch_scale=pitch_value)
    
    def on_intonation_changed(self, value):
        """抑扬顿挫滑块变化回调"""
        intonation_value = float(value)
        self.intonation_label.config(text=f"{intonation_value:.2f}")
        if self.voicevox_client:
            self.voicevox_client.set_voice_parameters(intonation_scale=intonation_value)
    
    def on_volume_changed(self, value):
        """音量滑块变化回调"""
        volume_value = float(value)
        self.volume_label.config(text=f"{volume_value:.2f}")
        if self.voicevox_client:
            self.voicevox_client.set_voice_parameters(volume_scale=volume_value)

    def test_voicevox(self):
        """测试VOICEVOX语音合成"""
        if not self.voicevox_client or not self.voicevox_connected:
            messagebox.showwarning("警告", "VOICEVOX未连接")
            return
            
        # 根据当前角色选择测试文本
        current_speaker = self.voicevox_client.get_current_speaker_info()
        
        if "ずんだもん" in current_speaker['name']:
            test_text = "こんにちは！ずんだもんなのだ！"
        elif "四国めたん" in current_speaker['name']:
            test_text = "こんにちは、四国めたんです！"
        else:
            test_text = "こんにちは！VOICEVOX音声合成のテストです。"
        
        def test_in_background():
            try:
                # 分析文本情感并设置Avatar表情
                if self.avatar_controller.is_avatar_connected():
                    emotion = self.avatar_controller.analyze_text_emotion(test_text)
                    self.avatar_controller.start_speaking(test_text, emotion, voice_level=0.8)
                    self.log(f"设置Avatar表情: {emotion}")
                
                success = self.voicevox_client.synthesize_and_play(test_text)
                
                if success:
                    self.log(f"VOICEVOX语音测试成功: {test_text}")
                else:
                    self.log("VOICEVOX语音测试失败")
                    
                # 语音播放完成后停止Avatar说话状态
                if self.avatar_controller.is_avatar_connected():
                    # 延迟一点时间让语音播放完
                    def stop_speaking():
                        self.avatar_controller.stop_speaking()
                    self.root.after(3000, stop_speaking)  # 3秒后停止
                    
            except Exception as e:
                self.log(f"VOICEVOX语音测试出错: {e}")
                # 出错时也要重置Avatar状态
                if self.avatar_controller.is_avatar_connected():
                    self.avatar_controller.stop_speaking()
        
        threading.Thread(target=test_in_background, daemon=True).start()
    
    def synthesize_with_voicevox(self, text):
        """使用VOICEVOX合成并播放文本（用于LLM输出）"""
        if not self.voicevox_enabled_var.get() or not self.voicevox_client or not self.voicevox_connected:
            return False
            
        def synthesize_in_background():
            try:
                # 分析文本情感并设置Avatar表情和语音状态
                if self.avatar_controller.is_avatar_connected():
                    emotion = self.avatar_controller.analyze_text_emotion(text)
                    self.avatar_controller.start_speaking(text, emotion, voice_level=0.8)
                    self.log(f"Avatar开始说话 - 表情: {emotion}, 文本: {text[:30]}...")
                
                success = self.voicevox_client.synthesize_and_play(text)
                
                if success:
                    self.log(f"VOICEVOX语音合成: {text[:50]}...")
                    
                    # 估算语音播放时长（简单估算：每个字符约0.15秒）
                    estimated_duration = len(text) * 150  # 毫秒
                    min_duration = 2000  # 最少2秒
                    max_duration = 8000  # 最多8秒
                    duration = max(min_duration, min(estimated_duration, max_duration))
                    
                    # 语音播放完成后停止Avatar说话状态
                    if self.avatar_controller.is_avatar_connected():
                        def stop_speaking():
                            self.avatar_controller.stop_speaking()
                            self.log("Avatar停止说话")
                        self.root.after(duration, stop_speaking)
                else:
                    self.log("VOICEVOX语音合成失败")
                    # 失败时立即重置Avatar状态
                    if self.avatar_controller.is_avatar_connected():
                        self.avatar_controller.stop_speaking()
                        
            except Exception as e:
                self.log(f"VOICEVOX语音合成出错: {e}")
                # 出错时也要重置Avatar状态
                if self.avatar_controller.is_avatar_connected():
                    self.avatar_controller.stop_speaking()
        
        threading.Thread(target=synthesize_in_background, daemon=True).start()
        return True
    
    def init_llm_handler(self):
        """初始化LLM处理器"""
        def init_in_background():
            try:
                self.llm_handler = VoiceLLMHandler(config=self.config)
                
                # 设置LLM响应回调
                self.llm_handler.set_response_callback(self.on_llm_response)
                
                if self.llm_handler.is_client_ready():
                    # 启动处理器
                    self.llm_handler.start_processing()
                    self.log("LLM处理器初始化成功")
                else:
                    self.log("LLM处理器初始化失败：客户端未就绪")
                    
            except Exception as e:
                self.log(f"初始化LLM处理器失败: {e}")
        
        # 在后台线程中初始化
        threading.Thread(target=init_in_background, daemon=True).start()
    
    def on_llm_response(self, response: VoiceLLMResponse):
        """处理LLM响应"""
        def update_ui():
            if response.success:
                # 显示LLM回复在语音识别框中
                self.add_speech_output(response.llm_response, "AI回复")
                
                # 发送到VRChat聊天框
                self.client.send_text_message(f"[AI] {response.llm_response}")
                
                # 使用VOICEVOX合成语音
                self.synthesize_with_voicevox(response.llm_response)
                
                self.log(f"LLM响应: {response.llm_response[:100]}...")
            else:
                self.log(f"LLM处理失败: {response.error}")
        
        # 在主线程中更新UI
        self.root.after(0, update_ui)
    
    def toggle_llm_enabled(self):
        """切换LLM启用状态"""
        self.llm_enabled = self.llm_enabled_var.get()
        status = "启用" if self.llm_enabled else "禁用"
        self.log(f"AI对话功能已{status}")
    
    def open_character_management(self):
        """打开角色管理窗口"""
        if self.character_window is not None and self.character_window.winfo_exists():
            self.character_window.lift()
            self.character_window.focus()
            return
        
        self.character_window = tk.Toplevel(self.root)
        self.character_window.title(self.get_text("character_management"))
        self.character_window.geometry("500x400")
        self.character_window.resizable(True, True)
        
        # 创建主框架
        main_frame = ttk.Frame(self.character_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 角色列表框架
        list_frame = ttk.LabelFrame(main_frame, text=self.get_text("character_management"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 角色列表
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        self.character_listbox = tk.Listbox(list_container)
        self.character_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.character_listbox.bind('<<ListboxSelect>>', self.on_character_select)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_container, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.character_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.character_listbox.yview)
        
        # 距离显示框架
        distance_frame = ttk.Frame(list_frame)
        distance_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.distance_label = ttk.Label(distance_frame, text=self.get_text("distance_tracking") + ": --")
        self.distance_label.pack(side=tk.LEFT)
        
        # 当前位置显示框架
        position_frame = ttk.Frame(list_frame)
        position_frame.pack(fill=tk.X, pady=(2, 0))
        
        self.position_label = ttk.Label(position_frame, text=f"当前位置: ({self.player_position['x']:.1f}, {self.player_position['y']:.1f}, {self.player_position['z']:.1f})")
        self.position_label.pack(side=tk.LEFT)
        
        # 添加角色框架
        add_frame = ttk.LabelFrame(main_frame, text=self.get_text("add_new_character"), padding="5")
        add_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 角色名称输入
        name_frame = ttk.Frame(add_frame)
        name_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(name_frame, text=self.get_text("character_name") + ":", width=12).pack(side=tk.LEFT)
        self.character_name_entry = ttk.Entry(name_frame)
        self.character_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # 坐标输入
        coord_frame = ttk.Frame(add_frame)
        coord_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(coord_frame, text=self.get_text("character_x") + ":", width=6).pack(side=tk.LEFT)
        self.character_x_entry = ttk.Entry(coord_frame, width=10)
        self.character_x_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Label(coord_frame, text=self.get_text("character_y") + ":", width=6).pack(side=tk.LEFT)
        self.character_y_entry = ttk.Entry(coord_frame, width=10)
        self.character_y_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Label(coord_frame, text=self.get_text("character_z") + ":", width=6).pack(side=tk.LEFT)
        self.character_z_entry = ttk.Entry(coord_frame, width=10)
        self.character_z_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # 按钮框架
        button_frame = ttk.Frame(add_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(button_frame, text=self.get_text("add_character"), 
                  command=self.add_character).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=self.get_text("update_position"), 
                  command=self.update_character_position).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="使用当前位置", 
                  command=self.use_current_position).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=self.get_text("remove_character"), 
                  command=self.remove_character).pack(side=tk.LEFT)
        
        # 刷新角色列表
        self.refresh_character_list()
        
        # 启动距离更新线程
        if not hasattr(self, 'distance_update_running'):
            self.distance_update_running = True
            threading.Thread(target=self.distance_update_loop, daemon=True).start()
    
    def refresh_character_list(self):
        """刷新角色列表"""
        if not hasattr(self, 'character_listbox'):
            return
            
        self.character_listbox.delete(0, tk.END)
        for name, pos in self.vrc_characters.items():
            distance = self.calculate_distance(self.player_position, pos)
            self.character_listbox.insert(tk.END, f"{name} - ({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f}) - {distance:.2f}m")
    
    def on_character_select(self, event):
        """角色选择事件"""
        selection = self.character_listbox.curselection()
        if not selection:
            return
        
        character_info = self.character_listbox.get(selection[0])
        character_name = character_info.split(" - ")[0]
        
        if character_name in self.vrc_characters:
            pos = self.vrc_characters[character_name]
            self.character_name_entry.delete(0, tk.END)
            self.character_name_entry.insert(0, character_name)
            
            self.character_x_entry.delete(0, tk.END)
            self.character_x_entry.insert(0, str(pos['x']))
            
            self.character_y_entry.delete(0, tk.END)
            self.character_y_entry.insert(0, str(pos['y']))
            
            self.character_z_entry.delete(0, tk.END)
            self.character_z_entry.insert(0, str(pos['z']))
            
            # 更新距离显示
            distance = self.calculate_distance(self.player_position, pos)
            self.distance_label.config(text=f"{self.get_text('distance_to').format(name=character_name)}: {distance:.2f}m")
    
    def add_character(self):
        """添加新角色"""
        try:
            name = self.character_name_entry.get().strip()
            if not name:
                messagebox.showwarning(self.get_text("warning"), self.get_text("character_name") + self.get_text("param_name_value_required"))
                return
            
            if self.avatar_controller.character_manager.character_exists(name):
                messagebox.showwarning(self.get_text("warning"), self.get_text("character_exists"))
                return
            
            x = float(self.character_x_entry.get() or 0)
            y = float(self.character_y_entry.get() or 0)
            z = float(self.character_z_entry.get() or 0)
            
            # 使用Avatar控制器添加角色
            success = self.avatar_controller.add_character(name, x, y, z)
            if success:
                self.refresh_character_list()  # 刷新窗口列表（如果存在）
                self.update_character_distance_display()  # 更新距离显示
            
            # 清空输入框
            self.character_name_entry.delete(0, tk.END)
            self.character_x_entry.delete(0, tk.END)
            self.character_y_entry.delete(0, tk.END)
            self.character_z_entry.delete(0, tk.END)
            
            messagebox.showinfo(self.get_text("success"), self.get_text("character_added"))
            self.log(f"{self.get_text('character_added')}: {name} ({x}, {y}, {z})")
            
        except ValueError:
            messagebox.showerror(self.get_text("error"), self.get_text("invalid_position"))
    
    def update_character_position(self):
        """更新角色位置"""
        try:
            name = self.character_name_entry.get().strip()
            if not name or name not in self.vrc_characters:
                messagebox.showwarning(self.get_text("warning"), self.get_text("character_name") + self.get_text("param_name_value_required"))
                return
            
            x = float(self.character_x_entry.get() or 0)
            y = float(self.character_y_entry.get() or 0)
            z = float(self.character_z_entry.get() or 0)
            
            self.vrc_characters[name] = {"x": x, "y": y, "z": z}
            self.save_character_data()  # 自动保存
            self.refresh_character_list()
            
            messagebox.showinfo(self.get_text("success"), self.get_text("update_position"))
            self.log(f"{self.get_text('character_name')} {name} {self.get_text('update_position')}: ({x}, {y}, {z})")
            
        except ValueError:
            messagebox.showerror(self.get_text("error"), self.get_text("invalid_position"))
    
    def remove_character(self):
        """删除角色"""
        name = self.character_name_entry.get().strip()
        if not name:
            messagebox.showwarning(self.get_text("warning"), self.get_text("select_character_to_remove"))
            return
        
        # 使用Avatar控制器删除角色
        success = self.avatar_controller.remove_character(name)
        if success:
            self.refresh_character_list()  # 刷新窗口列表（如果存在）
            self.update_character_distance_display()  # 更新距离显示
            
            # 清空输入框
            self.character_name_entry.delete(0, tk.END)
            self.character_x_entry.delete(0, tk.END)
            self.character_y_entry.delete(0, tk.END)
            self.character_z_entry.delete(0, tk.END)
            
            messagebox.showinfo(self.get_text("success"), self.get_text("character_removed"))
            self.log(f"{self.get_text('character_removed')}: {name}")
    
    def calculate_distance(self, pos1, pos2):
        """计算3D距离"""
        dx = pos1['x'] - pos2['x']
        dy = pos1['y'] - pos2['y']
        dz = pos1['z'] - pos2['z']
        return (dx*dx + dy*dy + dz*dz) ** 0.5
    
    def distance_update_loop(self):
        """距离更新循环"""
        while getattr(self, 'distance_update_running', False):
            try:
                # 模拟从VRChat OSC获取玩家位置
                # 在实际应用中，这里应该从OSC接收玩家位置数据
                if self.is_connected and hasattr(self, 'character_listbox'):
                    self.root.after(0, self.refresh_character_list)
                
                time.sleep(1)  # 每秒更新一次
            except Exception:
                break
    
    def update_player_position(self, x, y, z):
        """更新玩家位置（从OSC调用）"""
        # 更新Avatar控制器的位置（这会自动处理角色距离计算）
        self.avatar_controller.update_player_position(x, y, z)
        
        # 为了兼容性，也保持旧的变量
        self.player_position = {"x": x, "y": y, "z": z}
        
        # 更新主界面中的位置显示
        if hasattr(self, 'current_pos_label'):
            pos_text = f"({x:.2f}, {y:.2f}, {z:.2f})"
            self.root.after(0, lambda: self.current_pos_label.config(text=pos_text))
        
        # 更新主界面中的距离显示
        self.root.after(0, self.update_character_distance_display)
        
        # 更新角色管理窗口中的位置显示
        if hasattr(self, 'position_label'):
            self.root.after(0, lambda: self.position_label.config(
                text=f"当前位置: ({x:.1f}, {y:.1f}, {z:.1f})"
            ))
    
    def use_current_position(self):
        """使用当前位置填充坐标输入框"""
        # 从Avatar控制器获取当前位置
        current_pos = self.avatar_controller.get_player_position()
        
        self.character_x_entry.delete(0, tk.END)
        self.character_x_entry.insert(0, f"{current_pos['x']:.2f}")
        
        self.character_y_entry.delete(0, tk.END)
        self.character_y_entry.insert(0, f"{current_pos['y']:.2f}")
        
        self.character_z_entry.delete(0, tk.END)
        self.character_z_entry.insert(0, f"{current_pos['z']:.2f}")
    
    def update_character_distance_display(self):
        """更新角色距离显示"""
        if not hasattr(self, 'character_distance_text'):
            return
        
        try:
            # 使用Avatar控制器获取距离信息
            distance_text = self.avatar_controller.get_distance_text(max_count=8)  # 显示更多角色
            
            # 更新距离显示
            self.character_distance_text.config(state='normal')
            self.character_distance_text.delete(1.0, tk.END)
            self.character_distance_text.insert(tk.END, distance_text)
            self.character_distance_text.config(state='disabled')
        except Exception as e:
            if hasattr(self, 'log'):
                self.log(f"更新距离显示失败: {e}")
    
    def load_character_data(self):
        """加载角色数据"""
        try:
            import json
            import os
            
            # 创建数据目录
            os.makedirs(os.path.dirname(self.characters_file), exist_ok=True)
            
            if os.path.exists(self.characters_file):
                with open(self.characters_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.vrc_characters = data.get('characters', {})
                    self.player_position = data.get('player_position', {"x": 0.0, "y": 0.0, "z": 0.0})
                    
                    self.log(f"已加载{len(self.vrc_characters)}个角色数据")
                    
                    # 初始化角色距离显示
                    self.root.after(100, self.update_character_distance_display)
            else:
                # 创建空文件
                self.save_character_data()
                
        except Exception as e:
            self.log(f"加载角色数据失败: {e}")
    
    def save_character_data(self):
        """保存角色数据"""
        try:
            import json
            import os
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.characters_file), exist_ok=True)
            
            data = {
                'characters': self.vrc_characters,
                'player_position': self.player_position,
                'version': '1.0',
                'updated': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(self.characters_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            if hasattr(self, 'log'):
                self.log(f"已保存{len(self.vrc_characters)}个角色数据")
                
        except Exception as e:
            if hasattr(self, 'log'):
                self.log(f"保存角色数据失败: {e}")
    
    # === AI角色控制方法 ===
    
    def create_ai_character(self):
        """创建AI角色"""
        name = self.new_ai_name_entry.get().strip()
        personality = self.ai_personality_var.get()
        
        if not name:
            messagebox.showwarning("警告", "请输入AI角色名称")
            return
        
        if not self.avatar_controller:
            messagebox.showerror("错误", "Avatar控制器未初始化")
            return
        
        try:
            success = self.avatar_controller.create_ai_character(name, personality)
            if success:
                messagebox.showinfo("成功", f"AI角色 '{name}' 创建成功")
                self.new_ai_name_entry.delete(0, tk.END)
                self.refresh_ai_character_list()
                self.log(f"创建AI角色: {name} (人格: {personality})")
            else:
                messagebox.showerror("错误", f"创建AI角色失败 - 角色名称可能已存在")
        except Exception as e:
            messagebox.showerror("错误", f"创建AI角色时出错: {e}")
            self.log(f"创建AI角色错误: {e}")
    
    def toggle_ai_character(self):
        """激活/停用AI角色"""
        selected_name = self.ai_character_var.get().strip()
        
        if not selected_name:
            messagebox.showwarning("警告", "请选择一个AI角色")
            return
        
        if not self.avatar_controller:
            messagebox.showerror("错误", "Avatar控制器未初始化")
            return
        
        try:
            # 检查当前是否有激活的AI角色
            current_active = self.avatar_controller.get_active_ai_character()
            
            if current_active == selected_name:
                # 停用当前角色
                success = self.avatar_controller.deactivate_ai_character()
                if success:
                    messagebox.showinfo("成功", f"已停用AI角色 '{selected_name}'")
                    self.log(f"停用AI角色: {selected_name}")
                else:
                    messagebox.showerror("错误", "停用AI角色失败")
            else:
                # 激活选中的角色
                success = self.avatar_controller.activate_ai_character(selected_name)
                if success:
                    messagebox.showinfo("成功", f"已激活AI角色 '{selected_name}'")
                    self.log(f"激活AI角色: {selected_name}")
                else:
                    messagebox.showerror("错误", "激活AI角色失败")
            
            # 更新状态显示
            self.update_ai_character_status()
            
        except Exception as e:
            messagebox.showerror("错误", f"切换AI角色状态时出错: {e}")
            self.log(f"切换AI角色状态错误: {e}")
    
    def delete_ai_character(self):
        """删除AI角色"""
        selected_name = self.ai_character_var.get().strip()
        
        if not selected_name:
            messagebox.showwarning("警告", "请选择要删除的AI角色")
            return
        
        # 确认删除
        result = messagebox.askyesno("确认删除", f"确定要删除AI角色 '{selected_name}' 吗？")
        if not result:
            return
        
        if not self.avatar_controller:
            messagebox.showerror("错误", "Avatar控制器未初始化")
            return
        
        try:
            success = self.avatar_controller.remove_ai_character(selected_name)
            if success:
                messagebox.showinfo("成功", f"已删除AI角色 '{selected_name}'")
                self.refresh_ai_character_list()
                self.update_ai_character_status()
                self.log(f"删除AI角色: {selected_name}")
            else:
                messagebox.showerror("错误", "删除AI角色失败")
        except Exception as e:
            messagebox.showerror("错误", f"删除AI角色时出错: {e}")
            self.log(f"删除AI角色错误: {e}")
    
    def ai_greet(self):
        """让AI角色打招呼"""
        if not self.avatar_controller:
            messagebox.showerror("错误", "Avatar控制器未初始化")
            return
        
        if not self.avatar_controller.has_active_ai_character():
            messagebox.showwarning("警告", "没有激活的AI角色")
            return
        
        try:
            success = self.avatar_controller.make_ai_character_greet()
            if success:
                active_name = self.avatar_controller.get_active_ai_character()
                self.log(f"AI角色 '{active_name}' 执行打招呼")
            else:
                messagebox.showerror("错误", "AI角色打招呼失败")
        except Exception as e:
            messagebox.showerror("错误", f"AI角色打招呼时出错: {e}")
            self.log(f"AI角色打招呼错误: {e}")
    
    def ai_speak_custom(self):
        """让AI角色说自定义内容"""
        text = self.ai_speak_entry.get().strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入要说的内容")
            return
        
        if not self.avatar_controller:
            messagebox.showerror("错误", "Avatar控制器未初始化")
            return
        
        if not self.avatar_controller.has_active_ai_character():
            messagebox.showwarning("警告", "没有激活的AI角色")
            return
        
        try:
            success = self.avatar_controller.make_ai_character_speak(text)
            if success:
                active_name = self.avatar_controller.get_active_ai_character()
                self.log(f"AI角色 '{active_name}' 说话: {text}")
                self.ai_speak_entry.delete(0, tk.END)  # 清空输入框
            else:
                messagebox.showerror("错误", "AI角色说话失败")
        except Exception as e:
            messagebox.showerror("错误", f"AI角色说话时出错: {e}")
            self.log(f"AI角色说话错误: {e}")
    
    def refresh_ai_character_list(self):
        """刷新AI角色列表"""
        if not self.avatar_controller:
            return
        
        try:
            # 获取所有AI角色名称
            ai_characters = self.avatar_controller.get_ai_characters()
            
            # 更新下拉框选项
            self.ai_character_combo['values'] = ai_characters
            
            # 如果当前选中的角色不在列表中，清空选择
            current_selection = self.ai_character_var.get()
            if current_selection not in ai_characters:
                self.ai_character_var.set("")
            
            # 更新状态显示
            self.update_ai_character_status()
            
        except Exception as e:
            self.log(f"刷新AI角色列表错误: {e}")
    
    def update_ai_character_status(self):
        """更新AI角色状态显示"""
        if not hasattr(self, 'active_ai_label') or not self.avatar_controller:
            return
        
        try:
            active_name = self.avatar_controller.get_active_ai_character()
            
            if active_name:
                status_text = f"当前激活: {active_name}"
                self.active_ai_label.config(text=status_text, foreground="green")
                
                # 更新按钮文本
                if hasattr(self, 'activate_ai_btn'):
                    self.activate_ai_btn.config(text="停用")
                    
                # 启用行为控制按钮
                if hasattr(self, 'ai_greet_btn'):
                    self.ai_greet_btn.config(state="normal")
                if hasattr(self, 'ai_speak_btn'):
                    self.ai_speak_btn.config(state="normal")
                if hasattr(self, 'ai_speak_entry'):
                    self.ai_speak_entry.config(state="normal")
            else:
                status_text = "当前激活: 无"
                self.active_ai_label.config(text=status_text, foreground="red")
                
                # 更新按钮文本
                if hasattr(self, 'activate_ai_btn'):
                    self.activate_ai_btn.config(text="激活")
                    
                # 禁用行为控制按钮
                if hasattr(self, 'ai_greet_btn'):
                    self.ai_greet_btn.config(state="disabled")
                if hasattr(self, 'ai_speak_btn'):
                    self.ai_speak_btn.config(state="disabled")
                if hasattr(self, 'ai_speak_entry'):
                    self.ai_speak_entry.config(state="disabled")
                    
        except Exception as e:
            self.log(f"更新AI角色状态显示错误: {e}")
    
    def init_single_ai_manager(self):
        """初始化单AI角色管理器"""
        try:
            if not self.single_ai_manager:
                self.single_ai_manager = SingleAIVRCManager(voicevox_client=self.voicevox_client)
                
                # 设置状态回调函数
                self.single_ai_manager.set_status_callback(self.on_ai_status_change)
                
                self.log("单AI角色管理器初始化成功")
                
                # 刷新AI角色界面状态
                self.update_ai_character_status()
            else:
                # 更新现有管理器的VOICEVOX客户端
                self.single_ai_manager.update_voicevox_client(self.voicevox_client)
                
        except Exception as e:
            self.log(f"初始化单AI角色管理器失败: {e}")
    
    def on_ai_status_change(self, event_type: str, data: dict):
        """AI状态变化回调"""
        if event_type == "vrc_connected":
            self.root.after(0, lambda: self.ai_osc_status_label.config(text="已连接", foreground="green"))
            self.root.after(0, lambda: self.ai_osc_connect_btn.config(text="断开连接"))
            self.log("AI角色VRC连接成功")
        elif event_type == "vrc_disconnected":
            self.root.after(0, lambda: self.ai_osc_status_label.config(text="未连接", foreground="red"))
            self.root.after(0, lambda: self.ai_osc_connect_btn.config(text="连接VRC"))
            self.log("AI角色VRC连接断开")
        elif event_type == "ai_character_created":
            self.log(f"AI角色创建成功: {data.get('name')} (人格: {data.get('personality')})")
        elif event_type == "ai_activated":
            self.log(f"AI角色激活: {data.get('name')}")
        elif event_type == "ai_deactivated":
            self.log(f"AI角色停用: {data.get('name')}")
        
        # 更新界面状态
        self.root.after(0, self.update_ai_character_status)
    
    def on_voice_queue_status_change(self, event_type: str, item):
        """语音队列状态变化回调"""
        if event_type == "item_added":
            self.log(f"语音已添加到队列: {item.text[:30]}...")
        elif event_type == "processing":
            self.log(f"正在处理语音: {item.text[:30]}...")
        elif event_type == "completed":
            self.log(f"语音处理完成: {item.text[:30]}...")
        elif event_type == "error":
            self.log(f"语音处理失败: {item.text[:30]}...")
        
        # 更新语音队列显示
        self.root.after(0, self.update_voice_queue_display)
    
    # === 单AI角色控制方法 ===
    
    def create_ai_character(self):
        """创建AI角色"""
        name = self.new_ai_name_entry.get().strip()
        personality = self.ai_personality_var.get()
        
        if not name:
            messagebox.showwarning("警告", "请输入AI角色名称")
            return
        
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化，请先连接VOICEVOX")
            return
        
        try:
            from src.avatar.ai_character import AIPersonality
            personality_enum = AIPersonality(personality)
            
            success = self.single_ai_manager.create_ai_character(name, personality_enum)
            
            if success:
                messagebox.showinfo("成功", 
                    f"AI角色 '{name}' 创建成功！\n\n"
                    f"人格类型: {personality}\n\n"
                    "接下来请连接VRC来激活AI角色"
                )
                self.new_ai_name_entry.delete(0, tk.END)
                self.update_ai_character_status()
                self.log(f"创建AI角色: {name} (人格: {personality})")
            else:
                messagebox.showerror("错误", "创建AI角色失败")
        except Exception as e:
            messagebox.showerror("错误", f"创建AI角色时出错: {e}")
            self.log(f"创建AI角色错误: {e}")
    
    def toggle_multi_ai_character(self):
        """激活/停用多实例AI角色"""
        selected_name = self.ai_character_var.get().strip()
        
        if not selected_name:
            messagebox.showwarning("警告", "请选择一个AI角色")
            return
        
        if not self.multi_ai_manager:
            messagebox.showerror("错误", "多实例AI管理器未初始化")
            return
        
        try:
            # 获取角色状态
            status = self.multi_ai_manager.get_character_status(selected_name)
            is_active = status.get("ai_active", False)
            
            if is_active:
                # 停用角色
                success = self.multi_ai_manager.deactivate_ai_character(selected_name)
                if success:
                    messagebox.showinfo("成功", f"已停用AI角色 '{selected_name}'")
                    self.log(f"停用多实例AI角色: {selected_name}")
                else:
                    messagebox.showerror("错误", "停用AI角色失败")
            else:
                # 激活角色（会自动启动VRC实例如果需要的话）
                success = self.multi_ai_manager.activate_ai_character(selected_name)
                if success:
                    messagebox.showinfo("成功", 
                        f"已激活AI角色 '{selected_name}'\n\n"
                        "AI角色现在可以自动说话和做表情了！\n"
                        "如果VRChat实例还没启动，系统会自动启动它。"
                    )
                    self.log(f"激活多实例AI角色: {selected_name}")
                else:
                    messagebox.showerror("错误", "激活AI角色失败，请检查VRChat实例状态")
            
            # 更新状态显示
            self.update_multi_ai_character_status()
            
        except Exception as e:
            messagebox.showerror("错误", f"切换AI角色状态时出错: {e}")
            self.log(f"切换多实例AI角色状态错误: {e}")
    
    def delete_multi_ai_character(self):
        """删除多实例AI角色"""
        selected_name = self.ai_character_var.get().strip()
        
        if not selected_name:
            messagebox.showwarning("警告", "请选择要删除的AI角色")
            return
        
        # 确认删除
        result = messagebox.askyesno(
            "确认删除", 
            f"确定要删除AI角色 '{selected_name}' 吗？\n\n"
            "这将同时删除：\n"
            "• AI角色和其行为逻辑\n"
            "• 对应的VRChat实例配置\n"
            "• 正在运行的VRChat客户端进程\n\n"
            "此操作无法撤销！"
        )
        if not result:
            return
        
        if not self.multi_ai_manager:
            messagebox.showerror("错误", "多实例AI管理器未初始化")
            return
        
        try:
            success = self.multi_ai_manager.remove_ai_character(selected_name)
            if success:
                messagebox.showinfo("成功", f"已完全删除AI角色 '{selected_name}' 及其VRChat实例")
                self.refresh_multi_ai_character_list()
                self.update_multi_ai_character_status()
                self.log(f"删除多实例AI角色: {selected_name}")
            else:
                messagebox.showerror("错误", "删除AI角色失败")
        except Exception as e:
            messagebox.showerror("错误", f"删除AI角色时出错: {e}")
            self.log(f"删除多实例AI角色错误: {e}")
    
    def multi_ai_greet(self):
        """让多实例AI角色打招呼"""
        selected_name = self.ai_character_var.get().strip()
        
        if not selected_name:
            messagebox.showwarning("警告", "请选择一个AI角色")
            return
        
        if not self.multi_ai_manager:
            messagebox.showerror("错误", "多实例AI管理器未初始化")
            return
        
        try:
            success = self.multi_ai_manager.make_character_greet(selected_name)
            if success:
                self.log(f"多实例AI角色 '{selected_name}' 执行打招呼")
            else:
                messagebox.showwarning("警告", f"AI角色 '{selected_name}' 未激活或执行失败")
        except Exception as e:
            messagebox.showerror("错误", f"AI角色打招呼时出错: {e}")
            self.log(f"多实例AI角色打招呼错误: {e}")
    
    def multi_ai_speak_custom(self):
        """让多实例AI角色说自定义内容"""
        selected_name = self.ai_character_var.get().strip()
        text = self.ai_speak_entry.get().strip()
        
        if not selected_name:
            messagebox.showwarning("警告", "请选择一个AI角色")
            return
        
        if not text:
            messagebox.showwarning("警告", "请输入要说的内容")
            return
        
        if not self.multi_ai_manager:
            messagebox.showerror("错误", "多实例AI管理器未初始化")
            return
        
        try:
            success = self.multi_ai_manager.make_character_speak(selected_name, text)
            if success:
                self.log(f"多实例AI角色 '{selected_name}' 说话: {text}")
                self.ai_speak_entry.delete(0, tk.END)  # 清空输入框
            else:
                messagebox.showwarning("警告", f"AI角色 '{selected_name}' 未激活或执行失败")
        except Exception as e:
            messagebox.showerror("错误", f"AI角色说话时出错: {e}")
            self.log(f"多实例AI角色说话错误: {e}")
    
    def refresh_multi_ai_character_list(self):
        """刷新多实例AI角色列表"""
        if not self.multi_ai_manager:
            return
        
        try:
            # 获取所有AI角色名称
            ai_characters = self.multi_ai_manager.get_ai_character_names()
            
            # 更新下拉框选项
            self.ai_character_combo['values'] = ai_characters
            
            # 如果当前选中的角色不在列表中，清空选择
            current_selection = self.ai_character_var.get()
            if current_selection not in ai_characters:
                self.ai_character_var.set("")
            
            # 更新状态显示
            self.update_multi_ai_character_status()
            
        except Exception as e:
            self.log(f"刷新多实例AI角色列表错误: {e}")
    
    def update_multi_ai_character_status(self):
        """更新多实例AI角色状态显示"""
        if not hasattr(self, 'active_ai_label') or not self.multi_ai_manager:
            return
        
        try:
            selected_name = self.ai_character_var.get().strip()
            
            if selected_name:
                status = self.multi_ai_manager.get_character_status(selected_name)
                is_active = status.get("ai_active", False)
                vrc_status = status.get("vrc_instance", {}).get("status", "unknown")
                
                if is_active:
                    status_text = f"当前选择: {selected_name} (已激活, VRC: {vrc_status})"
                    self.active_ai_label.config(text=status_text, foreground="green")
                    
                    # 更新按钮文本
                    if hasattr(self, 'activate_ai_btn'):
                        self.activate_ai_btn.config(text="停用")
                        
                    # 启用行为控制按钮
                    if hasattr(self, 'ai_greet_btn'):
                        self.ai_greet_btn.config(state="normal")
                    if hasattr(self, 'ai_speak_btn'):
                        self.ai_speak_btn.config(state="normal")
                    if hasattr(self, 'ai_speak_entry'):
                        self.ai_speak_entry.config(state="normal")
                else:
                    status_text = f"当前选择: {selected_name} (未激活, VRC: {vrc_status})"
                    self.active_ai_label.config(text=status_text, foreground="orange")
                    
                    # 更新按钮文本
                    if hasattr(self, 'activate_ai_btn'):
                        self.activate_ai_btn.config(text="激活")
                        
                    # 禁用行为控制按钮
                    if hasattr(self, 'ai_greet_btn'):
                        self.ai_greet_btn.config(state="disabled")
                    if hasattr(self, 'ai_speak_btn'):
                        self.ai_speak_btn.config(state="disabled")
                    if hasattr(self, 'ai_speak_entry'):
                        self.ai_speak_entry.config(state="disabled")
            else:
                status_text = "当前激活: 无"
                self.active_ai_label.config(text=status_text, foreground="red")
                
                # 更新按钮文本
                if hasattr(self, 'activate_ai_btn'):
                    self.activate_ai_btn.config(text="激活")
                    
                # 禁用行为控制按钮
                if hasattr(self, 'ai_greet_btn'):
                    self.ai_greet_btn.config(state="disabled")
                if hasattr(self, 'ai_speak_btn'):
                    self.ai_speak_btn.config(state="disabled")
                if hasattr(self, 'ai_speak_entry'):
                    self.ai_speak_entry.config(state="disabled")
                    
        except Exception as e:
            self.log(f"更新多实例AI角色状态显示错误: {e}")
    
    # === 新的单AI角色控制方法 ===
    
    def toggle_ai_osc_connection(self):
        """切换AI角色OSC连接状态"""
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        try:
            status = self.single_ai_manager.get_status()
            
            if status["vrc_connected"]:
                # 断开连接
                self.single_ai_manager.disconnect_from_vrc()
                messagebox.showinfo("成功", "已断开VRChat连接")
            else:
                # 连接VRChat
                success = self.single_ai_manager.connect_to_vrc()
                if success:
                    messagebox.showinfo("成功", "VRChat连接成功！\n\n现在可以发送文本和语音消息了")
                else:
                    messagebox.showerror("错误", "VRChat连接失败，请检查VRChat是否开启OSC")
                    
        except Exception as e:
            messagebox.showerror("错误", f"切换OSC连接时出错: {e}")
            self.log(f"切换AI角色OSC连接错误: {e}")
    
    def toggle_ai_character(self):
        """激活/停用AI角色"""
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        try:
            status = self.single_ai_manager.get_status()
            
            if not status["ai_character_exists"]:
                messagebox.showwarning("警告", "请先创建AI角色")
                return
            
            if not status["vrc_connected"]:
                messagebox.showwarning("警告", "请先连接VRChat")
                return
            
            if status["ai_active"]:
                # 停用AI角色
                success = self.single_ai_manager.deactivate_ai_character()
                if success:
                    messagebox.showinfo("成功", "AI角色已停用")
                else:
                    messagebox.showerror("错误", "停用AI角色失败")
            else:
                # 激活AI角色
                success = self.single_ai_manager.activate_ai_character()
                if success:
                    messagebox.showinfo("成功", "AI角色已激活！\n\nAI角色现在会自动说话和做表情了")
                else:
                    messagebox.showerror("错误", "激活AI角色失败")
                    
        except Exception as e:
            messagebox.showerror("错误", f"切换AI角色状态时出错: {e}")
            self.log(f"切换AI角色状态错误: {e}")
    
    def ai_send_text_message(self):
        """发送文本消息到VRChat"""
        text = self.ai_text_entry.get().strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入要发送的文本")
            return
        
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        try:
            success = self.single_ai_manager.send_text_message(text)
            if success:
                self.log(f"文本消息已发送: {text}")
                self.ai_text_entry.delete(0, tk.END)
            else:
                messagebox.showerror("错误", "发送文本消息失败，请检查VRChat连接")
                
        except Exception as e:
            messagebox.showerror("错误", f"发送文本消息时出错: {e}")
            self.log(f"发送文本消息错误: {e}")
    
    def ai_upload_voice_file(self):
        """上传语音文件"""
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        # 选择语音文件
        file_path = filedialog.askopenfilename(
            title="选择语音文件",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.flac *.ogg *.m4a"),
                ("WAV文件", "*.wav"),
                ("MP3文件", "*.mp3"),
                ("所有文件", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            success = self.single_ai_manager.upload_voice_file(file_path)
            if success:
                filename = os.path.basename(file_path)
                self.ai_voice_file_label.config(text=f"已添加: {filename}", foreground="green")
                self.log(f"语音文件已添加到队列: {filename}")
                messagebox.showinfo("成功", f"语音文件已添加到播放队列：\n{filename}")
            else:
                messagebox.showerror("错误", "添加语音文件失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"上传语音文件时出错: {e}")
            self.log(f"上传语音文件错误: {e}")
    
    def ai_generate_and_send_voice(self):
        """生成并发送VOICEVOX语音"""
        text = self.ai_voicevox_text_entry.get().strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入要合成的文本")
            return
        
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        try:
            # 获取当前选择的VOICEVOX角色ID
            speaker_id = 0  # 默认使用第一个角色，可以后续扩展为从界面获取
            
            success = self.single_ai_manager.generate_and_send_voice(text, speaker_id)
            if success:
                self.log(f"VOICEVOX语音已生成并添加到队列: {text}")
                self.ai_voicevox_text_entry.delete(0, tk.END)
                messagebox.showinfo("成功", f"语音已添加到播放队列：\n{text[:50]}...")
            else:
                messagebox.showerror("错误", "生成语音失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"生成语音时出错: {e}")
            self.log(f"生成VOICEVOX语音错误: {e}")
    
    def ai_greet(self):
        """让AI角色打招呼"""
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        try:
            success = self.single_ai_manager.make_ai_greet()
            if success:
                status = self.single_ai_manager.get_status()
                self.log(f"AI角色 '{status['ai_character_name']}' 执行打招呼")
            else:
                messagebox.showwarning("警告", "AI角色未激活或执行失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"AI角色打招呼时出错: {e}")
            self.log(f"AI角色打招呼错误: {e}")
    
    def ai_speak_custom(self):
        """让AI角色说自定义内容"""
        text = self.ai_speak_entry.get().strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入要说的内容")
            return
        
        if not self.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        try:
            success = self.single_ai_manager.make_ai_speak(text)
            if success:
                status = self.single_ai_manager.get_status()
                self.log(f"AI角色 '{status['ai_character_name']}' 说话: {text}")
                self.ai_speak_entry.delete(0, tk.END)
            else:
                messagebox.showwarning("警告", "AI角色未激活或执行失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"AI角色说话时出错: {e}")
            self.log(f"AI角色说话错误: {e}")
    
    def update_ai_character_status(self):
        """更新AI角色状态显示"""
        if not self.single_ai_manager:
            return
        
        try:
            status = self.single_ai_manager.get_status()
            
            # 更新激活状态显示
            if hasattr(self, 'active_ai_label'):
                if status["ai_character_exists"]:
                    if status["ai_active"]:
                        status_text = f"当前角色: {status['ai_character_name']} (已激活)"
                        self.active_ai_label.config(text=status_text, foreground="green")
                        
                        # 更新按钮状态
                        if hasattr(self, 'activate_ai_btn'):
                            self.activate_ai_btn.config(text="停用")
                        
                        # 启用控制按钮
                        self._set_ai_controls_state("normal")
                        
                    else:
                        status_text = f"当前角色: {status['ai_character_name']} (未激活)"
                        self.active_ai_label.config(text=status_text, foreground="orange")
                        
                        if hasattr(self, 'activate_ai_btn'):
                            self.activate_ai_btn.config(text="激活")
                        
                        # 部分启用控制按钮（VRC连接相关的可用）
                        self._set_ai_controls_state("disabled")
                        
                else:
                    status_text = "当前角色: 无"
                    self.active_ai_label.config(text=status_text, foreground="red")
                    
                    if hasattr(self, 'activate_ai_btn'):
                        self.activate_ai_btn.config(text="激活")
                    
                    # 禁用所有控制按钮
                    self._set_ai_controls_state("disabled")
            
            # 更新OSC连接状态显示
            if hasattr(self, 'ai_osc_status_label'):
                if status["vrc_connected"]:
                    self.ai_osc_status_label.config(text="已连接", foreground="green")
                    if hasattr(self, 'ai_osc_connect_btn'):
                        self.ai_osc_connect_btn.config(text="断开连接")
                else:
                    self.ai_osc_status_label.config(text="未连接", foreground="red")
                    if hasattr(self, 'ai_osc_connect_btn'):
                        self.ai_osc_connect_btn.config(text="连接VRC")
            
        except Exception as e:
            self.log(f"更新AI角色状态显示错误: {e}")
    
    def _set_ai_controls_state(self, state):
        """设置AI控制按钮状态"""
        controls = [
            'ai_greet_btn', 'ai_speak_btn', 'ai_speak_entry',
            'ai_send_text_btn', 'ai_text_entry',
            'ai_upload_voice_btn', 'ai_voicevox_generate_btn', 'ai_voicevox_text_entry'
        ]
        
        for control_name in controls:
            if hasattr(self, control_name):
                control = getattr(self, control_name)
                if hasattr(control, 'config'):
                    control.config(state=state)
    
    def update_voice_queue_display(self):
        """更新语音队列显示"""
        if not hasattr(self, 'ai_voice_queue_text') or not self.single_ai_manager:
            return
        
        try:
            items = self.single_ai_manager.get_voice_queue_items(10)
            
            display_text = ""
            for item in items:
                status_symbol = {
                    "pending": "⏳",
                    "processing": "🔄", 
                    "completed": "✅",
                    "error": "❌"
                }.get(item.get("status", "pending"), "❓")
                
                display_text += f"{status_symbol} [{item.get('time', '')}] {item.get('text', '')}\n"
            
            if not display_text:
                display_text = "队列为空"
            
            # 更新文本显示
            self.ai_voice_queue_text.config(state='normal')
            self.ai_voice_queue_text.delete(1.0, tk.END)
            self.ai_voice_queue_text.insert(tk.END, display_text)
            self.ai_voice_queue_text.config(state='disabled')
            
        except Exception as e:
            self.log(f"更新语音队列显示错误: {e}")
    
    def refresh_ai_character_list(self):
        """刷新AI角色列表（兼容方法）"""
        self.update_ai_character_status()
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()


def main():
    """主函数"""
    try:
        app = VRChatOSCGUI()
        app.run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行错误: {e}")


if __name__ == "__main__":
    main()