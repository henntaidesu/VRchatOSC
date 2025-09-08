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
import cv2
from PIL import Image, ImageTk
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vrchat_controller import VRChatController
from src.config_manager import config_manager
from ui.settings_window import SettingsWindow
from ui.languages.language_dict import get_text, get_language_display_names, DISPLAY_TO_LANGUAGE_MAP
from src.avatar import AvatarController
from src.avatar.single_ai_vrc_manager import SingleAIVRCManager
from ui.mainUI.right_area.camera_control import CameraControl
from ui.mainUI.central_area.user_vrc import VRChatConnection
from ui.mainUI.central_area.LLM_process import LLMProcessor
from ui.mainUI.left_area.voicevox_area import VoicevoxArea
from ui.mainUI.left_area.ai_vrchat import AIVRChatManager


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
        self.disable_fallback_var = tk.BooleanVar(value=self.config.disable_fallback_mode)
        
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
        self.camera_id_mapping = {}  # 摄像头显示名称到ID的映射
        self.emotion_model_type = 'ResEmoteNet'  # 默认使用ResEmoteNet情感识别模型
        
        # VOICEVOX相关变量
        self.voicevox_client = None
        self.voicevox_connected = False
        
        
        # 初始化LLM处理器
        self.llm_processor = LLMProcessor(self)
        
        # LLM相关属性
        self.llm_enabled = True  # 默认启用LLM
        
        # 初始化摄像头控制（必须在setup_ui之前）
        self.camera_control = CameraControl(self)
        
        # 初始化VOICEVOX控制（必须在setup_ui之前）
        self.voicevox_area = VoicevoxArea(self)
        
        # 初始化VRChat连接控制
        self.vrchat_connection = VRChatConnection(self)
        
        # 初始化AI VRChat管理器
        self.ai_vrchat_manager = AIVRChatManager(self)
        
        self.setup_ui()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def get_text(self, key):
        """获取当前语言的文本"""
        return get_text(self.ui_language.get(), key, key)
    
    @property
    def llm_handler(self):
        """获取LLM处理器实例"""
        if self.llm_processor:
            if self.llm_processor.streaming_mode and self.llm_processor.streaming_processor:
                return self.llm_processor.streaming_processor
            else:
                return self.llm_processor.llm_handler
        return None
    
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
        self.connect_btn = ttk.Button(self.connection_frame, text=self.get_text("connect"), command=self.vrchat_connection.toggle_connection)
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
        
        self.send_text_btn = ttk.Button(text_frame, text=self.get_text("send_text"), command=self.vrchat_connection.send_text_message)
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
        self.listen_btn = ttk.Button(voice_frame, text=self.get_text("start_listening"), command=self.vrchat_connection.toggle_voice_listening)
        self.listen_btn.grid(row=0, column=4, padx=(10, 5))
        
        # 语音文件上传按钮
        self.upload_voice_btn = ttk.Button(voice_frame, text=self.get_text("upload_voice"), command=self.upload_voice_file)
        self.upload_voice_btn.grid(row=0, column=5, padx=(0, 5))
        
        
        # 第二行：调试和模式控制
        debug_frame = ttk.Frame(self.message_frame)
        debug_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # 高级设置按钮
        self.settings_btn = ttk.Button(debug_frame, text=self.get_text("settings"), command=self.open_settings)
        self.settings_btn.grid(row=0, column=0, padx=(0, 5))
        
        # 摄像头按钮 - 现在用于在主界面显示/隐藏摄像头区域
        self.camera_btn = ttk.Button(debug_frame, text=self.get_text("camera_window"), command=self.camera_control.open_camera_window)
        self.camera_btn.grid(row=0, column=1, padx=(0, 5))
        
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
                               command=self.vrchat_connection.update_pause_threshold)
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
        self.send_param_btn = ttk.Button(self.param_frame, text=self.get_text("send_param"), command=self.vrchat_connection.send_parameter)
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
        self.speech_text.tag_config("实时识别", foreground="#FF5722")    # 红橙色 - 实时识别
        self.speech_text.tag_config("持续监听", foreground="#2196F3")    # 蓝色 - 持续监听
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
        self.voicevox_area.setup_voicevox_area(left_frame)
        
        # 右侧摄像头区域
        self.camera_control.setup_camera_area(right_frame)
        
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
        self.vrchat_connection.update_ui_state(False)
        
        # 初始化VOICEVOX
        self.voicevox_area.init_voicevox()
        
        # 启动VOICEVOX状态监控
        self.voicevox_area.start_status_monitoring()
        
        # 初始化LLM处理器
        self.llm_processor.init_llm_handler()

    def setup_character_management_area(self, parent_frame):
        """设置角色管理区域"""
        # 使用Notebook创建选项卡
        character_notebook = ttk.Notebook(parent_frame)
        character_notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # AI角色管理选项卡
        ai_frame = ttk.Frame(character_notebook)
        character_notebook.add(ai_frame, text="AI角色")
        
        # 设置AI角色管理界面
        self.ai_vrchat_manager.setup_ai_character_interface(ai_frame)
    

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
            pass  # 调试和fallback相关设置已删除
            
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
                self.camera_control.stop_camera_only()
            if self.is_listening:
                self.vrchat_connection.stop_voice_listening()
            if self.is_connected:
                self.vrchat_connection.disconnect_from_vrchat()
            
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
                        self.llm_processor.process_voice_text(text)
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
            self.voicevox_control_frame.config(text="VOICEVOX")
        if hasattr(self, 'voicevox_test_btn'):
            self.voicevox_test_btn.config(text=self.get_text("voice_test"))
        
        # 更新状态标签
        if hasattr(self, 'status_label'):
            if self.is_connected:
                self.status_label.config(text=self.get_text("connected"))
            else:
                self.status_label.config(text=self.get_text("disconnected"))
        if hasattr(self, 'voicevox_status_label'):
            # VOICEVOX状态根据实际连接状态更新
            pass
        
        if hasattr(self, 'send_text_btn'):
            self.send_text_btn.config(text=self.get_text("send_text"))
        if hasattr(self, 'upload_voice_btn'):
            self.upload_voice_btn.config(text=self.get_text("upload_voice"))
        if hasattr(self, 'record_voice_btn'):
            self.record_voice_btn.config(text=self.get_text("record_voice"))
        # 调试和状态相关的UI元素已删除
        if hasattr(self, 'camera_btn'):
            self.camera_btn.config(text=self.get_text("camera_window"))
        if hasattr(self, 'settings_btn'):
            self.settings_btn.config(text=self.get_text("settings"))
        if hasattr(self, 'send_param_btn'):
            self.send_param_btn.config(text=self.get_text("send_param"))
    

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
        
        # 更新AI角色移动控制区域
        self.refresh_ai_movement_control_labels()
        
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
    
    def refresh_ai_movement_control_labels(self):
        """刷新AI角色移动控制区域的标签文本"""
        try:
            # 更新所有按钮文本
            button_mapping = {
                'move_forward_left_btn': 'move_forward_left',
                'move_forward_btn': 'move_forward',
                'move_forward_right_btn': 'move_forward_right',
                'strafe_left_btn': 'strafe_left',
                'crouch_btn': 'crouch',
                'strafe_right_btn': 'strafe_right',
                'move_backward_left_btn': 'move_backward_left',
                'move_backward_btn': 'move_backward',
                'move_backward_right_btn': 'move_backward_right',
                'jump_btn': 'jump',
                'look_up_left_btn': 'look_up_left',
                'look_up_btn': 'look_up',
                'look_up_right_btn': 'look_up_right',
                'turn_left_btn': 'turn_left',
                'stop_look_btn': 'stop_look',
                'turn_right_btn': 'turn_right',
                'look_down_left_btn': 'look_down_left',
                'look_down_btn': 'look_down',
                'look_down_right_btn': 'look_down_right'
            }
            
            for button_attr, text_key in button_mapping.items():
                if hasattr(self, button_attr):
                    button = getattr(self, button_attr)
                    button.config(text=self.get_text(text_key))
        except Exception as e:
            self.log(f"更新AI移动控制标签失败: {e}")
    
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
