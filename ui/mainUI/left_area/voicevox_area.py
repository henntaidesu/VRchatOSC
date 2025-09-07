# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from src.VOICEVOX.voicevox_tts import VOICEVOXClient, get_voicevox_client


class VoicevoxArea:
    def __init__(self, main_app):
        self.main_app = main_app
        
    def setup_voicevox_area(self, parent_frame):
        """设置VOICEVOX控制区域"""
        # VOICEVOX控制面板 - 占用整个左侧区域
        self.main_app.voicevox_control_frame = ttk.LabelFrame(parent_frame, text="VOICEVOX", padding="5")
        self.main_app.voicevox_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        self.main_app.voicevox_control_frame.columnconfigure(0, weight=1)
        self.main_app.voicevox_control_frame.rowconfigure(2, weight=1)  # 为未来扩展留出空间
        
        # 第一行：服务器设置
        server_frame = ttk.Frame(self.main_app.voicevox_control_frame)
        server_frame.pack(fill=tk.X, pady=(0, 5))
        
        # IP地址输入
        ttk.Label(server_frame, text="IP:", width=4).pack(side=tk.LEFT, padx=(0, 2))
        saved_host = self.main_app.config.voicevox_host
        self.main_app.voicevox_host_var = tk.StringVar(value=saved_host)
        self.main_app.voicevox_host_entry = ttk.Entry(server_frame, textvariable=self.main_app.voicevox_host_var, width=12)
        self.main_app.voicevox_host_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # 端口输入
        ttk.Label(server_frame, text="端口:", width=4).pack(side=tk.LEFT, padx=(0, 2))
        saved_port = self.main_app.config.voicevox_port
        self.main_app.voicevox_port_var = tk.StringVar(value=str(saved_port))
        self.main_app.voicevox_port_entry = ttk.Entry(server_frame, textvariable=self.main_app.voicevox_port_var, width=8)
        self.main_app.voicevox_port_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # 连接按钮
        self.main_app.voicevox_connect_btn = ttk.Button(server_frame, text="连接", command=self.connect_voicevox, width=8)
        self.main_app.voicevox_connect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 连接状态
        self.main_app.voicevox_status_label = ttk.Label(server_frame, text="未连接", foreground="red")
        self.main_app.voicevox_status_label.pack(side=tk.RIGHT)
        
        # 第二行：期数选择
        period_frame = ttk.Frame(self.main_app.voicevox_control_frame)
        period_frame.pack(fill=tk.X, pady=(0, 5))
        
        # VOICEVOX期数选择
        ttk.Label(period_frame, text="期数:", width=6).pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.voicevox_period_var = tk.StringVar(value=self.main_app.config.voicevox_last_period)
        self.main_app.voicevox_period_combo = ttk.Combobox(period_frame, textvariable=self.main_app.voicevox_period_var,
                                                values=["1期", "2期", "3期"],
                                                width=8, state="readonly")
        self.main_app.voicevox_period_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.voicevox_period_combo.bind("<<ComboboxSelected>>", self.on_voicevox_period_changed)
        
        # 第二行：角色名称选择
        character_frame = ttk.Frame(self.main_app.voicevox_control_frame)
        character_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(character_frame, text="角色:", width=6).pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.voicevox_character_var = tk.StringVar(value=self.main_app.config.voicevox_last_speaker_name)
        self.main_app.voicevox_character_combo = ttk.Combobox(character_frame, textvariable=self.main_app.voicevox_character_var,
                                                   width=15, state="readonly")
        self.main_app.voicevox_character_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.voicevox_character_combo.bind("<<ComboboxSelected>>", self.on_voicevox_character_name_changed)
        
        # 第三行：样式选择和确定按钮
        style_frame = ttk.Frame(self.main_app.voicevox_control_frame)
        style_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(style_frame, text="样式:", width=6).pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.voicevox_style_var = tk.StringVar(value=self.main_app.config.voicevox_last_speaker_style)
        self.main_app.voicevox_style_combo = ttk.Combobox(style_frame, textvariable=self.main_app.voicevox_style_var,
                                               width=15, state="readonly")
        self.main_app.voicevox_style_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # 确定按钮
        self.main_app.voicevox_confirm_btn = ttk.Button(style_frame, text="确定", width=8, command=self.confirm_voicevox_character_change)
        self.main_app.voicevox_confirm_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # 第四行：控制按钮
        control_frame = ttk.Frame(self.main_app.voicevox_control_frame)
        control_frame.pack(fill=tk.X, pady=(5, 0))
        
        # VOICEVOX测试按钮
        self.main_app.voicevox_test_btn = ttk.Button(control_frame, text=self.main_app.get_text("voice_test"), command=self.test_voicevox)
        self.main_app.voicevox_test_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # VOICEVOX启用开关
        self.main_app.voicevox_enabled_var = tk.BooleanVar(value=True)
        self.main_app.voicevox_enabled_check = ttk.Checkbutton(control_frame, text="启用VOICEVOX", 
                                                    variable=self.main_app.voicevox_enabled_var)
        self.main_app.voicevox_enabled_check.pack(side=tk.LEFT, padx=(10, 0))
        
        # LLM启用开关
        self.main_app.llm_enabled_var = tk.BooleanVar(value=True)
        self.main_app.llm_enabled_check = ttk.Checkbutton(control_frame, text="启用AI对话", 
                                               variable=self.main_app.llm_enabled_var, 
                                               command=self.main_app.toggle_llm_enabled)
        self.main_app.llm_enabled_check.pack(side=tk.LEFT, padx=(10, 0))
        
        # 第四行：语音参数控制
        params_frame = ttk.LabelFrame(self.main_app.voicevox_control_frame, text=self.main_app.get_text("voice_params"), padding="5")
        params_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 语速控制
        speed_frame = ttk.Frame(params_frame)
        speed_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(speed_frame, text="语速:", width=8).pack(side=tk.LEFT)
        self.main_app.speed_var = tk.DoubleVar(value=1.0)
        self.main_app.speed_scale = ttk.Scale(speed_frame, from_=0.5, to=2.0, variable=self.main_app.speed_var,
                                   orient=tk.HORIZONTAL, command=self.main_app.on_speed_changed)
        self.main_app.speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.main_app.speed_label = ttk.Label(speed_frame, text="1.00", width=5)
        self.main_app.speed_label.pack(side=tk.RIGHT)
        
        # 音高控制  
        pitch_frame = ttk.Frame(params_frame)
        pitch_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(pitch_frame, text="音高:", width=8).pack(side=tk.LEFT)
        self.main_app.pitch_var = tk.DoubleVar(value=0.0)
        self.main_app.pitch_scale = ttk.Scale(pitch_frame, from_=-0.15, to=0.15, variable=self.main_app.pitch_var,
                                   orient=tk.HORIZONTAL, command=self.main_app.on_pitch_changed)
        self.main_app.pitch_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.main_app.pitch_label = ttk.Label(pitch_frame, text="0.00", width=5)
        self.main_app.pitch_label.pack(side=tk.RIGHT)
        
        # 抑扬顿挫控制
        intonation_frame = ttk.Frame(params_frame)
        intonation_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(intonation_frame, text="抑扬:", width=8).pack(side=tk.LEFT)
        self.main_app.intonation_var = tk.DoubleVar(value=1.0)
        self.main_app.intonation_scale = ttk.Scale(intonation_frame, from_=0.0, to=2.0, variable=self.main_app.intonation_var,
                                        orient=tk.HORIZONTAL, command=self.main_app.on_intonation_changed)
        self.main_app.intonation_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.main_app.intonation_label = ttk.Label(intonation_frame, text="1.00", width=5)
        self.main_app.intonation_label.pack(side=tk.RIGHT)
        
        # 音量控制
        volume_frame = ttk.Frame(params_frame)
        volume_frame.pack(fill=tk.X, pady=(0, 0))
        ttk.Label(volume_frame, text="音量:", width=8).pack(side=tk.LEFT)
        self.main_app.volume_var = tk.DoubleVar(value=1.0)
        self.main_app.volume_scale = ttk.Scale(volume_frame, from_=0.0, to=2.0, variable=self.main_app.volume_var,
                                    orient=tk.HORIZONTAL, command=self.main_app.on_volume_changed)
        self.main_app.volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.main_app.volume_label = ttk.Label(volume_frame, text="1.00", width=5)
        self.main_app.volume_label.pack(side=tk.RIGHT)
        
        # 语音参数控制按钮
        params_button_frame = ttk.Frame(params_frame)
        params_button_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 预设配置下拉菜单
        preset_frame = ttk.Frame(params_button_frame)
        preset_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(preset_frame, text="预设:").pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.voice_preset_var = tk.StringVar(value="默认")
        self.main_app.voice_preset_combo = ttk.Combobox(preset_frame, textvariable=self.main_app.voice_preset_var, 
                                             values=["默认", "慢速清晰", "快速自然", "低音温和", "高音活泼", "机器人", "自定义"], 
                                             state="readonly", width=10)
        self.main_app.voice_preset_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.voice_preset_combo.bind('<<ComboboxSelected>>', self.main_app.on_voice_preset_changed)
        
        # 控制按钮
        button_frame = ttk.Frame(params_button_frame)
        button_frame.pack(side=tk.RIGHT)
        
        self.main_app.preview_btn = ttk.Button(button_frame, text="试听", command=self.preview_voice, width=6)
        self.main_app.preview_btn.pack(side=tk.LEFT, padx=(5, 2))
        
        self.main_app.reset_params_btn = ttk.Button(button_frame, text="重置", command=self.main_app.reset_voice_params, width=6)
        self.main_app.reset_params_btn.pack(side=tk.LEFT, padx=(2, 2))
        
        self.main_app.save_params_btn = ttk.Button(button_frame, text="保存", command=self.main_app.save_voice_params, width=6)
        self.main_app.save_params_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        # 角色管理区域 - 直接在左侧VOICEVOX区域下方
        self.main_app.setup_character_management_area(self.main_app.voicevox_control_frame)

    def init_voicevox(self, retry_count=3):
        """初始化VOICEVOX客户端"""
        def init_in_background():
            # 获取配置的主机和端口
            host = self.main_app.config.voicevox_host
            port = self.main_app.config.voicevox_port
            
            for attempt in range(retry_count):
                try:
                    self.main_app.log(f"正在尝试连接VOICEVOX Engine {host}:{port}... (第{attempt + 1}次)")
                    
                    # 使用配置的主机和端口创建客户端实例
                    from src.VOICEVOX.voicevox_tts import VOICEVOXClient
                    self.main_app.voicevox_client = VOICEVOXClient(host=host, port=port)
                    
                    # 测试连接
                    if self.main_app.voicevox_client.test_connection():
                        try:
                            # 获取角色列表
                            speakers_list = self.main_app.voicevox_client.get_speakers_list()
                            if speakers_list:
                                speaker_names = [speaker['display'] for speaker in speakers_list]
                                self.main_app.voicevox_connected = True
                                
                                # 更新UI（必须在主线程中执行）
                                self.main_app.root.after(0, lambda: self.update_voicevox_ui(speaker_names, True))
                                self.main_app.log(f"VOICEVOX连接成功！已加载{len(speaker_names)}个角色")
                                return
                            else:
                                self.main_app.log("VOICEVOX连接成功但未获取到角色列表")
                        except Exception as e:
                            self.main_app.log(f"获取VOICEVOX角色列表失败: {e}")
                    else:
                        self.main_app.log(f"VOICEVOX Engine连接测试失败 (第{attempt + 1}次)")
                        
                except Exception as e:
                    self.main_app.log(f"VOICEVOX连接尝试失败 (第{attempt + 1}次): {e}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < retry_count - 1:
                    self.main_app.log("等待3秒后重试...")
                    time.sleep(3)
            
            # 所有尝试都失败了
            self.main_app.voicevox_connected = False
            error_msg = f"VOICEVOX连接失败！已尝试{retry_count}次。请检查：\n" \
                       f"1. VOICEVOX Engine是否已启动\n" \
                       f"2. 端口50021是否被占用\n" \
                       f"3. 防火墙设置是否正确"
            self.main_app.log(error_msg)
            self.main_app.root.after(0, lambda: self.update_voicevox_ui([], False))
        
        # 在后台线程中初始化，避免阻塞UI
        threading.Thread(target=init_in_background, daemon=True).start()
    
    def connect_voicevox(self):
        """手动连接VOICEVOX服务器"""
        def connect_in_background():
            try:
                # 更新按钮状态
                self.main_app.root.after(0, lambda: self.main_app.voicevox_connect_btn.config(state="disabled", text="连接中..."))
                self.main_app.root.after(0, lambda: self.main_app.voicevox_status_label.config(text="连接中...", foreground="orange"))
                
                # 获取用户输入的IP和端口
                host = self.main_app.voicevox_host_var.get().strip()
                port = self.main_app.voicevox_port_var.get().strip()
                
                # 验证输入
                if not host:
                    host = "localhost"
                    self.main_app.voicevox_host_var.set(host)
                
                if not port:
                    port = "50021"
                    self.main_app.voicevox_port_var.set(port)
                
                try:
                    port = int(port)
                except ValueError:
                    self.main_app.root.after(0, lambda: messagebox.showerror("错误", "端口必须是数字"))
                    self.main_app.root.after(0, lambda: self.main_app.voicevox_connect_btn.config(state="normal", text="连接"))
                    self.main_app.root.after(0, lambda: self.main_app.voicevox_status_label.config(text="连接失败", foreground="red"))
                    return
                
                self.main_app.log(f"尝试连接VOICEVOX服务器: {host}:{port}")
                
                # 创建新的VOICEVOX客户端实例
                from src.VOICEVOX.voicevox_tts import VOICEVOXClient
                voicevox_client = VOICEVOXClient(host=host, port=port)
                
                # 测试连接
                if voicevox_client.test_connection():
                    # 获取角色列表
                    speakers_list = voicevox_client.get_speakers_list()
                    if speakers_list:
                        speaker_names = [speaker['display'] for speaker in speakers_list]
                        
                        # 保存成功连接的配置
                        self.main_app.config.set_voicevox_server(host, port)
                        self.main_app.config.save_config()
                        
                        # 更新全局客户端实例
                        self.main_app.voicevox_client = voicevox_client
                        self.main_app.voicevox_connected = True
                        
                        # 更新UI
                        self.main_app.root.after(0, lambda: self.update_voicevox_ui(speaker_names, True))
                        self.main_app.root.after(0, lambda: self.main_app.voicevox_connect_btn.config(state="normal", text="重连"))
                        self.main_app.log(f"VOICEVOX连接成功！服务器: {host}:{port}, 已加载{len(speaker_names)}个角色")
                    else:
                        raise Exception("未获取到角色列表")
                else:
                    raise Exception("连接测试失败")
                    
            except Exception as e:
                self.main_app.log(f"VOICEVOX连接失败: {e}")
                self.main_app.voicevox_connected = False
                self.main_app.root.after(0, lambda: self.update_voicevox_ui([], False))
                self.main_app.root.after(0, lambda: self.main_app.voicevox_connect_btn.config(state="normal", text="连接"))
                self.main_app.root.after(0, lambda: messagebox.showerror("连接失败", f"无法连接到VOICEVOX服务器 {host}:{port}\n\n错误信息: {e}\n\n请检查:\n1. VOICEVOX Engine是否已启动\n2. IP地址和端口是否正确\n3. 防火墙设置"))
        
        # 在后台线程中连接
        threading.Thread(target=connect_in_background, daemon=True).start()
    
    def update_voicevox_ui(self, speaker_names, connected):
        """更新VOICEVOX UI状态"""
        try:
            if connected:
                # 连接成功时，更新Avatar控制器的VOICEVOX客户端
                self.main_app.avatar_controller.set_voicevox_client(self.main_app.voicevox_client)
                
                # 初始化SingleAI管理器
                if not self.main_app.single_ai_manager:
                    from src.avatar.single_ai_vrc_manager import SingleAIVRCManager
                    self.main_app.single_ai_manager = SingleAIVRCManager(
                        voicevox_client=self.main_app.voicevox_client
                    )
                
                # 显示连接详细信息
                host = self.main_app.voicevox_host_var.get()
                port = self.main_app.voicevox_port_var.get()
                self.main_app.voicevox_status_label.config(text=f"已连接 ({host}:{port})", foreground="green")
                self.main_app.voicevox_character_combo['values'] = speaker_names
                
                # 设置默认角色（如果配置中有保存的角色）
                if self.main_app.config.voicevox_last_speaker_name and self.main_app.config.voicevox_last_speaker_name in speaker_names:
                    self.main_app.voicevox_character_combo.set(self.main_app.config.voicevox_last_speaker_name)
                    self.on_voicevox_character_name_changed()  # 触发样式更新
                elif speaker_names:
                    self.main_app.voicevox_character_combo.set(speaker_names[0])
                    self.on_voicevox_character_name_changed()  # 触发样式更新
                
                # 启用相关控件
                self.main_app.voicevox_character_combo['state'] = 'readonly'
                self.main_app.voicevox_style_combo['state'] = 'readonly'
                self.main_app.voicevox_confirm_btn['state'] = 'normal'
                self.main_app.voicevox_test_btn['state'] = 'normal'
                self.main_app.voicevox_period_combo['state'] = 'readonly'
                
                self.main_app.voicevox_connected = True
                
                # 使用配置的期数重新连接
                saved_period = self.main_app.config.voicevox_last_period
                if saved_period and saved_period != self.main_app.voicevox_period_var.get():
                    self.main_app.voicevox_period_var.set(saved_period)
                    self.on_voicevox_period_changed()
                
            else:
                self.main_app.voicevox_status_label.config(text="未连接", foreground="red")
                self.main_app.voicevox_character_combo['values'] = []
                self.main_app.voicevox_style_combo['values'] = []
                
                # 禁用相关控件
                self.main_app.voicevox_character_combo['state'] = 'disabled'
                self.main_app.voicevox_style_combo['state'] = 'disabled'
                self.main_app.voicevox_confirm_btn['state'] = 'disabled'
                self.main_app.voicevox_test_btn['state'] = 'disabled'
                self.main_app.voicevox_period_combo['state'] = 'disabled'
                
                self.main_app.voicevox_connected = False
                
        except Exception as e:
            self.main_app.log(f"更新VOICEVOX UI失败: {e}")

    def confirm_voicevox_character_change(self):
        """确认VOICEVOX角色变更"""
        try:
            if not self.main_app.voicevox_connected:
                messagebox.showwarning("警告", "VOICEVOX未连接")
                return
                
            character_name = self.main_app.voicevox_character_var.get()
            style_name = self.main_app.voicevox_style_var.get()
            
            if not character_name or not style_name:
                messagebox.showwarning("警告", "请选择角色和样式")
                return
            
            # 获取样式ID
            # 从display名称中提取角色名称
            actual_character_name = character_name.split('] ')[-1].split(' - ')[0] if '] ' in character_name else character_name.split(' - ')[0]
            style_id = self.main_app.voicevox_client.get_speaker_id_by_name_and_style(actual_character_name, style_name)
            
            if style_id is not None:
                # 保存设置到配置
                current_period = self.main_app.voicevox_period_var.get()
                self.main_app.config.set_voicevox_last_selection(
                    period=current_period,
                    character=character_name,
                    speaker_id=str(style_id),
                    speaker_name=character_name,
                    speaker_style=style_name
                )
                self.main_app.config.save_config()
                
                # 更新VOICEVOX客户端的当前说话人
                self.main_app.voicevox_client.set_speaker(style_id, actual_character_name, style_name)
                
                # 更新Avatar控制器
                self.main_app.avatar_controller.set_voicevox_client(self.main_app.voicevox_client)
                
                self.main_app.log(f"VOICEVOX角色已切换为: {character_name} - {style_name} (ID: {style_id})")
                messagebox.showinfo("成功", f"角色已切换为: {character_name} - {style_name}")
            else:
                messagebox.showerror("错误", "无法找到对应的样式ID")
                
        except Exception as e:
            self.main_app.log(f"切换VOICEVOX角色失败: {e}")
            messagebox.showerror("错误", f"切换角色失败: {e}")

    def on_voicevox_character_changed(self, event=None):
        """VOICEVOX角色改变事件处理（已废弃，保留兼容性）"""
        # 这个方法已经不使用，但保留以防其他地方调用
        pass

    def on_voicevox_period_changed(self, event=None):
        """VOICEVOX期数改变事件处理"""
        try:
            new_period = self.main_app.voicevox_period_var.get()
            if new_period:
                # 保存到配置
                current_character = self.main_app.voicevox_character_var.get()
                current_style = self.main_app.voicevox_style_var.get()
                self.main_app.config.set_voicevox_last_selection(
                    period=new_period,
                    character=current_character,
                    speaker_name=current_character,
                    speaker_style=current_style
                )
                self.main_app.config.save_config()
                
                self.main_app.log(f"VOICEVOX期数已切换为: {new_period}")
                
                # 重新初始化VOICEVOX连接以使用新期数
                self.init_voicevox()
                
        except Exception as e:
            self.main_app.log(f"切换VOICEVOX期数失败: {e}")

    def on_voicevox_character_name_changed(self, event=None):
        """VOICEVOX角色名称改变事件处理"""
        try:
            if not self.main_app.voicevox_connected:
                return
                
            character_name = self.main_app.voicevox_character_var.get()
            if not character_name:
                return
            
            # 获取该角色的样式列表
            # 从display名称中提取角色名称
            # 格式通常是 "[期数] 角色名 - 样式" 或类似格式
            actual_character_name = character_name.split('] ')[-1].split(' - ')[0] if '] ' in character_name else character_name.split(' - ')[0]
            styles = self.main_app.voicevox_client.get_styles_for_character(actual_character_name)
            
            # 更新样式下拉框
            self.main_app.voicevox_style_combo['values'] = styles
            
            # 如果配置中有保存的样式且在当前样式列表中，则选中它
            if (self.main_app.config.voicevox_last_speaker_style and 
                self.main_app.config.voicevox_last_speaker_style in styles):
                self.main_app.voicevox_style_combo.set(self.main_app.config.voicevox_last_speaker_style)
            elif styles:
                # 否则选择第一个样式
                self.main_app.voicevox_style_combo.set(styles[0])
            
        except Exception as e:
            self.main_app.log(f"更新VOICEVOX样式列表失败: {e}")

    def test_voicevox(self):
        """测试VOICEVOX语音合成"""
        try:
            if not self.main_app.voicevox_connected:
                messagebox.showwarning("警告", "VOICEVOX未连接")
                return
            
            # 获取当前选择的角色和样式
            character_name = self.main_app.voicevox_character_var.get()
            style_name = self.main_app.voicevox_style_var.get()
            
            if not character_name or not style_name:
                messagebox.showwarning("警告", "请先选择角色和样式")
                return
            
            # 测试文本
            test_text = "こんにちは、VOICEVOX音声合成のテストです。"
            
            # 获取样式ID
            # 从display名称中提取角色名称
            actual_character_name = character_name.split('] ')[-1].split(' - ')[0] if '] ' in character_name else character_name.split(' - ')[0]
            style_id = self.main_app.voicevox_client.get_speaker_id_by_name_and_style(actual_character_name, style_name)
            
            if style_id is not None:
                self.main_app.log(f"正在测试VOICEVOX语音合成... 角色: {character_name} - {style_name}")
                
                # 在后台线程中进行语音合成
                def synthesize_test():
                    try:
                        # 临时设置说话人用于测试
                        original_speaker = getattr(self.main_app.voicevox_client, '_current_speaker_id', None)
                        self.main_app.voicevox_client.set_speaker(style_id, actual_character_name, style_name)
                        
                        # 使用当前的语音参数进行合成
                        audio_data = self.main_app.voicevox_client.synthesize(
                            text=test_text,
                            speed=self.main_app.speed_var.get(),
                            pitch=self.main_app.pitch_var.get(),
                            intonation=self.main_app.intonation_var.get(),
                            volume=self.main_app.volume_var.get()
                        )
                        
                        if audio_data:
                            self.main_app.voicevox_client.play_audio(audio_data)
                            self.main_app.root.after(0, lambda: self.main_app.log("VOICEVOX语音测试完成"))
                            self.main_app.root.after(0, lambda: messagebox.showinfo("成功", "语音测试完成"))
                        else:
                            self.main_app.root.after(0, lambda: self.main_app.log("VOICEVOX语音合成失败"))
                            self.main_app.root.after(0, lambda: messagebox.showerror("错误", "语音合成失败"))
                        
                        # 恢复原来的说话人
                        if original_speaker is not None:
                            self.main_app.voicevox_client.set_speaker(original_speaker)
                            
                    except Exception as e:
                        self.main_app.root.after(0, lambda: self.main_app.log(f"VOICEVOX测试失败: {e}"))
                        self.main_app.root.after(0, lambda: messagebox.showerror("错误", f"语音测试失败: {e}"))
                
                # 启动后台合成线程
                threading.Thread(target=synthesize_test, daemon=True).start()
                
            else:
                messagebox.showerror("错误", "无法找到对应的样式ID")
                
        except Exception as e:
            self.main_app.log(f"VOICEVOX测试失败: {e}")
            messagebox.showerror("错误", f"测试失败: {e}")

    def synthesize_with_voicevox(self, text):
        """使用VOICEVOX合成语音"""
        try:
            if not self.main_app.voicevox_connected or not self.main_app.voicevox_client:
                self.main_app.log("VOICEVOX未连接，跳过语音合成")
                return None
            
            if not self.main_app.voicevox_enabled_var.get():
                self.main_app.log("VOICEVOX已禁用，跳过语音合成")
                return None
            
            # 使用当前的语音参数进行合成
            audio_data = self.main_app.voicevox_client.synthesize(
                text=text,
                speed=self.main_app.speed_var.get(),
                pitch=self.main_app.pitch_var.get(),
                intonation=self.main_app.intonation_var.get(),
                volume=self.main_app.volume_var.get()
            )
            
            if audio_data:
                self.main_app.log(f"VOICEVOX语音合成成功: {text[:20]}...")
                # 播放音频
                self.main_app.voicevox_client.play_audio(audio_data)
                return audio_data
            else:
                self.main_app.log("VOICEVOX语音合成失败")
                return None
                
        except Exception as e:
            self.main_app.log(f"VOICEVOX语音合成出错: {e}")
            return None
    
    def ai_generate_and_send_voice(self):
        """生成并发送VOICEVOX语音"""
        text = self.main_app.ai_voicevox_text_entry.get().strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入要合成的文本")
            return
        
        if not self.main_app.single_ai_manager:
            messagebox.showerror("错误", "AI角色管理器未初始化")
            return
        
        try:
            # 获取当前选择的VOICEVOX角色ID
            speaker_id = 0  # 默认使用第一个角色，可以后续扩展为从界面获取
            
            success = self.main_app.single_ai_manager.generate_and_send_voice(text, speaker_id)
            if success:
                self.main_app.log(f"VOICEVOX语音已生成并添加到队列: {text}")
                self.main_app.ai_voicevox_text_entry.delete(0, tk.END)
                messagebox.showinfo("成功", f"语音已添加到播放队列：\n{text[:50]}...")
            else:
                messagebox.showerror("错误", "生成语音失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"生成语音时出错: {e}")
            self.main_app.log(f"生成VOICEVOX语音错误: {e}")
    
    def preview_voice(self):
        """语音试听"""
        if not self.main_app.voicevox_client or not self.main_app.voicevox_connected:
            messagebox.showwarning("警告", "VOICEVOX未连接")
            return
        
        # 获取当前角色信息
        current_speaker = self.main_app.voicevox_client.get_current_speaker_info()
        
        # 根据角色选择试听文本
        preview_texts = {
            "ずんだもん": "こんにちは！ずんだもんなのだ！この声はどうなのだ？",
            "四国めたん": "こんにちは、四国めたんです。この設定はいかがですか？",
            "春日部つむぎ": "こんにちは、春日部つむぎです。声の調子はどうでしょう？",
            "雨晴はう": "こんにちは、雨晴はうです。パラメータの確認です。",
            "波音リツ": "こんにちは、波音リツです。音声テストですね。"
        }
        
        # 选择测试文本
        test_text = preview_texts.get(current_speaker['name'], "こんにちは！音声パラメータのテストです。")
        
        def preview_in_background():
            try:
                success = self.main_app.voicevox_client.synthesize_and_play(test_text)
                if success:
                    self.main_app.log("语音试听播放成功")
                else:
                    self.main_app.log("语音试听播放失败")
            except Exception as e:
                self.main_app.log(f"语音试听错误: {e}")
        
        # 在后台线程中播放
        threading.Thread(target=preview_in_background, daemon=True).start()
    
    def check_voicevox_status(self):
        """检查VOICEVOX连接状态"""
        if hasattr(self.main_app, 'voicevox_client') and self.main_app.voicevox_client:
            try:
                # 测试连接是否可用
                if self.main_app.voicevox_client.test_connection():
                    if not self.main_app.voicevox_connected:
                        # 从断开连接变为连接成功
                        self.main_app.voicevox_connected = True
                        host = self.main_app.voicevox_host_var.get()
                        port = self.main_app.voicevox_port_var.get()
                        self.main_app.voicevox_status_label.config(text=f"已连接 ({host}:{port})", foreground="green")
                        self.main_app.log("VOICEVOX连接已恢复")
                    return True
                else:
                    # 连接失败
                    if self.main_app.voicevox_connected:
                        # 从连接变为断开
                        self.main_app.voicevox_connected = False
                        self.main_app.voicevox_status_label.config(text="连接断开", foreground="red")
                        self.main_app.log("VOICEVOX连接已断开")
                    return False
            except Exception as e:
                # 连接异常
                if self.main_app.voicevox_connected:
                    self.main_app.voicevox_connected = False
                    self.main_app.voicevox_status_label.config(text="连接异常", foreground="red")
                    self.main_app.log(f"VOICEVOX连接异常: {e}")
                return False
        else:
            # 没有客户端实例
            if hasattr(self.main_app, 'voicevox_connected'):
                self.main_app.voicevox_connected = False
            if hasattr(self.main_app, 'voicevox_status_label'):
                self.main_app.voicevox_status_label.config(text="未初始化", foreground="red")
            return False
    
    def start_status_monitoring(self):
        """开始状态监控"""
        def monitor_status():
            self.check_voicevox_status()
            # 每30秒检查一次状态
            self.main_app.root.after(30000, monitor_status)
        
        # 启动监控（5秒后开始）
        self.main_app.root.after(5000, monitor_status)
    
    def auto_reconnect(self):
        """自动重连VOICEVOX"""
        if not hasattr(self.main_app, 'voicevox_connected') or not self.main_app.voicevox_connected:
            self.main_app.log("尝试自动重连VOICEVOX...")
            self.init_voicevox(retry_count=1)