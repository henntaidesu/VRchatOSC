#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构后的VRChat OSC Client GUI
采用分离的UI组件和服务层架构
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import sys
import os
# PIL 和 numpy 将在需要时动态导入，避免启动时的依赖问题

# 添加路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置和基础组件
from src.config_manager import config_manager
from ui.settings_window import SettingsWindow
from ui.languages.language_dict import get_text, get_language_display_names, DISPLAY_TO_LANGUAGE_MAP

# 注意：所有服务层和UI组件的导入都延迟到实际使用时进行，避免依赖问题


class VRChatOSCGUI:
    """重构后的VRChat OSC GUI界面类"""
    
    def __init__(self):
        """初始化主界面"""
        # 加载配置
        self.config = config_manager
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("VRChat OSC 通信工具 (重构版)")
        
        # 设置窗口大小
        window_width = 1650
        window_height = self.config.window_height
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.resizable(True, True)
        
        # 初始化变量
        self._init_variables()
        
        # 初始化服务层
        self._init_services()
        
        # 初始化UI组件
        self._init_ui_components()
        
        # 设置服务层回调
        self._setup_service_callbacks()
        
        # 设置用户界面
        self.setup_ui()
        
        # 初始化语言和样式
        self._init_language_and_theme()
        
        # 启动自动初始化
        self._start_auto_initialization()
    
    def _init_variables(self):
        """初始化变量"""
        # 基本状态
        self.is_connected = False
        self.is_listening = False
        
        # UI变量
        self.host_var = tk.StringVar(value=self.config.osc_host)
        self.send_port_var = tk.StringVar(value=str(self.config.osc_send_port))
        self.receive_port_var = tk.StringVar(value=str(self.config.osc_receive_port))
        self.language_var = tk.StringVar(value=self.config.voice_language)
        self.device_var = tk.StringVar(value=self.config.voice_device)
        self.ui_language = tk.StringVar(value=self.config.ui_language)
        self.disable_fallback_var = tk.BooleanVar(value=self.config.disable_fallback_mode)
        
        # VOICEVOX相关变量
        self.voicevox_period_var = tk.StringVar(value="3期")
        self.voicevox_character_var = tk.StringVar()
        self.voicevox_style_var = tk.StringVar()
        self.voicevox_host_var = tk.StringVar(value=self.config.voicevox_host)
        self.voicevox_port_var = tk.StringVar(value=str(self.config.voicevox_port))
        self.voicevox_enabled_var = tk.BooleanVar(value=True)
        
        # 语音参数变量
        self.speed_var = tk.DoubleVar(value=1.0)
        self.pitch_var = tk.DoubleVar(value=0.0)
        self.intonation_var = tk.DoubleVar(value=1.0)
        self.volume_var = tk.DoubleVar(value=1.0)
        
        # 摄像头相关变量
        self.camera_id_var = tk.StringVar()
        self.resolution_var = tk.StringVar(value="1920x1080")
        self.model_var = tk.StringVar(value="ResEmoteNet")
        self.emotion_update_interval_var = tk.DoubleVar(value=3.0)
        
        # 语音识别阈值
        self.threshold_var = tk.DoubleVar(value=0.5)
        self.pause_threshold_var = tk.DoubleVar(value=2.0)
        
        # 语音文件相关变量
        self.uploaded_audio_data = None
        self.uploaded_audio_sample_rate = None
        self.uploaded_filename = None
        
        # Avatar控制器
        try:
            from src.avatar import AvatarController
            self.avatar_controller = AvatarController(character_data_file="data/vrc_characters.json")
        except ImportError as e:
            self.avatar_controller = None
            print(f"Avatar控制器不可用: {e}")
        
        # 表情显示相关
        self.expression_labels = {}
        self.expression_progress_bars = {}
        
        # 摄像头映射（兼容性）
        self.camera_id_mapping = {}
        
        # 其他兼容性变量
        self.voicevox_connected = False
        self.voicevox_client = None
    
    def _init_services(self):
        """初始化服务层"""
        try:
            # VRChat服务
            try:
                from src.services.vrchat_service import VRChatService
                self.vrchat_service = VRChatService(self.config)
                self.log("VRChat服务初始化成功")
            except ImportError as e:
                self.vrchat_service = None
                self.log(f"VRChat服务不可用: {e}")
            
            # LLM服务
            try:
                from src.services.llm_service import LLMService
                self.llm_service = LLMService(self.config)
                self.log("LLM服务初始化成功")
            except ImportError as e:
                self.llm_service = None
                self.log(f"LLM服务不可用: {e}")
            
            # VOICEVOX服务
            try:
                from src.services.voicevox_service import VoicevoxService
                self.voicevox_service = VoicevoxService(self.config)
                self.log("VOICEVOX服务初始化成功")
            except ImportError as e:
                self.voicevox_service = None
                self.log(f"VOICEVOX服务不可用: {e}")
            
            # 摄像头服务
            try:
                from src.services.camera_service import CameraService
                self.camera_service = CameraService(self.config)
                self.log("摄像头服务初始化成功")
            except ImportError as e:
                self.camera_service = None
                self.log(f"摄像头服务不可用: {e}")
            
            self.log("服务层初始化完成")
            
        except Exception as e:
            self.log(f"服务层初始化失败: {e}")
    
    def _init_ui_components(self):
        """初始化UI组件"""
        try:
            # 中央区域UI组件
            try:
                from src.ui.components.central.vrchat_connection_handler import VRChatConnectionHandler
                self.vrchat_connection_handler = VRChatConnectionHandler(self)
                self.log("VRChat连接处理器初始化成功")
            except ImportError as e:
                self.vrchat_connection_handler = None
                self.log(f"VRChat连接处理器不可用: {e}")
            
            try:
                from src.ui.components.central.llm_handler import LLMHandler
                self.llm_handler = LLMHandler(self)
                # 为了兼容性，设置别名
                self.llm_processor = self.llm_handler
                self.log("LLM处理器初始化成功")
            except ImportError as e:
                self.llm_handler = None
                self.llm_processor = None
                self.log(f"LLM处理器不可用: {e}")
            
            # 左侧区域UI组件  
            try:
                from src.ui.components.left.voicevox_controller import VoicevoxController
                self.voicevox_controller = VoicevoxController(self)
                self.log("VOICEVOX控制器初始化成功")
            except ImportError as e:
                self.voicevox_controller = None
                self.log(f"VOICEVOX控制器不可用: {e}")
            
            try:
                from src.ui.components.left.ai_vrchat_manager import AIVRChatManager
                self.ai_vrchat_manager = AIVRChatManager(self)
                self.log("AI VRChat管理器初始化成功")
            except ImportError as e:
                self.ai_vrchat_manager = None
                self.log(f"AI VRChat管理器不可用: {e}")
            
            # 右侧区域UI组件
            try:
                from src.ui.components.right.camera_handler import CameraHandler
                self.camera_handler = CameraHandler(self)
                self.log("摄像头处理器初始化成功")
            except ImportError as e:
                self.camera_handler = None
                self.log(f"摄像头处理器不可用: {e}")
            
            self.log("UI组件初始化完成")
            
        except Exception as e:
            self.log(f"UI组件初始化失败: {e}")
    
    def _setup_service_callbacks(self):
        """设置服务层回调"""
        try:
            # VRChat服务回调
            if self.vrchat_service and self.vrchat_connection_handler:
                self.vrchat_service.set_callbacks(
                    status_change_cb=self.vrchat_connection_handler.on_status_change,
                    voice_result_cb=self.vrchat_connection_handler.on_voice_result,
                    connection_status_cb=self.vrchat_connection_handler.on_connection_status_change,
                    log_cb=self.log
                )
                self.log("VRChat服务回调设置成功")
            
            # LLM服务回调
            if self.llm_service and self.llm_handler:
                self.llm_service.set_callbacks(
                    response_cb=self.llm_handler.on_llm_response,
                    log_cb=self.log
                )
                self.log("LLM服务回调设置成功")
            
            # VOICEVOX服务回调
            if self.voicevox_service and self.voicevox_controller:
                self.voicevox_service.set_callbacks(
                    connection_status_cb=self.voicevox_controller.update_voicevox_ui,
                    log_cb=self.log
                )
                self.log("VOICEVOX服务回调设置成功")
            
            # 摄像头服务回调
            if self.camera_service and self.camera_handler:
                self.camera_service.set_callbacks(
                    camera_status_cb=self.camera_handler.on_camera_status_change,
                    emotion_update_cb=self.camera_handler._update_expression_display,
                    frame_cb=self.camera_handler.update_video_display,
                    log_cb=self.log
                )
                self.log("摄像头服务回调设置成功")
            
            self.log("服务层回调设置完成")
            
        except Exception as e:
            self.log(f"服务层回调设置失败: {e}")
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建三列布局
        self.setup_three_column_layout(main_frame)
        
        # 日志现在已合并到中央区域显示
        
        # 设置窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_three_column_layout(self, parent):
        """设置三列布局"""
        # 创建三列容器
        columns_frame = ttk.Frame(parent)
        columns_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧区域 (400px宽)
        left_frame = ttk.LabelFrame(columns_frame, text="VOICEVOX & AI控制", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.config(width=400)
        
        # 中央区域 (600px宽)
        center_frame = ttk.LabelFrame(columns_frame, text="VRChat连接与语音识别", padding="5")
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # 右侧区域 (600px宽)
        right_frame = ttk.LabelFrame(columns_frame, text="摄像头控制", padding="5")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_frame.config(width=600)
        
        # 设置各区域内容
        self.setup_left_area(left_frame)
        self.setup_center_area(center_frame)
        self.setup_right_area(right_frame)
    
    def setup_left_area(self, parent):
        """设置左侧区域 - VOICEVOX和AI控制"""
        # VOICEVOX控制区域
        voicevox_frame = ttk.LabelFrame(parent, text="VOICEVOX语音合成", padding="5")
        voicevox_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.setup_voicevox_controls(voicevox_frame)
        
        # AI VRChat管理区域
        ai_frame = ttk.LabelFrame(parent, text="AI角色管理", padding="5")
        ai_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # 使用AI VRChat管理器设置界面
        if self.ai_vrchat_manager:
            self.ai_vrchat_manager.setup_ai_character_interface(ai_frame)
        else:
            tk.Label(ai_frame, text="AI VRChat管理器不可用", foreground="red").pack()
    
    def setup_voicevox_controls(self, parent):
        """设置VOICEVOX控制界面"""
        # 连接设置行
        connection_row = ttk.Frame(parent)
        connection_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(connection_row, text="主机:", width=6).pack(side=tk.LEFT)
        self.voicevox_host_entry = ttk.Entry(connection_row, textvariable=self.voicevox_host_var, width=12)
        self.voicevox_host_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(connection_row, text="端口:", width=5).pack(side=tk.LEFT)
        self.voicevox_port_entry = ttk.Entry(connection_row, textvariable=self.voicevox_port_var, width=8)
        self.voicevox_port_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        self.voicevox_connect_btn = ttk.Button(connection_row, text="连接", 
                                             command=lambda: self.voicevox_controller.connect_voicevox() if self.voicevox_controller else None, width=8)
        self.voicevox_connect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 状态显示
        self.voicevox_status_label = ttk.Label(connection_row, text="未连接", foreground="red", width=12)
        self.voicevox_status_label.pack(side=tk.LEFT)
        
        # 角色选择行
        character_row = ttk.Frame(parent)
        character_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(character_row, text="期数:", width=5).pack(side=tk.LEFT)
        self.voicevox_period_combo = ttk.Combobox(character_row, textvariable=self.voicevox_period_var,
                                                values=["1期", "2期", "3期"], width=8, state="readonly")
        self.voicevox_period_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.voicevox_period_combo.bind('<<ComboboxSelected>>', lambda e: self.voicevox_controller.on_voicevox_period_changed(e) if self.voicevox_controller else None)
        
        ttk.Label(character_row, text="角色:", width=5).pack(side=tk.LEFT)
        self.voicevox_character_combo = ttk.Combobox(character_row, textvariable=self.voicevox_character_var,
                                                   width=12, state="disabled")
        self.voicevox_character_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.voicevox_character_combo.bind('<<ComboboxSelected>>', lambda e: self.voicevox_controller.on_voicevox_character_name_changed(e) if self.voicevox_controller else None)
        
        # 样式选择行
        style_row = ttk.Frame(parent)
        style_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(style_row, text="样式:", width=5).pack(side=tk.LEFT)
        self.voicevox_style_combo = ttk.Combobox(style_row, textvariable=self.voicevox_style_var,
                                               width=12, state="disabled")
        self.voicevox_style_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        self.voicevox_confirm_btn = ttk.Button(style_row, text="确认", 
                                             command=lambda: self.voicevox_controller.confirm_voicevox_character_change() if self.voicevox_controller else None, 
                                             width=8, state="disabled")
        self.voicevox_confirm_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.voicevox_test_btn = ttk.Button(style_row, text="测试", 
                                          command=lambda: self.voicevox_controller.test_voicevox() if self.voicevox_controller else None, 
                                          width=8, state="disabled")
        self.voicevox_test_btn.pack(side=tk.LEFT)
        
        # 语音参数设置
        params_frame = ttk.LabelFrame(parent, text="语音参数", padding="3")
        params_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 速度
        speed_row = ttk.Frame(params_frame)
        speed_row.pack(fill=tk.X)
        ttk.Label(speed_row, text="速度:", width=6).pack(side=tk.LEFT)
        self.speed_scale = ttk.Scale(speed_row, from_=0.5, to=2.0, variable=self.speed_var, orient='horizontal')
        self.speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.speed_label = ttk.Label(speed_row, text="1.0", width=6)
        self.speed_label.pack(side=tk.LEFT)
        
        # 音调
        pitch_row = ttk.Frame(params_frame)
        pitch_row.pack(fill=tk.X)
        ttk.Label(pitch_row, text="音调:", width=6).pack(side=tk.LEFT)
        self.pitch_scale = ttk.Scale(pitch_row, from_=-0.15, to=0.15, variable=self.pitch_var, orient='horizontal')
        self.pitch_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.pitch_label = ttk.Label(pitch_row, text="0.0", width=6)
        self.pitch_label.pack(side=tk.LEFT)
        
        # 抑扬顿挫
        intonation_row = ttk.Frame(params_frame)
        intonation_row.pack(fill=tk.X)
        ttk.Label(intonation_row, text="语调:", width=6).pack(side=tk.LEFT)
        self.intonation_scale = ttk.Scale(intonation_row, from_=0.0, to=2.0, variable=self.intonation_var, orient='horizontal')
        self.intonation_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.intonation_label = ttk.Label(intonation_row, text="1.0", width=6)
        self.intonation_label.pack(side=tk.LEFT)
        
        # 音量
        volume_row = ttk.Frame(params_frame)
        volume_row.pack(fill=tk.X)
        ttk.Label(volume_row, text="音量:", width=6).pack(side=tk.LEFT)
        self.volume_scale = ttk.Scale(volume_row, from_=0.0, to=2.0, variable=self.volume_var, orient='horizontal')
        self.volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.volume_label = ttk.Label(volume_row, text="1.0", width=6)
        self.volume_label.pack(side=tk.LEFT)
    
    def setup_center_area(self, parent):
        """设置中央区域 - VRChat连接与语音识别"""
        # VRChat连接设置
        connection_frame = ttk.LabelFrame(parent, text="VRChat OSC连接", padding="5")
        connection_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.setup_vrchat_connection(connection_frame)
        
        # 语音识别设置
        voice_frame = ttk.LabelFrame(parent, text="语音识别", padding="5")
        voice_frame.pack(fill=tk.X, pady=(5, 5))
        
        self.setup_voice_recognition(voice_frame)
        
        # 系统日志显示区域 - 支持多语言
        log_frame = ttk.LabelFrame(parent, text=self.get_text("log"), padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 5))
        
        self.setup_system_log(log_frame)
        
        # 语音识别结果显示区域 - 支持多语言
        result_frame = ttk.LabelFrame(parent, text=self.get_text("speech_output"), padding="5")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        
        self.setup_voice_results(result_frame)
    
    def setup_vrchat_connection(self, parent):
        """设置VRChat连接界面"""
        # 连接设置行
        connection_row = ttk.Frame(parent)
        connection_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(connection_row, text="主机:", width=6).pack(side=tk.LEFT)
        self.host_entry = ttk.Entry(connection_row, textvariable=self.host_var, width=15)
        self.host_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(connection_row, text="发送:", width=5).pack(side=tk.LEFT)
        self.send_port_entry = ttk.Entry(connection_row, textvariable=self.send_port_var, width=8)
        self.send_port_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(connection_row, text="接收:", width=5).pack(side=tk.LEFT)
        self.receive_port_entry = ttk.Entry(connection_row, textvariable=self.receive_port_var, width=8)
        self.receive_port_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        self.connect_btn = ttk.Button(connection_row, text="连接", 
                                    command=lambda: self.vrchat_connection_handler.toggle_connection() if self.vrchat_connection_handler else None, width=8)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 状态显示
        self.status_label = ttk.Label(connection_row, text="未连接", foreground="red", width=10)
        self.status_label.pack(side=tk.LEFT)
        
        # 进度条（连接时显示）
        self.progress_bar = ttk.Progressbar(parent, mode='indeterminate')
        # 默认隐藏
        
        # 消息发送行
        message_row = ttk.Frame(parent)
        message_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(message_row, text="消息:", width=6).pack(side=tk.LEFT)
        self.message_entry = ttk.Entry(message_row, width=30)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind("<Return>", lambda e: self.vrchat_connection_handler.send_text_message() if self.vrchat_connection_handler else None)
        
        self.send_message_btn = ttk.Button(message_row, text="发送消息", 
                                         command=lambda: self.vrchat_connection_handler.send_text_message() if self.vrchat_connection_handler else None, width=10)
        self.send_message_btn.pack(side=tk.LEFT)
        
        # 参数设置行
        param_row = ttk.Frame(parent)
        param_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(param_row, text="参数:", width=6).pack(side=tk.LEFT)
        self.param_name_entry = ttk.Entry(param_row, width=15)
        self.param_name_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(param_row, text="值:", width=3).pack(side=tk.LEFT)
        self.param_value_entry = ttk.Entry(param_row, width=15)
        self.param_value_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        self.send_param_btn = ttk.Button(param_row, text="发送参数", 
                                       command=lambda: self.vrchat_connection_handler.send_parameter() if self.vrchat_connection_handler else None, width=10)
        self.send_param_btn.pack(side=tk.LEFT)
    
    def setup_voice_recognition(self, parent):
        """设置语音识别界面"""
        # 语音设备选择行
        device_row = ttk.Frame(parent)
        device_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(device_row, text="设备:", width=6).pack(side=tk.LEFT)
        self.device_combo = ttk.Combobox(device_row, textvariable=self.device_var, width=20, state="readonly")
        self.device_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(device_row, text="语言:", width=6).pack(side=tk.LEFT)
        
        # 语音识别语言选择 - 使用友好显示名称
        self.voice_language_display_var = tk.StringVar()
        voice_lang_map = {"中文": "zh", "日本語": "ja", "English": "en"}
        voice_lang_reverse = {"zh": "中文", "ja": "日本語", "en": "English"}
        current_voice_lang = voice_lang_reverse.get(self.language_var.get(), "中文")
        self.voice_language_display_var.set(current_voice_lang)
        
        self.language_combo = ttk.Combobox(device_row, textvariable=self.voice_language_display_var,
                                         values=list(voice_lang_map.keys()), width=10, state="readonly")
        
        def on_voice_language_changed(event=None):
            """语音识别语言切换事件"""
            display_name = self.voice_language_display_var.get()
            lang_code = voice_lang_map.get(display_name, "zh")
            self.language_var.set(lang_code)
            
        self.language_combo.bind('<<ComboboxSelected>>', on_voice_language_changed)
        self.language_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # 语音监听控制行
        listen_row = ttk.Frame(parent)
        listen_row.pack(fill=tk.X, pady=(5, 0))
        
        self.listen_btn = ttk.Button(listen_row, text="开始监听", 
                                   command=lambda: self.vrchat_connection_handler.toggle_voice_listening() if self.vrchat_connection_handler else None, 
                                   width=12, state="disabled")
        self.listen_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 语音阈值控制
        ttk.Label(listen_row, text="阈值:", width=5).pack(side=tk.LEFT)
        self.threshold_scale = ttk.Scale(listen_row, from_=0.001, to=1.0, variable=self.threshold_var,
                                       orient='horizontal', command=lambda v: self.vrchat_connection_handler.update_voice_threshold(v) if self.vrchat_connection_handler else None)
        self.threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.threshold_label = ttk.Label(listen_row, text="0.500", width=8)
        self.threshold_label.pack(side=tk.LEFT)
        
        # 断句间隔控制
        pause_row = ttk.Frame(parent)
        pause_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(pause_row, text="断句:", width=5).pack(side=tk.LEFT)
        self.pause_scale = ttk.Scale(pause_row, from_=0.5, to=5.0, variable=self.pause_threshold_var,
                                   orient='horizontal', command=lambda v: self.vrchat_connection_handler.update_pause_threshold(v) if self.vrchat_connection_handler else None)
        self.pause_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.pause_label = ttk.Label(pause_row, text="2.0s", width=8)
        self.pause_label.pack(side=tk.LEFT)
        
        # 语音文件上传行
        upload_row = ttk.Frame(parent)
        upload_row.pack(fill=tk.X, pady=(5, 0))
        
        self.upload_voice_btn = ttk.Button(upload_row, text="上传语音", 
                                         command=self.upload_voice_file, width=12, state="disabled")
        self.upload_voice_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.uploaded_file_label = ttk.Label(upload_row, text="未选择文件", foreground="gray")
        self.uploaded_file_label.pack(side=tk.LEFT)
    
    def setup_system_log(self, parent):
        """设置系统日志显示区域"""
        # 创建文本显示区域
        self.log_text = scrolledtext.ScrolledText(parent, height=8, state='disabled', font=("", 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 配置日志标签样式
        self.log_text.tag_config('log', foreground='#666666', font=("", 8))  # 普通日志
        self.log_text.tag_config('error', foreground='red', font=("", 8, "bold"))  # 错误日志
        self.log_text.tag_config('success', foreground='green', font=("", 8))  # 成功日志
        
        # 创建控制按钮区域
        log_control_frame = ttk.Frame(parent)
        log_control_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.clear_log_btn = ttk.Button(log_control_frame, text=self.get_text("clear_log"), command=self.clear_log, width=10)
        self.clear_log_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # UI语言选择
        language_frame = ttk.Frame(log_control_frame)
        language_frame.pack(side=tk.RIGHT, padx=(5, 5))
        
        ttk.Label(language_frame, text="语言:", font=("", 8)).pack(side=tk.LEFT, padx=(0, 2))
        
        # 语言显示名称下拉框
        self.ui_language_display_var = tk.StringVar()
        self.ui_language_combo = ttk.Combobox(language_frame, textvariable=self.ui_language_display_var,
                                            values=get_language_display_names(), width=8, state="readonly",
                                            font=("", 8))
        self.ui_language_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.ui_language_combo.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        # 设置当前语言显示
        from ui.languages.language_dict import LANGUAGE_DISPLAY_MAP
        current_display_name = LANGUAGE_DISPLAY_MAP.get(self.ui_language.get(), "中文")
        self.ui_language_display_var.set(current_display_name)
        
        self.settings_btn = ttk.Button(log_control_frame, text=self.get_text("settings"), command=self.open_settings, width=8)
        self.settings_btn.pack(side=tk.RIGHT)
        
    def setup_voice_results(self, parent):
        """设置语音识别结果显示区域"""
        # 创建文本显示区域
        self.speech_output = scrolledtext.ScrolledText(parent, height=8, state='disabled', font=("", 9))
        self.speech_output.pack(fill=tk.BOTH, expand=True)
        
        # 配置文本标签
        self.speech_output.tag_config('user', foreground='blue', font=("", 9, "bold"))
        self.speech_output.tag_config('ai', foreground='green', font=("", 9, "bold"))
        self.speech_output.tag_config('system', foreground='red', font=("", 9, "bold"))
        self.speech_output.tag_config('voice', foreground='purple', font=("", 9))
        
        # 创建控制按钮区域
        result_control_frame = ttk.Frame(parent)
        result_control_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.clear_results_btn = ttk.Button(result_control_frame, text=self.get_text("clear_speech"), command=self.clear_speech_results, width=10)
        self.clear_results_btn.pack(side=tk.LEFT, padx=(0, 5))
    
    def setup_right_area(self, parent):
        """设置右侧区域 - 摄像头控制"""
        # 摄像头控制区域
        camera_frame = ttk.LabelFrame(parent, text="摄像头设置", padding="5")
        camera_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.setup_camera_controls(camera_frame)
        
        # 视频显示区域
        video_frame = ttk.LabelFrame(parent, text="视频预览", padding="5")
        video_frame.pack(fill=tk.X, pady=(5, 5))
        
        self.setup_video_display(video_frame)
        
        # 表情识别结果
        emotion_frame = ttk.LabelFrame(parent, text="表情识别", padding="5")
        emotion_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.setup_emotion_display(emotion_frame)
    
    def setup_camera_controls(self, parent):
        """设置摄像头控制界面"""
        # 摄像头选择行
        camera_row = ttk.Frame(parent)
        camera_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(camera_row, text="摄像头:", width=8).pack(side=tk.LEFT)
        self.camera_combo = ttk.Combobox(camera_row, textvariable=self.camera_id_var, width=20, state="readonly")
        self.camera_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.camera_combo.bind('<<ComboboxSelected>>', lambda e: self.camera_handler.on_camera_changed(e) if self.camera_handler else None)
        
        self.refresh_camera_btn = ttk.Button(camera_row, text="刷新", 
                                           command=lambda: self.camera_handler.refresh_camera_list() if self.camera_handler else None, width=8)
        self.refresh_camera_btn.pack(side=tk.LEFT)
        
        # 分辨率和模型选择行
        settings_row = ttk.Frame(parent)
        settings_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(settings_row, text="分辨率:", width=8).pack(side=tk.LEFT)
        self.resolution_combo = ttk.Combobox(settings_row, textvariable=self.resolution_var,
                                           values=["1920x1080", "1280x720", "800x600", "640x480"],
                                           width=12, state="readonly")
        self.resolution_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.resolution_combo.bind('<<ComboboxSelected>>', lambda e: self.camera_handler.on_resolution_changed(e) if self.camera_handler else None)
        
        ttk.Label(settings_row, text="模型:", width=6).pack(side=tk.LEFT)
        self.model_combo = ttk.Combobox(settings_row, textvariable=self.model_var,
                                      values=["Simple", "ResEmoteNet", "FER2013", "EmoNeXt"],
                                      width=12, state="readonly")
        self.model_combo.pack(side=tk.LEFT)
        self.model_combo.bind('<<ComboboxSelected>>', lambda e: self.camera_handler.on_model_changed(e) if self.camera_handler else None)
        
        # 控制按钮行
        control_row = ttk.Frame(parent)
        control_row.pack(fill=tk.X, pady=(5, 0))
        
        self.camera_start_btn = ttk.Button(control_row, text="启动摄像头", 
                                         command=lambda: self.camera_handler.toggle_camera_only() if self.camera_handler else None, width=12)
        self.camera_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.face_detection_btn = ttk.Button(control_row, text="开始面部识别", 
                                           command=lambda: self.camera_handler.toggle_face_detection() if self.camera_handler else None, 
                                           width=14, state="disabled")
        self.face_detection_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 功能按钮行
        function_row = ttk.Frame(parent)
        function_row.pack(fill=tk.X, pady=(5, 0))
        
        self.capture_btn = ttk.Button(function_row, text="截图", 
                                    command=lambda: self.camera_handler.capture_screenshot() if self.camera_handler else None, 
                                    width=8, state="disabled")
        self.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.save_expression_btn = ttk.Button(function_row, text="保存表情", 
                                            command=lambda: self.camera_handler.save_expression_data() if self.camera_handler else None,
                                            width=10, state="disabled")
        self.save_expression_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.focus_btn = ttk.Button(function_row, text="自动对焦", 
                                  command=lambda: self.camera_handler.auto_focus() if self.camera_handler else None,
                                  width=10, state="disabled")
        self.focus_btn.pack(side=tk.LEFT)
        
        # 数字变焦控制
        zoom_row = ttk.Frame(parent)
        zoom_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(zoom_row, text="变焦:", width=5).pack(side=tk.LEFT)
        self.zoom_scale = ttk.Scale(zoom_row, from_=1.0, to=5.0, orient='horizontal',
                                  command=lambda v: self.camera_handler.on_zoom_changed(v) if self.camera_handler else None)
        self.zoom_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.zoom_label = ttk.Label(zoom_row, text="1.0x", width=6)
        self.zoom_label.pack(side=tk.LEFT)
    
    def setup_video_display(self, parent):
        """设置视频显示区域"""
        # 创建视频显示容器
        video_container = ttk.Frame(parent)
        video_container.pack(fill=tk.BOTH, expand=True)
        
        self.video_label = tk.Label(video_container, text="点击启动摄像头", 
                                  background="black", foreground="white", font=("", 12))
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        # 设置容器的最小大小
        video_container.config(width=400, height=300)
        video_container.pack_propagate(False)  # 防止容器根据内容自动调整大小
    
    def setup_emotion_display(self, parent):
        """设置表情识别显示区域"""
        # 整体状态显示
        overall_frame = ttk.Frame(parent)
        overall_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(overall_frame, text="主导情感:", font=("", 9, "bold")).pack(side=tk.LEFT)
        self.overall_status_label = ttk.Label(overall_frame, text="无数据", font=("", 9))
        self.overall_status_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # 主导情感进度条
        self.overall_status_progress = ttk.Progressbar(overall_frame, length=200, mode='determinate')
        self.overall_status_progress.pack(side=tk.RIGHT, padx=(10, 0))
        
        # 详细表情数据
        emotions = ['happy', 'sad', 'angry', 'surprise', 'fear', 'disgust', 'neutral']
        emotion_names_cn = ['快乐', '悲伤', '愤怒', '惊讶', '恐惧', '厌恶', '中性']
        
        for i, (emotion, name_cn) in enumerate(zip(emotions, emotion_names_cn)):
            emotion_row = ttk.Frame(parent)
            emotion_row.pack(fill=tk.X, pady=2)
            
            ttk.Label(emotion_row, text=f"{name_cn}:", width=6).pack(side=tk.LEFT)
            
            # 进度条
            progress = ttk.Progressbar(emotion_row, length=150, mode='determinate')
            progress.pack(side=tk.LEFT, padx=(0, 10))
            self.expression_progress_bars[emotion] = progress
            
            # 数值标签
            label = ttk.Label(emotion_row, text="0.00", width=6, font=("", 9, "bold"))
            label.pack(side=tk.LEFT)
            self.expression_labels[emotion] = label
        
        # 更新间隔设置
        interval_row = ttk.Frame(parent)
        interval_row.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(interval_row, text="更新间隔:", width=8).pack(side=tk.LEFT)
        self.interval_scale = ttk.Scale(interval_row, from_=1.0, to=10.0, 
                                      variable=self.emotion_update_interval_var,
                                      orient='horizontal')
        self.interval_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.interval_label = ttk.Label(interval_row, text="3.0s", width=6)
        self.interval_label.pack(side=tk.LEFT)
        
        # 主导情感详细显示
        dominant_row = ttk.Frame(parent)
        dominant_row.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(dominant_row, text="详细:", width=6).pack(side=tk.LEFT)
        self.dominant_emotion_label = ttk.Label(dominant_row, text="无数据", font=("", 8))
        self.dominant_emotion_label.pack(side=tk.LEFT, padx=(5, 0))
    
    
    def _init_language_and_theme(self):
        """初始化语言和主题"""
        try:
            # 设置界面语言
            self.update_ui_language()
            
            # 初始化语音设备列表（在后台）
            threading.Thread(target=self._detect_audio_devices, daemon=True).start()
            
        except Exception as e:
            self.log(f"语言和主题初始化失败: {e}")
    
    def _detect_audio_devices(self):
        """检测音频设备"""
        try:
            import speech_recognition as sr
            
            # 获取麦克风列表
            mic_list = sr.Microphone.list_microphone_names()
            
            # 在主线程中更新UI
            self.root.after(0, lambda: self.device_combo.configure(values=mic_list))
            
            if mic_list and not self.device_var.get():
                self.root.after(0, lambda: self.device_var.set(mic_list[0]))
            
            self.log(f"检测到 {len(mic_list)} 个音频设备")
            
        except Exception as e:
            self.log(f"检测音频设备失败: {e}")
    
    def _start_auto_initialization(self):
        """启动自动初始化"""
        try:
            # 延迟初始化各种服务
            self.root.after(1000, self._auto_init_services)
            
        except Exception as e:
            self.log(f"自动初始化启动失败: {e}")
    
    def _auto_init_services(self):
        """自动初始化服务"""
        try:
            # 初始化LLM服务
            if self.llm_service:
                self.root.after(500, self.llm_service.init_llm_handler)
            
            # 初始化VOICEVOX服务
            if self.voicevox_service:
                self.root.after(1000, self.voicevox_service.init_voicevox)
            
            # 检测摄像头
            if self.camera_handler:
                self.root.after(1500, self.camera_handler.refresh_camera_list)
            
            self.log("自动初始化服务已启动")
            
        except Exception as e:
            self.log(f"自动初始化服务失败: {e}")
    
    def get_text(self, key: str) -> str:
        """获取多语言文本"""
        try:
            return get_text(self.ui_language.get(), key)
        except:
            return key
    
    def log(self, message: str):
        """添加日志消息到系统日志区域"""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            
            # 根据消息内容确定标签样式
            tag = 'log'
            if any(word in message for word in ['错误', '失败', 'Error', 'Failed']):
                tag = 'error'
            elif any(word in message for word in ['成功', '完成', 'Success', '已连接', '已启动']):
                tag = 'success'
            
            log_message = f"[{timestamp}] {message}\n"
            
            # 在主线程中更新日志显示
            def update_log():
                try:
                    self.log_text.config(state='normal')
                    self.log_text.insert(tk.END, log_message, tag)
                    self.log_text.see(tk.END)
                    self.log_text.config(state='disabled')
                except:
                    pass
            
            if threading.current_thread() == threading.main_thread():
                update_log()
            else:
                self.root.after(0, update_log)
                
        except Exception as e:
            print(f"日志记录失败: {e}")
    
    def clear_log(self):
        """清空系统日志"""
        try:
            self.log_text.config(state='normal')
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state='disabled')
        except Exception as e:
            print(f"清空日志失败: {e}")
            
    def clear_speech_results(self):
        """清空语音识别结果"""
        try:
            self.speech_output.config(state='normal')
            self.speech_output.delete(1.0, tk.END)
            self.speech_output.config(state='disabled')
        except Exception as e:
            self.log(f"清空语音结果失败: {e}")
    
    def add_speech_output(self, text: str, source: str = "用户", tag: str = None):
        """添加语音识别结果到语音识别结果区域"""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            
            # 根据来源确定标签
            if not tag:
                if "AI" in source or "回复" in source:
                    tag = "ai"
                elif "用户" in source or "语音" in source:
                    tag = "user"
                else:
                    tag = "system"
            
            # 在主线程中更新语音结果显示
            def update_output():
                try:
                    self.speech_output.config(state='normal')
                    self.speech_output.insert(tk.END, f"[{timestamp}] {source}: ", tag)
                    self.speech_output.insert(tk.END, f"{text}\n", "voice")
                    self.speech_output.see(tk.END)
                    self.speech_output.config(state='disabled')
                except:
                    pass
            
            if threading.current_thread() == threading.main_thread():
                update_output()
            else:
                self.root.after(0, update_output)
            
        except Exception as e:
            self.log(f"添加语音输出失败: {e}")
    
    def upload_voice_file(self):
        """上传语音文件"""
        try:
            file_path = filedialog.askopenfilename(
                title="选择语音文件",
                filetypes=[
                    ("音频文件", "*.wav *.mp3 *.m4a *.flac *.ogg"),
                    ("所有文件", "*.*")
                ]
            )
            
            if file_path:
                # 处理语音文件上传的逻辑
                import os
                filename = os.path.basename(file_path)
                self.uploaded_filename = filename
                self.uploaded_file_label.config(text=f"已选择: {filename}")
                self.log(f"已选择语音文件: {filename}")
                
                # TODO: 实现语音文件处理逻辑
                
        except Exception as e:
            self.log(f"上传语音文件失败: {e}")
            messagebox.showerror("错误", f"上传语音文件失败: {e}")
    
    def update_ui_language(self):
        """更新界面语言"""
        try:
            current_language = self.ui_language.get()
            
            # 更新窗口标题
            title = self.get_text("title")
            if title != "title":  # 如果找到了翻译
                self.root.title(f"{title} - 重构版")
            
            # 更新按钮文本
            if hasattr(self, 'clear_log_btn'):
                self.clear_log_btn.config(text=self.get_text("clear_log"))
            if hasattr(self, 'settings_btn'):
                self.settings_btn.config(text=self.get_text("settings"))  
            if hasattr(self, 'clear_results_btn'):
                self.clear_results_btn.config(text=self.get_text("clear_speech"))
            
            # 刷新语音语言下拉框的默认值
            if hasattr(self, 'language_combo'):
                try:
                    current_voice_lang = self.language_var.get()
                    # 确保当前选择仍然有效
                    if current_voice_lang not in ["zh", "ja", "en"]:
                        self.language_var.set("zh")
                        
                    # 更新语音识别语言显示
                    if hasattr(self, 'voice_language_display_var'):
                        voice_lang_reverse = {"zh": "中文", "ja": "日本語", "en": "English"}
                        display_name = voice_lang_reverse.get(current_voice_lang, "中文")
                        self.voice_language_display_var.set(display_name)
                except:
                    pass
            
            # 更新配置中的UI语言
            self.config.ui_language = current_language
            
            # 根据选择的语言记录不同的日志信息
            if current_language == "ja":
                self.log("インターフェース言語が更新されました: 日本語")
            elif current_language == "en": 
                self.log("Interface language updated: English")
            else:
                self.log(f"界面语言已更新为: 中文")
            
        except Exception as e:
            self.log(f"更新界面语言失败: {e}")
    
    def on_language_changed(self, event=None):
        """语言切换事件处理"""
        try:
            from ui.languages.language_dict import DISPLAY_TO_LANGUAGE_MAP
            
            # 获取选择的显示名称并转换为语言代码
            display_name = self.ui_language_display_var.get()
            language_code = DISPLAY_TO_LANGUAGE_MAP.get(display_name, "zh")
            
            # 更新内部语言变量
            self.ui_language.set(language_code)
            
            # 保存到配置
            self.config.ui_language = language_code
            self.config.save_config()
            
            # 更新界面
            self.update_ui_language()
            
        except Exception as e:
            self.log(f"语言切换失败: {e}")
    
    def open_settings(self):
        """打开设置窗口"""
        try:
            def on_settings_saved():
                """设置保存后的回调"""
                # 更新UI语言变量
                self.ui_language.set(self.config.ui_language)
                
                # 更新主界面语言下拉框显示
                if hasattr(self, 'ui_language_display_var'):
                    from ui.languages.language_dict import LANGUAGE_DISPLAY_MAP
                    current_display_name = LANGUAGE_DISPLAY_MAP.get(self.config.ui_language, "中文")
                    self.ui_language_display_var.set(current_display_name)
                
                # 更新界面语言
                self.update_ui_language()
                
            settings_window = SettingsWindow(self.root, on_settings_saved, self)
        except Exception as e:
            self.log(f"打开设置窗口失败: {e}")
            messagebox.showerror("错误", f"无法打开设置窗口: {e}")
    
    def on_closing(self):
        """窗口关闭时的处理"""
        try:
            self.log("正在关闭应用程序...")
            
            # 清理服务层资源
            if hasattr(self, 'vrchat_service'):
                self.vrchat_service.cleanup()
            if hasattr(self, 'llm_service'):
                self.llm_service.cleanup()
            if hasattr(self, 'voicevox_service'):
                self.voicevox_service.cleanup()
            if hasattr(self, 'camera_service'):
                self.camera_service.cleanup()
            
            # 清理UI组件资源
            if hasattr(self, 'camera_handler'):
                self.camera_handler.cleanup()
            if hasattr(self, 'voicevox_controller'):
                pass  # 已通过服务层清理
            if hasattr(self, 'ai_vrchat_manager'):
                self.ai_vrchat_manager.cleanup()
            
            # 保存配置
            self.config.save_config()
            
            self.log("应用程序已安全关闭")
            
        except Exception as e:
            self.log(f"关闭时出现错误: {e}")
        finally:
            self.root.destroy()
    
    def run(self):
        """运行应用程序"""
        try:
            self.log("VRChat OSC GUI 启动成功")
            self.root.mainloop()
        except Exception as e:
            self.log(f"应用程序运行错误: {e}")
            messagebox.showerror("严重错误", f"应用程序运行时发生错误: {e}")


def main():
    """主函数"""
    try:
        app = VRChatOSCGUI()
        app.run()
    except Exception as e:
        print(f"启动应用程序失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
