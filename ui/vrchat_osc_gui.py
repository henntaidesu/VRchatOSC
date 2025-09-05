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


class VRChatOSCGUI:
    """VRChat OSC GUI界面类"""
    
    def __init__(self):
        # 加载配置
        self.config = config_manager
        
        self.root = tk.Tk()
        self.root.title("VRChat OSC 通信工具")
        
        # 设置窗口大小以适应新的左右布局 (600px + 800px + 间距和padding)
        window_width = 1450  # 600 + 800 + 间距padding约50px
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
        self.camera_id_mapping = {}  # 摄像头显示名称到ID的映射
        self.emotion_model_type = 'Simple'  # 默认使用简单模型
        
        # 界面文本配置
        self.ui_texts = {
            "zh": {
                "title": "VRChat OSC 通信工具",
                "connection_settings": "连接设置",
                "host_address": "主机地址:",
                "send_port": "发送端口:",
                "receive_port": "接收端口:",
                "connect": "连接",
                "disconnect": "断开",
                "connecting": "连接中...",
                "message_send": "消息发送",
                "recognition_language": "识别语言:",
                "compute_device": "计算设备:",
                "record_voice": "录制语音",
                "start_listening": "开始监听",
                "stop_listening": "停止监听",
                "upload_voice": "上传语音",
                "send_voice": "发送语音",
                "stop_recording": "停止录制",
                "voice_threshold": "语音阈值:",
                "ui_language": "界面语言:",
                "send_text": "发送文字"
            },
            "ja": {
                "title": "VRChat OSC 通信ツール",
                "connection_settings": "接続設定",
                "host_address": "ホストアドレス:",
                "send_port": "送信ポート:",
                "receive_port": "受信ポート:",
                "connect": "接続",
                "disconnect": "切断",
                "connecting": "接続中...",
                "message_send": "メッセージ送信",
                "recognition_language": "認識言語:",
                "compute_device": "計算デバイス:",
                "record_voice": "音声録音",
                "start_listening": "監視開始",
                "stop_listening": "監視停止",
                "upload_voice": "音声アップロード",
                "send_voice": "音声送信",
                "stop_recording": "録音停止",
                "voice_threshold": "音声閾値:",
                "ui_language": "UI言語:",
                "send_text": "テキスト送信"
            }
        }
        
        self.setup_ui()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def get_text(self, key):
        """获取当前语言的文本"""
        return self.ui_texts[self.ui_language.get()].get(key, key)
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)  # 左侧控制面板，固定宽度
        main_frame.columnconfigure(1, weight=0)  # 右侧摄像头区域，固定宽度
        
        # 配置主框架行权重
        main_frame.rowconfigure(0, weight=1)  # 主内容区域可扩展
        
        # 创建左右两个主要区域，都固定宽度500px
        left_frame = ttk.Frame(main_frame, width=600)  # 固定左侧宽度为500px
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 5))
        left_frame.grid_propagate(False)  # 防止子组件改变frame大小
        
        right_frame = ttk.Frame(main_frame, width=800)  # 固定右侧宽度为500px
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.N, tk.S), padx=(5, 0))
        right_frame.grid_propagate(False)  # 防止子组件改变frame大小
        
        # 配置左右区域的权重
        left_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)  # 摄像头显示区域可扩展
        
        # 连接设置框架 - 放在左侧区域
        self.connection_frame = ttk.LabelFrame(left_frame, text=self.get_text("connection_settings"), padding="5")
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
        
        # 创建语言映射变量
        self.ui_language_display = tk.StringVar()
        self.language_map = {"中文": "zh", "日本語": "ja"}
        self.reverse_language_map = {"zh": "中文", "ja": "日本語"}
        
        # 设置初始显示值
        self.ui_language_display.set(self.reverse_language_map[self.ui_language.get()])
        
        self.ui_language_combo = ttk.Combobox(self.connection_frame, textvariable=self.ui_language_display,
                                            values=["中文", "日本語"], width=8, state="readonly")
        self.ui_language_combo.grid(row=0, column=7, padx=(0, 10))
        self.ui_language_combo.bind("<<ComboboxSelected>>", self.on_language_changed)
        
        # 连接按钮
        self.connect_btn = ttk.Button(self.connection_frame, text=self.get_text("connect"), command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=8, padx=(10, 0))
        
        # 配置连接框架的列权重
        self.connection_frame.columnconfigure(1, weight=1)
        self.connection_frame.columnconfigure(3, weight=1)
        self.connection_frame.columnconfigure(5, weight=1)
        
        # 消息发送框架 - 放在左侧区域
        message_frame = ttk.LabelFrame(left_frame, text="消息发送", padding="5")
        message_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        message_frame.columnconfigure(0, weight=1)
        
        # 文字消息输入
        text_frame = ttk.Frame(message_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        text_frame.columnconfigure(0, weight=1)
        
        self.message_entry = ttk.Entry(text_frame, font=("微软雅黑", 10))
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.message_entry.bind("<Return>", lambda e: self.send_text_message())
        
        ttk.Button(text_frame, text="发送文字", command=self.send_text_message).grid(row=0, column=1)
        
        # 语音设置框架
        voice_frame = ttk.Frame(message_frame)
        voice_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # 第一行：语言选择、设备选择、开始监听、上传语音
        ttk.Label(voice_frame, text="识别语言:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        language_combo = ttk.Combobox(voice_frame, textvariable=self.language_var, 
                                    values=["zh-CN", "ja-JP"], 
                                    width=10, state="readonly")
        language_combo.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Label(voice_frame, text="计算设备:").grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
        device_combo = ttk.Combobox(voice_frame, textvariable=self.device_var,
                                   values=["auto", "cuda", "cpu"],
                                   width=10, state="readonly")
        device_combo.grid(row=0, column=3, padx=(0, 10))
        
        # 开始监听按钮
        self.listen_btn = ttk.Button(voice_frame, text="开始监听", command=self.toggle_voice_listening)
        self.listen_btn.grid(row=0, column=4, padx=(10, 5))
        
        # 语音文件上传按钮
        self.upload_voice_btn = ttk.Button(voice_frame, text="上传语音", command=self.upload_voice_file)
        self.upload_voice_btn.grid(row=0, column=5, padx=(0, 5))
        
        # 第二行：调试和模式控制
        debug_frame = ttk.Frame(message_frame)
        debug_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # 调试模式开关
        self.debug_var = tk.BooleanVar(value=self.config.osc_debug_mode)
        debug_check = ttk.Checkbutton(debug_frame, text="OSC调试模式", 
                                     variable=self.debug_var, command=self.toggle_debug_mode)
        debug_check.grid(row=0, column=0, padx=(0, 10))
        
        # 强制备用模式开关
        self.fallback_var = tk.BooleanVar(value=self.config.use_fallback_mode)
        fallback_check = ttk.Checkbutton(debug_frame, text="强制备用模式", 
                                        variable=self.fallback_var, command=self.toggle_fallback_mode)
        fallback_check.grid(row=0, column=1, padx=(0, 10))
        
        # 禁用备用模式开关
        self.disable_fallback_var = tk.BooleanVar(value=self.config.disable_fallback_mode)
        disable_fallback_check = ttk.Checkbutton(debug_frame, text="禁用备用模式", 
                                                 variable=self.disable_fallback_var, command=self.toggle_disable_fallback_mode)
        disable_fallback_check.grid(row=0, column=2, padx=(0, 10))
        
        # 高级设置按钮
        self.settings_btn = ttk.Button(debug_frame, text="高级设置", command=self.open_settings)
        self.settings_btn.grid(row=0, column=3, padx=(0, 5))
        
        # 状态显示按钮
        self.status_btn = ttk.Button(debug_frame, text="显示状态", command=self.show_debug_status)
        self.status_btn.grid(row=0, column=4, padx=(0, 5))
        
        # 摄像头按钮 - 现在用于在主界面显示/隐藏摄像头区域
        self.camera_btn = ttk.Button(debug_frame, text="摄像头窗口", command=self.open_camera_window)
        self.camera_btn.grid(row=0, column=5, padx=(0, 5))
        
        # 语音阈值设置
        threshold_frame = ttk.Frame(message_frame)
        threshold_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(threshold_frame, text="语音阈值:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.threshold_var = tk.DoubleVar(value=self.config.voice_threshold)
        threshold_scale = ttk.Scale(threshold_frame, from_=0.005, to=0.05, 
                                   variable=self.threshold_var, orient='horizontal',
                                   command=self.update_voice_threshold)
        threshold_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.threshold_label = ttk.Label(threshold_frame, text=f"{self.config.voice_threshold:.3f}")
        self.threshold_label.grid(row=0, column=2, padx=(0, 15))
        
        # 断句检测设置
        ttk.Label(threshold_frame, text="断句间隔:").grid(row=0, column=3, sticky=tk.W, padx=(0, 5))
        self.pause_var = tk.DoubleVar(value=self.config.sentence_pause_threshold)
        pause_scale = ttk.Scale(threshold_frame, from_=0.2, to=1.0, 
                               variable=self.pause_var, orient='horizontal',
                               command=self.update_pause_threshold)
        pause_scale.grid(row=0, column=4, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.pause_label = ttk.Label(threshold_frame, text=f"{self.config.sentence_pause_threshold:.1f}s")
        self.pause_label.grid(row=0, column=5)
        
        threshold_frame.columnconfigure(1, weight=1)
        threshold_frame.columnconfigure(4, weight=1)
        
        
        # 参数设置框架 - 放在左侧区域
        param_frame = ttk.LabelFrame(left_frame, text="Avatar参数", padding="5")
        param_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        param_frame.columnconfigure(0, weight=1)
        param_frame.columnconfigure(2, weight=1)
        
        # 参数名输入
        ttk.Label(param_frame, text="参数名:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.param_name_entry = ttk.Entry(param_frame, width=20)
        self.param_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 参数值输入
        ttk.Label(param_frame, text="参数值:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.param_value_entry = ttk.Entry(param_frame, width=15)
        self.param_value_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 10))
        self.param_value_entry.bind("<Return>", lambda e: self.send_parameter())
        
        # 发送参数按钮
        ttk.Button(param_frame, text="发送参数", command=self.send_parameter).grid(row=0, column=4)
        
        # 日志显示框架 - 放在左侧区域
        log_frame = ttk.LabelFrame(left_frame, text="日志", padding="5")
        log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 配置左侧框架行权重
        left_frame.rowconfigure(3, weight=1)
        
        # 日志文本框 - 减小高度为语音识别框让出空间
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清空日志按钮
        ttk.Button(log_frame, text="清空日志", command=self.clear_log).grid(row=1, column=0, pady=(5, 0))
        
        # 语音识别输出框架 - 放在左侧区域
        speech_frame = ttk.LabelFrame(left_frame, text="语音识别输出 (基于VRChat语音状态)", padding="5")
        speech_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        speech_frame.columnconfigure(0, weight=1)
        speech_frame.rowconfigure(0, weight=1)
        
        # 配置左侧框架行权重 - 为语音识别框分配空间
        left_frame.rowconfigure(4, weight=1)
        
        # 语音识别文本框
        self.speech_text = scrolledtext.ScrolledText(speech_frame, height=8, font=("微软雅黑", 12), wrap=tk.WORD)
        self.speech_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置语音识别输出的颜色标签
        self.speech_text.tag_config("持续监听", foreground="#2196F3")  # 蓝色
        self.speech_text.tag_config("录制语音", foreground="#4CAF50")  # 绿色  
        self.speech_text.tag_config("发送语音", foreground="#FF9800")  # 橙色
        self.speech_text.tag_config("时间戳", foreground="#666666")   # 灰色
        
        # 语音识别框按钮行
        speech_button_frame = ttk.Frame(speech_frame)
        speech_button_frame.grid(row=1, column=0, pady=(5, 0), sticky=(tk.W, tk.E))
        
        # 清空语音识别按钮
        ttk.Button(speech_button_frame, text="清空语音记录", command=self.clear_speech_output).grid(row=0, column=0, padx=(0, 5))
        
        # 保存语音记录按钮
        ttk.Button(speech_button_frame, text="保存语音记录", command=self.save_speech_output).grid(row=0, column=1, padx=(5, 0))
        
        # 右侧摄像头区域
        self.setup_camera_area(right_frame)
        
        # 状态栏 - 跨越整个底部
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="未连接", foreground="red")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 进度条（默认隐藏）
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        self.progress_bar.grid_remove()  # 初始隐藏
        
        # 初始状态设置
        self.update_ui_state(False)
    
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
                self.camera_combo['values'] = ['未检测到摄像头']
                self.camera_combo.set('未检测到摄像头')
                self.camera_id_mapping = {}
                self.log("未检测到可用摄像头")
                
        except Exception as e:
            self.log(f"更新摄像头列表失败: {e}")
            self.camera_combo['values'] = ['更新失败']
            self.camera_combo.set('更新失败')
    
    def on_model_changed(self, event=None):
        """模型选择变更处理"""
        self.emotion_model_type = self.model_var.get()
        self.log(f"情感识别模型已切换为: {self.emotion_model_type}")
        
        # 如果摄像头正在运行，需要重启以应用新模型
        if self.camera_running:
            self.log("检测到模型变更，正在重启摄像头以应用新模型...")
            self.stop_camera()
            # 延迟一点再启动
            self.root.after(1000, self.start_camera)
    
    def setup_camera_area(self, parent_frame):
        """设置摄像头区域"""
        # 摄像头控制面板
        camera_control_frame = ttk.LabelFrame(parent_frame, text="摄像头控制", padding="5")
        camera_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        camera_control_frame.columnconfigure(0, weight=1)
        
        # 摄像头控制按钮
        control_buttons = ttk.Frame(camera_control_frame)
        control_buttons.pack(fill=tk.X, pady=5)
        
        # 摄像头选择
        ttk.Label(control_buttons, text="摄像头:").pack(side=tk.LEFT, padx=(0, 5))
        self.camera_id_var = tk.StringVar(value="0")
        self.camera_combo = ttk.Combobox(control_buttons, textvariable=self.camera_id_var, 
                                        width=15, state="readonly")
        self.camera_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # 模型选择
        ttk.Label(control_buttons, text="模型:").pack(side=tk.LEFT, padx=(0, 5))
        self.model_var = tk.StringVar(value="Simple")
        model_combo = ttk.Combobox(control_buttons, textvariable=self.model_var,
                                  values=["Simple", "ResEmoteNet", "FER2013"], 
                                  width=10, state="readonly")
        model_combo.pack(side=tk.LEFT, padx=(0, 10))
        model_combo.bind("<<ComboboxSelected>>", self.on_model_changed)
        
        # 刷新摄像头列表按钮
        refresh_btn = ttk.Button(control_buttons, text="刷新", command=self.refresh_camera_list)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 初始化摄像头列表
        self.refresh_camera_list()
        
        # 摄像头启动/停止按钮
        self.camera_start_btn = ttk.Button(control_buttons, text="启动摄像头", command=self.toggle_camera_only)
        self.camera_start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 面部识别启动/停止按钮  
        self.face_detection_btn = ttk.Button(control_buttons, text="启动面部识别", 
                                           command=self.toggle_face_detection, state="disabled")
        self.face_detection_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 截图按钮
        self.capture_btn = ttk.Button(control_buttons, text="截图", command=self.capture_screenshot, 
                                     state="disabled")
        self.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 摄像头显示区域
        camera_display_frame = ttk.LabelFrame(parent_frame, text="摄像头画面", padding="5")
        camera_display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        camera_display_frame.columnconfigure(0, weight=1)
        camera_display_frame.rowconfigure(0, weight=1)
        
        # 视频显示标签 - 设置固定尺寸和样式
        self.video_label = tk.Label(camera_display_frame, text="点击启动摄像头按钮开始", 
                                   bg="black", fg="white",
                                   font=("Arial", 12),
                                   width=80, height=30)  # 设置足够的显示空间
        self.video_label.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        # 表情数据显示区域
        expression_frame = ttk.LabelFrame(parent_frame, text="实时表情数据", padding="5")
        expression_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        expression_frame.columnconfigure(1, weight=1)
        expression_frame.columnconfigure(3, weight=1)
        
        # 表情数据标签
        self.expressions = {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
        }
        
        # 创建表情显示组件
        row = 0
        col = 0
        self.expression_labels = {}
        self.expression_progress_bars = {}
        
        for expr_name in self.expressions.keys():
            # 表情名称
            display_name = {
                'eyeblink_left': '左眼眨眼',
                'eyeblink_right': '右眼眨眼',
                'mouth_open': '嘴巴张开',
                'smile': '微笑'
            }.get(expr_name, expr_name)
            
            ttk.Label(expression_frame, text=f"{display_name}:").grid(
                row=row, column=col*2, sticky=tk.W, padx=(0, 5))
            
            # 数值显示
            value_label = ttk.Label(expression_frame, text="0.00", width=6)
            value_label.grid(row=row, column=col*2+1, sticky=tk.W, padx=(0, 20))
            self.expression_labels[expr_name] = value_label
            
            # 进度条
            progress = ttk.Progressbar(expression_frame, length=100, mode='determinate')
            progress.grid(row=row, column=col*2+2, sticky=(tk.W, tk.E), padx=(0, 20))
            progress['maximum'] = 100
            self.expression_progress_bars[expr_name] = progress
            
            col += 1
            if col >= 2:
                col = 0
                row += 1
    
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
    
    def add_speech_output(self, text: str, source: str = "语音"):
        """添加语音识别输出"""
        timestamp = time.strftime("%H:%M:%S")
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_speech_output(timestamp, source, text))
    
    def _update_speech_output(self, timestamp: str, source: str, text: str):
        """更新语音识别输出显示（在主线程中调用）"""
        # 插入时间戳（灰色）
        start_pos = self.speech_text.index(tk.END + "-1c")
        self.speech_text.insert(tk.END, f"[{timestamp}] ")
        self.speech_text.tag_add("时间戳", start_pos, self.speech_text.index(tk.END + "-1c"))
        
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
                title="保存语音记录",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            
            if filename:
                content = self.speech_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log(f"语音记录已保存到: {filename}")
                
        except Exception as e:
            messagebox.showerror("保存错误", f"保存文件失败: {e}")
            self.log(f"保存语音记录失败: {e}")
    
    def update_ui_state(self, connected: bool):
        """更新UI状态"""
        self.is_connected = connected
        
        if connected:
            self.connect_btn.config(text=self.get_text("disconnect"))
            self.status_label.config(text="已连接", foreground="green")
            # 启用功能按钮
            self.listen_btn.config(state="normal")
            self.upload_voice_btn.config(state="normal")
        else:
            self.connect_btn.config(text=self.get_text("connect"))
            self.status_label.config(text="未连接", foreground="red")
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
            messagebox.showerror("错误", "端口号必须是数字")
        except Exception as e:
            self.connect_btn.config(text="连接", state="normal")
            self.progress_bar.stop()
            self.progress_bar.grid_remove()
            messagebox.showerror("连接错误", f"无法连接到VRChat: {e}")
            self.log(f"连接失败: {e}")
    
    def _connection_success(self, host: str, send_port: int):
        """连接成功的UI更新"""
        # 隐藏进度条
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        
        self.update_ui_state(True)
        self.log(f"已连接到VRChat OSC服务器 {host}:{send_port}")
        self.log("语音识别模型加载完成！")
        self.log("现在可以开始使用语音识别功能了")
    
    def _connection_failed(self, error_msg: str):
        """连接失败的UI更新"""
        # 隐藏进度条
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        
        self.connect_btn.config(text="连接", state="normal")
        messagebox.showerror("连接错误", f"无法连接到VRChat: {error_msg}")
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
            messagebox.showwarning("警告", "请先连接到VRChat")
            return
        
        message = self.message_entry.get().strip()
        if not message:
            return
        
        try:
            self.client.send_text_message(message)
            self.log(f"[发送文字] {message}")
            self.message_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("发送错误", f"发送消息失败: {e}")
            self.log(f"发送消息失败: {e}")
    
    def toggle_voice_listening(self):
        """切换语音监听状态"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接到VRChat")
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
                messagebox.showerror("语音错误", "语音识别模型未加载，请等待模型加载完成")
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
                messagebox.showerror("语音错误", "启动语音监听失败")
            
        except Exception as e:
            messagebox.showerror("语音错误", f"启动语音监听失败: {e}")
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
            messagebox.showwarning("警告", "请先连接到VRChat")
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
    
    def on_closing(self):
        """窗口关闭事件处理"""
        try:
            if self.camera_running:
                self.stop_camera_only()
            if self.is_listening:
                self.stop_voice_listening()
            if self.is_connected:
                self.disconnect_from_vrchat()
            self.root.destroy()
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            self.root.destroy()
    
    def upload_voice_file(self):
        """上传语音文件"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接到VRChat")
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
            messagebox.showwarning("警告", "请先连接到VRChat")
            self.debug_var.set(False)
            return
        
        debug_enabled = self.debug_var.get()
        self.client.set_debug_mode(debug_enabled)
        status = "启用" if debug_enabled else "禁用"
        self.log(f"OSC调试模式已{status}")
    
    def toggle_fallback_mode(self):
        """切换强制备用模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接到VRChat")
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
            messagebox.showwarning("警告", "请先连接到VRChat")
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
            messagebox.showwarning("警告", "请先连接到VRChat")
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
        selected_lang = self.language_map.get(selected_display, "zh")
        
        # 更新内部语言变量
        self.ui_language.set(selected_lang)
        
        # 更新窗口标题
        self.root.title(self.get_text("title"))
        
        # 更新界面文本
        self.connection_frame.config(text=self.get_text("connection_settings"))
        
        # 更新连接按钮文本
        if self.is_connected:
            self.connect_btn.config(text=self.get_text("disconnect"))
        else:
            self.connect_btn.config(text=self.get_text("connect"))
            
        # 更新监听按钮文本
        if self.is_listening:
            self.listen_btn.config(text=self.get_text("stop_listening"))
        else:
            self.listen_btn.config(text=self.get_text("start_listening"))
        
        # 记录语言切换
        self.log(f"界面语言已切换为: {selected_display}")
    
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
            
            # 启动简单的视频显示线程
            self.camera_thread = threading.Thread(target=self.simple_video_loop, daemon=True)
            self.camera_thread.start()
            
            self.log("摄像头启动成功")
            
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
            
            # 这里不需要重新创建摄像头实例，只是设置标志
            self.face_detection_running = True
            self.face_detection_btn.config(text="停止面部识别")
            
            self.log("面部识别启动成功")
            
        except Exception as e:
            self.log(f"面部识别启动失败: {e}")
    
    def process_face_detection(self, frame):
        """处理面部识别"""
        expressions = {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
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
                
                # 简单的表情模拟（可以后续扩展）
                if len(faces) > 0:
                    expressions['smile'] = 0.3
            
            # GPU模型的处理逻辑可以在这里添加
            
        except Exception as e:
            self.log(f"面部识别处理错误: {e}")
        
        return frame, expressions
    
    def stop_camera_only(self):
        """只停止摄像头"""
        try:
            self.log("正在停止摄像头...")
            self.camera_running = False
            
            # 同时停止面部识别
            if self.face_detection_running:
                self.face_detection_running = False
                self.face_detection_btn.config(text="启动面部识别", state="disabled")
            
            # 等待线程结束
            if self.camera_thread and self.camera_thread.is_alive():
                self.camera_thread.join(timeout=2)
            
            # 释放摄像头
            if self.camera:
                self.camera.release()
                self.camera = None
            
            # 更新UI
            self.camera_start_btn.config(text="启动摄像头")
            self.capture_btn.config(state="disabled")
            self.video_label.config(image="", text="点击启动摄像头按钮开始")
            
            self.log("摄像头已停止")
            
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
    
    def start_camera(self):
        """启动摄像头"""
        try:
            # 获取选中的摄像头信息
            selected_camera = self.camera_id_var.get()
            
            # 从映射中获取实际的摄像头ID
            if hasattr(self, 'camera_id_mapping') and selected_camera in self.camera_id_mapping:
                camera_id = self.camera_id_mapping[selected_camera]
            else:
                # 后备方案：尝试从字符串中解析ID
                try:
                    camera_id = int(selected_camera.split()[1]) if '摄像头' in selected_camera else int(selected_camera)
                except:
                    camera_id = 0
                    self.log("无法解析摄像头ID，使用默认摄像头0")
            
            self.log(f"正在启动摄像头: {selected_camera} (ID: {camera_id})")
            
            # 初始化摄像头和面部控制器
            self.camera = FaceMeshCamera(camera_id)
            self.face_controller = FaceExpressionController(camera_id)
            
            # 添加表情变化回调
            self.face_controller.add_expression_callback(self.on_expression_update)
            
            # 启动表情控制器
            self.log("正在启动面部检测...")
            if self.face_controller.start():
                self.camera_running = True
                self.camera_start_btn.config(text="停止摄像头")
                self.capture_btn.config(state="normal")
                self.log("摄像头启动成功，开始视频流...")
                
                # 更新显示标签
                self.video_label.config(text="正在连接摄像头...")
                
                # 启动视频更新线程
                self.camera_thread = threading.Thread(target=self.update_camera_video, daemon=True)
                self.camera_thread.start()
            else:
                messagebox.showerror("错误", "无法启动面部检测")
                self.log("面部检测启动失败")
                
        except Exception as e:
            messagebox.showerror("启动错误", f"启动摄像头失败: {e}")
            self.log(f"摄像头启动错误: {e}")
            print(f"摄像头启动详细错误: {e}")
            import traceback
            self.log(f"错误详情: {traceback.format_exc()}")
    
    def stop_camera(self):
        """停止摄像头"""
        try:
            self.log("正在停止摄像头...")
            self.camera_running = False
            
            # 等待视频线程结束
            if self.camera_thread and self.camera_thread.is_alive():
                self.log("等待视频线程结束...")
                self.camera_thread.join(timeout=2)
            
            # 停止面部控制器
            if self.face_controller:
                self.log("停止面部控制器...")
                self.face_controller.stop()
                self.face_controller = None
            
            # 释放摄像头资源
            if self.camera:
                self.log("释放摄像头资源...")
                if hasattr(self.camera, 'release'):
                    self.camera.release()
                elif hasattr(self.camera, 'cap') and self.camera.cap:
                    self.camera.cap.release()
                self.camera = None
            
            # 更新UI
            self.camera_start_btn.config(text="启动摄像头")
            self.capture_btn.config(state="disabled")
            self.log("摄像头已停止")
            
            # 清空视频显示
            self.video_label.config(image="", text="点击启动摄像头按钮开始")
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
        except Exception as e:
            self.log(f"停止摄像头错误: {e}")
            print(f"停止摄像头详细错误: {e}")
            import traceback
            self.log(f"错误详情: {traceback.format_exc()}")
    
    def update_camera_video(self):
        """视频更新线程"""
        self.log("视频更新线程已启动")
        try:
            while self.camera_running:
                try:
                    # 检查摄像头是否还在运行
                    if not self.camera_running:
                        break
                        
                    frame, expressions = self.camera.get_frame_with_expressions()
                    
                    if frame is not None:
                        # 转换OpenCV图像为PIL图像
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(frame_rgb)
                        
                        # 固定显示大小，确保有合适的显示区域
                        display_width = 640
                        display_height = 480
                        
                        # 调整图像大小
                        img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)
                        
                        # 转换为PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        
                        # 更新显示（需要在主线程中执行）
                        self.current_frame = frame  # 保存当前帧用于截图
                        if self.camera_running:  # 再次检查状态
                            self.root.after(0, lambda p=photo: self.update_video_display(p))
                        
                    time.sleep(0.03)  # 约33fps
                    
                except Exception as e:
                    if self.camera_running:  # 只在运行时记录错误
                        self.log(f"视频更新错误: {e}")
                        print(f"视频更新错误: {e}")
                    time.sleep(0.1)
                    
        except Exception as e:
            self.log(f"视频线程异常: {e}")
            print(f"视频线程异常: {e}")
        finally:
            self.log("视频更新线程已结束")
    
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
    
    def on_expression_update(self, expressions):
        """表情数据更新回调"""
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_expression_display(expressions))
    
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
                    
        except Exception as e:
            print(f"更新表情显示错误: {e}")
    
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
    
    def open_camera_window(self):
        """打开摄像头窗口（保留原功能作为备选）"""
        try:
            from .camera_window import CameraWindow
            CameraWindow(self.root)
        except Exception as e:
            messagebox.showerror("摄像头错误", f"无法打开摄像头窗口: {e}")
            self.log(f"打开摄像头窗口失败: {e}")
    
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