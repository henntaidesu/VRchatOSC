# -*- coding: utf-8 -*-


import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import numpy as np
import soundfile as sf


class AIVRChatManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.current_scenario = "学習疲労"
        self.scenario_data = {}
        self.ai_osc_client = None
        self.ai_is_connected = False
        self.ai_selected_voice_file = None
        self.movement_speed = 1.0
        
        # 读取AI_CHARACTER_VRC配置
        self.ai_host = main_app.config.ai_character_host
        self.ai_send_port = main_app.config.ai_character_send_port  
        self.ai_receive_port = main_app.config.ai_character_receive_port
        self.auto_connect = main_app.config.ai_character_auto_connect
        self.connection_timeout = main_app.config.ai_character_connection_timeout
        self.last_character_name = main_app.config.ai_character_last_name
        self.last_character_personality = main_app.config.ai_character_last_personality
        
        # 调试配置加载
        self.main_app.log(f"AI_CHARACTER_VRC配置已加载:")
        self.main_app.log(f"  主机: {self.ai_host}")  
        self.main_app.log(f"  发送端口: {self.ai_send_port}")
        self.main_app.log(f"  接收端口: {self.ai_receive_port}")
        self.main_app.log(f"  自动连接: {self.auto_connect}")
        self.main_app.log(f"  角色: {self.last_character_name or '未设置'}")
    
    def setup_ai_character_interface(self, parent_frame):
        """设置AI角色管理界面"""
        # 场景选择区域
        scenario_frame = ttk.LabelFrame(parent_frame, text="AI场景选择", padding="5")
        scenario_frame.pack(fill=tk.X, pady=(0, 5))

        scenario_row = ttk.Frame(scenario_frame)
        scenario_row.pack(fill=tk.X)

        ttk.Label(scenario_row, text="当前场景:", width=6).pack(side=tk.LEFT)
        self.main_app.scenario_var = tk.StringVar(value="学習疲労")
        self.main_app.scenario_combo = ttk.Combobox(scenario_row, textvariable=self.main_app.scenario_var,
                                         values=["学習疲労", "研究ストレス", "就職活動不安"],
                                         width=15, state="readonly")
        self.main_app.scenario_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.scenario_combo.bind('<<ComboboxSelected>>', self.on_scenario_change)

        # 应用场景按钮
        self.main_app.apply_scenario_btn = ttk.Button(scenario_row, text="应用场景", command=self.apply_scenario, width=10)
        self.main_app.apply_scenario_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 运行模式选择（已禁用）
        ttk.Label(scenario_row, text="模式:", width=5).pack(side=tk.LEFT)
        self.main_app.runtime_mode_var = tk.StringVar(value="user")
        self.main_app.runtime_mode_combo = ttk.Combobox(scenario_row, textvariable=self.main_app.runtime_mode_var,
                                             values=["user"],
                                             width=10, state="disabled")
        self.main_app.runtime_mode_combo.pack(side=tk.LEFT, padx=(0, 5))

        # 场景描述标签
        self.main_app.scenario_desc_label = ttk.Label(scenario_frame, text="学習疲労・勉強に疲れた時のサポート", 
                                           foreground="gray", font=("", 8))
        self.main_app.scenario_desc_label.pack(fill=tk.X, pady=(5, 0))

        # AI角色移动控制区域
        movement_frame = ttk.LabelFrame(parent_frame, text="AI角色移动控制", padding="5")
        movement_frame.pack(fill=tk.X, pady=(0, 5))

        # 移动和镜头控制布局
        control_container = ttk.Frame(movement_frame)
        control_container.pack(pady=(5, 0))

        # 左侧: 移动控制
        movement_grid = ttk.Frame(control_container)
        movement_grid.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(movement_grid, text="移动控制", font=("", 9, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 5))

        # 斜着走按钮 - 左上、右上
        self.main_app.move_forward_left_btn = ttk.Button(movement_grid, text=self.main_app.get_text("move_forward_left"), width=6)
        self.main_app.move_forward_left_btn.grid(row=1, column=0, padx=2, pady=2)
        self.main_app.move_forward_left_btn.bind("<ButtonPress-1>", lambda e: self.move_forward_left())
        self.main_app.move_forward_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        # 前进按钮
        self.main_app.move_forward_btn = ttk.Button(movement_grid, text=self.main_app.get_text("move_forward"), width=6)
        self.main_app.move_forward_btn.grid(row=1, column=1, padx=2, pady=2)
        self.main_app.move_forward_btn.bind("<ButtonPress-1>", lambda e: self.move_forward())
        self.main_app.move_forward_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.move_forward_right_btn = ttk.Button(movement_grid, text=self.main_app.get_text("move_forward_right"), width=6)
        self.main_app.move_forward_right_btn.grid(row=1, column=2, padx=2, pady=2)
        self.main_app.move_forward_right_btn.bind("<ButtonPress-1>", lambda e: self.move_forward_right())
        self.main_app.move_forward_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        # 左移、蹲下、右移按钮
        self.main_app.strafe_left_btn = ttk.Button(movement_grid, text=self.main_app.get_text("strafe_left"), width=6)
        self.main_app.strafe_left_btn.grid(row=2, column=0, padx=2, pady=2)
        self.main_app.strafe_left_btn.bind("<ButtonPress-1>", lambda e: self.strafe_left())
        self.main_app.strafe_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.crouch_btn = ttk.Button(movement_grid, text=self.main_app.get_text("crouch"), width=6)
        self.main_app.crouch_btn.grid(row=2, column=1, padx=2, pady=2)
        self.main_app.crouch_btn.bind("<ButtonPress-1>", lambda e: self.crouch())
        self.main_app.crouch_btn.bind("<ButtonRelease-1>", lambda e: self.stop_crouch())

        self.main_app.strafe_right_btn = ttk.Button(movement_grid, text=self.main_app.get_text("strafe_right"), width=6)
        self.main_app.strafe_right_btn.grid(row=2, column=2, padx=2, pady=2)
        self.main_app.strafe_right_btn.bind("<ButtonPress-1>", lambda e: self.strafe_right())
        self.main_app.strafe_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        # 斜着走按钮 - 左下、后退、右下
        self.main_app.move_backward_left_btn = ttk.Button(movement_grid, text=self.main_app.get_text("move_backward_left"), width=6)
        self.main_app.move_backward_left_btn.grid(row=3, column=0, padx=2, pady=2)
        self.main_app.move_backward_left_btn.bind("<ButtonPress-1>", lambda e: self.move_backward_left())
        self.main_app.move_backward_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.move_backward_btn = ttk.Button(movement_grid, text=self.main_app.get_text("move_backward"), width=6)
        self.main_app.move_backward_btn.grid(row=3, column=1, padx=2, pady=2)
        self.main_app.move_backward_btn.bind("<ButtonPress-1>", lambda e: self.move_backward())
        self.main_app.move_backward_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.move_backward_right_btn = ttk.Button(movement_grid, text=self.main_app.get_text("move_backward_right"), width=6)
        self.main_app.move_backward_right_btn.grid(row=3, column=2, padx=2, pady=2)
        self.main_app.move_backward_right_btn.bind("<ButtonPress-1>", lambda e: self.move_backward_right())
        self.main_app.move_backward_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        # 跳跃按钮
        self.main_app.jump_btn = ttk.Button(movement_grid, text=self.main_app.get_text("jump"), command=self.jump, width=6)
        self.main_app.jump_btn.grid(row=4, column=1, padx=2, pady=2)
        
        # OSC连接测试按钮
        self.main_app.osc_test_btn = ttk.Button(movement_grid, text="测试连接", command=self.test_osc_connection, width=6)
        self.main_app.osc_test_btn.grid(row=4, column=0, padx=2, pady=2)
        
        # AI角色连接按钮
        self.main_app.ai_connect_btn = ttk.Button(movement_grid, text="AI连接", command=self.connect_ai_vrchat, width=6)
        self.main_app.ai_connect_btn.grid(row=4, column=2, padx=2, pady=2)

        # 右侧: 镜头控制
        camera_grid = ttk.Frame(control_container)
        camera_grid.pack(side=tk.LEFT)

        ttk.Label(camera_grid, text="镜头控制", font=("", 9, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 5))

        # 斜着看按钮 - 左上、上看、右上
        self.main_app.look_up_left_btn = ttk.Button(camera_grid, text=self.main_app.get_text("look_up_left"), width=6)
        self.main_app.look_up_left_btn.grid(row=1, column=0, padx=2, pady=2)
        self.main_app.look_up_left_btn.bind("<ButtonPress-1>", lambda e: self.look_up_left())
        self.main_app.look_up_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_up_btn = ttk.Button(camera_grid, text=self.main_app.get_text("look_up"), width=6)
        self.main_app.look_up_btn.grid(row=1, column=1, padx=2, pady=2)
        self.main_app.look_up_btn.bind("<ButtonPress-1>", lambda e: self.look_up())
        self.main_app.look_up_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_up_right_btn = ttk.Button(camera_grid, text=self.main_app.get_text("look_up_right"), width=6)
        self.main_app.look_up_right_btn.grid(row=1, column=2, padx=2, pady=2)
        self.main_app.look_up_right_btn.bind("<ButtonPress-1>", lambda e: self.look_up_right())
        self.main_app.look_up_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        # 左转、停止、右转按钮
        self.main_app.turn_left_btn = ttk.Button(camera_grid, text=self.main_app.get_text("turn_left"), width=6)
        self.main_app.turn_left_btn.grid(row=2, column=0, padx=2, pady=2)
        self.main_app.turn_left_btn.bind("<ButtonPress-1>", lambda e: self.turn_left())
        self.main_app.turn_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.stop_look_btn = ttk.Button(camera_grid, text=self.main_app.get_text("stop_look"), width=6)
        self.main_app.stop_look_btn.grid(row=2, column=1, padx=2, pady=2)
        self.main_app.stop_look_btn.bind("<Button-1>", lambda e: self.stop_look())

        self.main_app.turn_right_btn = ttk.Button(camera_grid, text=self.main_app.get_text("turn_right"), width=6)
        self.main_app.turn_right_btn.grid(row=2, column=2, padx=2, pady=2)
        self.main_app.turn_right_btn.bind("<ButtonPress-1>", lambda e: self.turn_right())
        self.main_app.turn_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        # 斜着看按钮 - 左下、下看、右下
        self.main_app.look_down_left_btn = ttk.Button(camera_grid, text=self.main_app.get_text("look_down_left"), width=6)
        self.main_app.look_down_left_btn.grid(row=3, column=0, padx=2, pady=2)
        self.main_app.look_down_left_btn.bind("<ButtonPress-1>", lambda e: self.look_down_left())
        self.main_app.look_down_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_down_btn = ttk.Button(camera_grid, text=self.main_app.get_text("look_down"), width=6)
        self.main_app.look_down_btn.grid(row=3, column=1, padx=2, pady=2)
        self.main_app.look_down_btn.bind("<ButtonPress-1>", lambda e: self.look_down())
        self.main_app.look_down_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_down_right_btn = ttk.Button(camera_grid, text=self.main_app.get_text("look_down_right"), width=6)
        self.main_app.look_down_right_btn.grid(row=3, column=2, padx=2, pady=2)
        self.main_app.look_down_right_btn.bind("<ButtonPress-1>", lambda e: self.look_down_right())
        self.main_app.look_down_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        # 控制速度设置
        speed_frame = ttk.Frame(movement_frame)
        speed_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(speed_frame, text=self.main_app.get_text("control_speed"), width=8).pack(side=tk.LEFT)
        self.main_app.movement_speed_var = tk.DoubleVar(value=1.0)
        self.main_app.movement_speed_scale = ttk.Scale(speed_frame, from_=0.1, to=2.0, 
                                            orient=tk.HORIZONTAL, variable=self.main_app.movement_speed_var)
        self.main_app.movement_speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        self.main_app.movement_speed_label = ttk.Label(speed_frame, text="1.0")
        self.main_app.movement_speed_label.pack(side=tk.LEFT)

        # 更新速度显示
        self.main_app.movement_speed_var.trace('w', self.update_speed_label)
        
        # AI角色配置信息显示区域
        ai_config_frame = ttk.LabelFrame(movement_frame, text="AI角色配置", padding="5")
        ai_config_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 显示AI角色连接信息
        ai_info_text = f"主机: {self.ai_host}:{self.ai_send_port} | 自动连接: {'是' if self.auto_connect else '否'}"
        if self.last_character_name:
            ai_info_text += f" | 角色: {self.last_character_name}"
        
        self.main_app.ai_config_label = ttk.Label(ai_config_frame, text=ai_info_text, font=("", 8))
        self.main_app.ai_config_label.pack()

        # VRC OSC连接控制区域
        vrc_control_frame = ttk.LabelFrame(parent_frame, text="VRC连接配置", padding="5")
        vrc_control_frame.pack(fill=tk.X, pady=(5, 5))

        # 使用grid布局优化空间利用
        config_grid = ttk.Frame(vrc_control_frame)
        config_grid.pack(fill=tk.X, pady=(0, 5))
        config_grid.columnconfigure(1, weight=1)
        config_grid.columnconfigure(3, weight=1)

        # 主机地址和端口
        ttk.Label(config_grid, text="主机:", width=6).grid(row=0, column=0, sticky=tk.W, padx=(0, 2))
        self.main_app.ai_host_entry = ttk.Entry(config_grid, width=12)
        self.main_app.ai_host_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))

        ttk.Label(config_grid, text="发送:", width=6).grid(row=0, column=2, sticky=tk.W)
        self.main_app.ai_send_port_entry = ttk.Entry(config_grid, width=6)
        self.main_app.ai_send_port_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 5))

        ttk.Label(config_grid, text="接收:", width=6).grid(row=0, column=4, sticky=tk.W)
        self.main_app.ai_receive_port_entry = ttk.Entry(config_grid, width=6)
        self.main_app.ai_receive_port_entry.grid(row=0, column=5, sticky=(tk.W, tk.E))

        # 状态显示行
        status_frame = ttk.Frame(vrc_control_frame)
        status_frame.pack(fill=tk.X, pady=(5, 2))

        ttk.Label(status_frame, text="音频服务:", width=10).pack(side=tk.LEFT, padx=(0, 2))
        self.main_app.ai_audio_status_label = ttk.Label(status_frame, text="未检查", foreground="gray", width=10)
        self.main_app.ai_audio_status_label.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(status_frame, text="VRC连接:", width=10).pack(side=tk.LEFT, padx=(0, 2))
        self.main_app.ai_osc_status_label = ttk.Label(status_frame, text="未连接", foreground="red", width=20)
        self.main_app.ai_osc_status_label.pack(side=tk.LEFT, padx=(0, 5))

        # 按钮控制行
        button_frame = ttk.Frame(vrc_control_frame)
        button_frame.pack(fill=tk.X, pady=(2, 5))

        self.main_app.save_ai_config_btn = ttk.Button(button_frame, text="保存配置", command=self.save_ai_vrc_config, width=10)
        self.main_app.save_ai_config_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.main_app.ai_osc_connect_btn = ttk.Button(button_frame, text="连接VRC", command=self.toggle_ai_osc_connection, width=10)
        self.main_app.ai_osc_connect_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.main_app.refresh_audio_btn = ttk.Button(button_frame, text="刷新音频", command=self.refresh_audio_service_status, width=10)
        self.main_app.refresh_audio_btn.pack(side=tk.LEFT)

        self.load_ai_vrc_config_from_file()

        # VRC消息发送区域
        vrc_message_frame = ttk.LabelFrame(parent_frame, text="VRC消息控制", padding="5")
        vrc_message_frame.pack(fill=tk.X, pady=(5, 5))

        text_message_row = ttk.Frame(vrc_message_frame)
        text_message_row.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(text_message_row, text="发送文本:", width=6).pack(side=tk.LEFT)
        self.main_app.ai_text_entry = ttk.Entry(text_message_row)
        self.main_app.ai_text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.main_app.ai_text_entry.bind("<Return>", lambda e: self.ai_send_text_message())

        self.main_app.ai_send_text_btn = ttk.Button(text_message_row, text="发送", command=self.ai_send_text_message, width=6)
        self.main_app.ai_send_text_btn.pack(side=tk.LEFT)

        voice_upload_row = ttk.Frame(vrc_message_frame)
        voice_upload_row.pack(fill=tk.X, pady=(0, 5))

        self.main_app.ai_upload_voice_btn = ttk.Button(voice_upload_row, text="上传语音文件", command=self.ai_upload_voice_file, width=12)
        self.main_app.ai_upload_voice_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.main_app.ai_voice_file_label = ttk.Label(voice_upload_row, text="未选择文件", foreground="gray")
        self.main_app.ai_voice_file_label.pack(side=tk.LEFT, padx=(5, 0))

        voicevox_control_row = ttk.Frame(vrc_message_frame)
        voicevox_control_row.pack(fill=tk.X, pady=(5, 0))

        self.main_app.ai_voicevox_generate_btn = ttk.Button(voicevox_control_row, text="生成并发送语音", command=self.main_app.voicevox_area.ai_generate_and_send_voice, width=15)
        self.main_app.ai_voicevox_generate_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(voicevox_control_row, text="内容:", width=5).pack(side=tk.LEFT)
        self.main_app.ai_voicevox_text_entry = ttk.Entry(voicevox_control_row)
        self.main_app.ai_voicevox_text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.main_app.ai_voicevox_text_entry.bind("<Return>", lambda e: self.main_app.voicevox_area.ai_generate_and_send_voice())

        self.init_movement_controls()
        self.init_scenario_system()

    
    def on_scenario_change(self, event=None):
        """场景切换事件"""
        try:
            selected_scenario = self.main_app.scenario_var.get()
            self.current_scenario = selected_scenario
            self.update_scenario_description()
            self.main_app.log(f"切换场景: {selected_scenario}")
        except Exception as e:
            self.main_app.log(f"场景切换异常: {e}")
    
    def update_scenario_description(self):
        """更新场景描述"""
        try:
            if hasattr(self.main_app, 'scenario_desc_label') and self.current_scenario in self.scenario_data:
                description = self.scenario_data[self.current_scenario].get("description", "")
                self.main_app.scenario_desc_label.config(text=description)
        except Exception as e:
            self.main_app.log(f"更新场景描述异常: {e}")
    
    def apply_scenario(self):
        """应用当前场景"""
        try:
            if self.current_scenario not in self.scenario_data:
                self.main_app.log(f"未找到场景: {self.current_scenario}")
                return

            scenario_info = self.scenario_data[self.current_scenario]
            system_prompt = scenario_info.get("system_prompt", "")

            # 设置LLM系统提示
            self.main_app.config.set('LLM', 'system_prompt', system_prompt)
            self.main_app.log(f"应用场景: {self.current_scenario}")
            self.main_app.log(f"系统提示已更新")
        except Exception as e:
            self.main_app.log(f"应用场景异常: {e}")
    
    def init_movement_controls(self):
        """初始化移动控制"""
        try:
            self.movement_speed = 1.0
            if hasattr(self.main_app, 'movement_speed_var'):
                self.main_app.movement_speed_var.set(self.movement_speed)
            
            # 设置OSC客户端
            if hasattr(self.main_app, 'client') and self.main_app.client:
                self.ai_osc_client = self.main_app.client
                self.main_app.log("AI移动控制OSC客户端已连接")
        except Exception as e:
            self.main_app.log(f"初始化移动控制异常: {e}")
    
    def set_osc_client(self, osc_client):
        """设置OSC客户端"""
        try:
            self.ai_osc_client = osc_client
            if osc_client:
                self.main_app.log("AI移动控制OSC客户端已更新")
                # 测试连接
                self.test_osc_connection()
            else:
                self.main_app.log("AI移动控制OSC客户端已断开")
        except Exception as e:
            self.main_app.log(f"设置OSC客户端异常: {e}")
    
    def create_ai_osc_client(self):
        """创建独立的AI角色OSC客户端"""
        try:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            from src.osc_client import OSCClient
            
            # 直接创建OSC客户端，而不是VRChatController
            ai_client = OSCClient(
                host=self.ai_host,
                send_port=self.ai_send_port,
                receive_port=self.ai_receive_port
            )
            
            self.ai_osc_client = ai_client
            self.main_app.log(f"AI角色OSC客户端已创建: {self.ai_host}:{self.ai_send_port}")
            
            # 测试AI角色连接
            self.test_osc_connection()
            return True
            
        except Exception as e:
            self.main_app.log(f"创建AI角色OSC客户端失败: {e}")
            self.main_app.log(f"错误详情: {str(e)}")
            return False
    
    def connect_ai_vrchat(self):
        """连接到AI角色VRChat"""
        try:
            if self.auto_connect:
                self.main_app.log("自动连接AI角色VRChat...")
                if self.create_ai_osc_client():
                    self.ai_is_connected = True
                    self.main_app.log("✓ AI角色VRChat连接成功")
                else:
                    self.main_app.log("✗ AI角色VRChat连接失败")
            else:
                self.main_app.log("AI角色VRChat自动连接已禁用")
        except Exception as e:
            self.main_app.log(f"连接AI角色VRChat异常: {e}")
    
    def save_ai_character_config(self, character_name=None, personality=None):
        """保存AI角色配置"""
        try:
            if character_name:
                self.last_character_name = character_name
                if personality:
                    self.last_character_personality = personality
                self.main_app.config.set_ai_character_last_info(character_name, personality or self.last_character_personality)
                self.main_app.log(f"AI角色配置已保存: {character_name}")
                
                # 更新配置显示
                self.update_ai_config_display()
        except Exception as e:
            self.main_app.log(f"保存AI角色配置异常: {e}")
    
    def update_ai_config_display(self):
        """更新AI角色配置显示"""
        try:
            ai_info_text = f"主机: {self.ai_host}:{self.ai_send_port} | 自动连接: {'是' if self.auto_connect else '否'}"
            if self.last_character_name:
                ai_info_text += f" | 角色: {self.last_character_name}"
            
            if hasattr(self.main_app, 'ai_config_label'):
                self.main_app.ai_config_label.config(text=ai_info_text)
        except Exception as e:
            self.main_app.log(f"更新AI配置显示异常: {e}")
    
    def test_osc_connection(self):
        """测试OSC连接是否正常"""
        try:
            if self.ai_osc_client:
                # 发送一个安全的测试消息（发送chatbox消息测试连接）
                success = self.ai_osc_client.send_chatbox_message("AI移动控制已连接", send_immediately=False, show_in_chatbox=False)
                if success:
                    self.main_app.log("✓ AI OSC连接测试成功 - AI移动控制已就绪")
                    return True
                else:
                    self.main_app.log("✗ AI OSC连接测试失败")
                    return False
            else:
                self.main_app.log("✗ AI OSC客户端未设置")
                return False
        except Exception as e:
            self.main_app.log(f"AI OSC连接测试异常: {e}")
            # 尝试简单的消息发送测试
            try:
                if self.ai_osc_client:
                    success = self.ai_osc_client.send_message("/test", 1.0)
                    if success:
                        self.main_app.log("✓ AI OSC基本连接测试成功")
                        return True
            except Exception as e2:
                self.main_app.log(f"基本连接测试也失败: {e2}")
            return False
    
    def send_osc_command(self, address: str, value, action_name: str):
        """发送OSC命令的通用方法"""
        try:
            # 详细的连接状态检查
            if not hasattr(self, 'ai_osc_client') or not self.ai_osc_client:
                self.main_app.log(f"✗ AI OSC客户端未初始化，无法执行{action_name}")
                self.main_app.log(f"   连接状态: ai_is_connected={getattr(self, 'ai_is_connected', False)}")
                self.main_app.log(f"   OSC客户端: {hasattr(self, 'ai_osc_client')} / {getattr(self, 'ai_osc_client', None)}")
                return False
            
            # 调试信息
            self.main_app.log(f"发送OSC命令: {address} = {value} 到 {self.ai_host}:{self.ai_send_port}")
            
            success = self.ai_osc_client.send_message(address, value)
            if success:
                self.main_app.log(f"✓ {action_name}执行成功")
                return True
            else:
                self.main_app.log(f"✗ {action_name}发送失败 - OSC客户端返回失败")
                return False
        except Exception as e:
            self.main_app.log(f"✗ {action_name}异常: {e}")
            import traceback
            self.main_app.log(f"   异常详情: {traceback.format_exc()}")
            return False
    
    def update_speed_label(self, *args):
        """更新移动速度标签显示"""
        try:
            if hasattr(self.main_app, 'movement_speed_var') and hasattr(self.main_app, 'movement_speed_label'):
                speed = self.main_app.movement_speed_var.get()
                self.movement_speed = speed
                self.main_app.movement_speed_label.config(text=f"{speed:.1f}")
        except Exception as e:
            self.main_app.log(f"更新移动速度标签异常: {e}")
    
    # ���6�p
    def move_forward(self):
        """前进"""
        self.send_osc_command("/input/Vertical", self.movement_speed, f"前进 (速度: {self.movement_speed})")
    
    def move_backward(self):
        """后退"""
        self.send_osc_command("/input/Vertical", -self.movement_speed, f"后退 (速度: {self.movement_speed})")
    
    def strafe_left(self):
        """左移"""
        self.send_osc_command("/input/Horizontal", -self.movement_speed, f"左移 (速度: {self.movement_speed})")
    
    def strafe_right(self):
        """右移"""
        self.send_osc_command("/input/Horizontal", self.movement_speed, f"右移 (速度: {self.movement_speed})")
    
    def jump(self):
        """跳跃"""
        if self.send_osc_command("/input/Jump", 1, "跳跃"):
            # 跳跃后自动复位
            self.main_app.root.after(100, lambda: self.send_osc_command("/input/Jump", 0, "跳跃复位"))
    
    def turn_left(self):
        """左转"""
        self.send_osc_command("/input/LookHorizontal", -self.movement_speed * 0.5, "左转")
    
    def turn_right(self):
        """右转"""
        self.send_osc_command("/input/LookHorizontal", self.movement_speed * 0.5, "右转")
    
    def look_up(self):
        """上看（VRChat OSC不支持垂直视角，改为右转）"""
        self.send_osc_command("/input/LookHorizontal", self.movement_speed * 0.5, "上转（右转）")
    
    def look_down(self):
        """下看（VRChat OSC不支持垂直视角，改为左转）"""  
        self.send_osc_command("/input/LookHorizontal", -self.movement_speed * 0.5, "下转（左转）")
    
    # 停止控制方法
    def stop_movement(self):
        """停止移动"""
        self.send_osc_command("/input/Vertical", 0.0, "停止前后移动")
        self.send_osc_command("/input/Horizontal", 0.0, "停止左右移动")
    
    def stop_look(self):
        """停止镜头移动"""
        # 只停止水平视角，因为VRChat OSC不支持垂直视角控制
        self.send_osc_command("/input/LookHorizontal", 0.0, "停止镜头移动")
    
    # 跑步控制（VRChat OSC没有专门的蹲下参数，使用跑步控制代替）
    def crouch(self):
        """切换为走路模式（取消跑步）"""
        try:
            if self.ai_osc_client:
                self.ai_osc_client.send_message("/input/Run", 0)  # 取消跑步，使用走路模式
                self.main_app.log("切换为走路模式")
        except Exception as e:
            self.main_app.log(f"切换走路模式异常: {e}")
    
    def stop_crouch(self):
        """恢复跑步模式"""
        try:
            if self.ai_osc_client:
                self.ai_osc_client.send_message("/input/Run", 1)  # 恢复跑步模式
                self.main_app.log("恢复跑步模式")
        except Exception as e:
            self.main_app.log(f"恢复跑步模式异常: {e}")
    
    # 斜着移动方法
    def move_forward_left(self):
        """左前移动"""
        try:
            if self.ai_osc_client:
                self.ai_osc_client.send_message("/input/Vertical", self.movement_speed)
                self.ai_osc_client.send_message("/input/Horizontal", -self.movement_speed)
                self.main_app.log(f"左前移动 (速度: {self.movement_speed})")
        except Exception as e:
            self.main_app.log(f"左前移动异常: {e}")
    
    def move_forward_right(self):
        """右前移动"""
        try:
            if self.ai_osc_client:
                self.ai_osc_client.send_message("/input/Vertical", self.movement_speed)
                self.ai_osc_client.send_message("/input/Horizontal", self.movement_speed)
                self.main_app.log(f"右前移动 (速度: {self.movement_speed})")
        except Exception as e:
            self.main_app.log(f"右前移动异常: {e}")
    
    def move_backward_left(self):
        """左后移动"""
        try:
            if self.ai_osc_client:
                self.ai_osc_client.send_message("/input/Vertical", -self.movement_speed)
                self.ai_osc_client.send_message("/input/Horizontal", -self.movement_speed)
                self.main_app.log(f"左后移动 (速度: {self.movement_speed})")
        except Exception as e:
            self.main_app.log(f"左后移动异常: {e}")
    
    def move_backward_right(self):
        """右后移动"""
        try:
            if self.ai_osc_client:
                self.ai_osc_client.send_message("/input/Vertical", -self.movement_speed)
                self.ai_osc_client.send_message("/input/Horizontal", self.movement_speed)
                self.main_app.log(f"右后移动 (速度: {self.movement_speed})")
        except Exception as e:
            self.main_app.log(f"右后移动异常: {e}")
    
    # 斜向镜头控制方法（VRChat OSC只支持水平转向）
    def look_up_left(self):
        """左上看（实际为左转）"""
        self.send_osc_command("/input/LookHorizontal", -self.movement_speed * 0.5, "左上转")
    
    def look_up_right(self):
        """右上看（实际为右转）"""
        self.send_osc_command("/input/LookHorizontal", self.movement_speed * 0.5, "右上转")
    
    def look_down_left(self):
        """左下看（实际为左转）"""
        self.send_osc_command("/input/LookHorizontal", -self.movement_speed * 0.5, "左下转")
    
    def look_down_right(self):
        """右下看（实际为右转）"""
        self.send_osc_command("/input/LookHorizontal", self.movement_speed * 0.5, "右下转")

    
    def init_scenario_system(self):
        """初始化场景系统"""
        try:
            self.load_scenario_data()
            self.current_scenario = "学習疲労"
            if hasattr(self.main_app, 'scenario_var'):
                self.main_app.scenario_var.set(self.current_scenario)
            self.update_scenario_description()
        except Exception as e:
            self.main_app.log(f"初始化场景系统异常: {e}")
    
    def load_scenario_data(self):
        """加载场景数据"""
        try:
            scenario_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'scenarios.json')
            if os.path.exists(scenario_file):
                with open(scenario_file, 'r', encoding='utf-8') as f:
                    self.scenario_data = json.load(f)
                self.main_app.log("场景数据加载成功")
            else:
                self.main_app.log("场景文件不存在，创建默认场景")
                self.create_default_scenario_data()
        except Exception as e:
            self.main_app.log(f"加载场景数据失败: {e}")
            self.create_default_scenario_data()
    
    def create_default_scenario_data(self):
        """创建默认场景数据"""
        try:
            self.scenario_data = {
                "学習疲労": {
                    "description": "学习疲劳时的支持场景",
                    "system_prompt": "你是一个善于鼓励学生的AI助手。"
                },
                "研究ストレス": {
                    "description": "研究压力大的支持场景",
                    "system_prompt": "你是一个善于缓解科研压力的AI助手。"
                },
                "就職活動不安": {
                    "description": "就业活动焦虑的支持场景",
                    "system_prompt": "你是一个善于安慰求职者的AI助手。"
                }
            }
            with open("scenarios.json", 'w', encoding='utf-8') as f:
                json.dump(self.scenario_data, f, ensure_ascii=False, indent=2)
            self.main_app.log("默认场景数据已创建")
        except Exception as e:
            self.main_app.log(f"创建默认场景数据异常: {e}")
    
    def load_ai_vrc_config_from_file(self):
        """加载AI VRC配置"""
        try:
            if hasattr(self.main_app, 'config'):
                ai_host = self.main_app.config.get('AI_VRC', 'host', '127.0.0.1')
                ai_send_port = self.main_app.config.get('AI_VRC', 'send_port', '9000')
                ai_receive_port = self.main_app.config.get('AI_VRC', 'receive_port', '9001')
                if hasattr(self.main_app, 'ai_host_entry'):
                    self.main_app.ai_host_entry.delete(0, tk.END)
                    self.main_app.ai_host_entry.insert(0, ai_host)
                if hasattr(self.main_app, 'ai_send_port_entry'):
                    self.main_app.ai_send_port_entry.delete(0, tk.END)
                    self.main_app.ai_send_port_entry.insert(0, str(ai_send_port))
                if hasattr(self.main_app, 'ai_receive_port_entry'):
                    self.main_app.ai_receive_port_entry.delete(0, tk.END)
                    self.main_app.ai_receive_port_entry.insert(0, str(ai_receive_port))
        except Exception as e:
            self.main_app.log(f"加载AI VRC配置异常: {e}")
    
    def save_ai_vrc_config(self):
        """保存AI VRC配置"""
        try:
            if hasattr(self.main_app, 'config'):
                ai_host = self.main_app.ai_host_entry.get().strip() if hasattr(self.main_app, 'ai_host_entry') else '127.0.0.1'
                ai_send_port = self.main_app.ai_send_port_entry.get().strip() if hasattr(self.main_app, 'ai_send_port_entry') else '9000'
                ai_receive_port = self.main_app.ai_receive_port_entry.get().strip() if hasattr(self.main_app, 'ai_receive_port_entry') else '9001'
                self.main_app.config.set('AI_VRC', 'host', ai_host)
                self.main_app.config.set('AI_VRC', 'send_port', ai_send_port)
                self.main_app.config.set('AI_VRC', 'receive_port', ai_receive_port)
                messagebox.showinfo("保存成功", "AI VRC配置已保存")
                self.main_app.log("AI VRC配置已保存")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存AI VRC配置失败: {e}")
            self.main_app.log(f"保存AI VRC配置异常: {e}")
    
    def toggle_ai_osc_connection(self):
        """切换AI OSC连接状态"""
        try:
            if not self.ai_is_connected:
                self.connect_ai_osc()
            else:
                self.disconnect_ai_osc()
        except Exception as e:
            self.main_app.log(f"切换AI OSC连接异常: {e}")
    
    def connect_ai_osc(self):
        """连接AI OSC"""
        try:
            # 先创建OSC客户端
            if self.create_ai_osc_client():
                self.ai_is_connected = True
                if hasattr(self.main_app, 'ai_osc_status_label'):
                    self.main_app.ai_osc_status_label.config(text="已连接", foreground="green")
                if hasattr(self.main_app, 'ai_osc_connect_btn'):
                    self.main_app.ai_osc_connect_btn.config(text="断开VRC")
                self.main_app.log("AI OSC已连接")
                return True
            else:
                self.main_app.log("AI OSC连接失败")
                return False
        except Exception as e:
            self.main_app.log(f"连接AI OSC异常: {e}")
            return False
    
    def disconnect_ai_osc(self):
        """断开AI OSC"""
        try:
            self.ai_is_connected = False
            
            # 清理OSC客户端
            if hasattr(self, 'ai_osc_client') and self.ai_osc_client:
                try:
                    if hasattr(self.ai_osc_client, 'stop_server'):
                        self.ai_osc_client.stop_server()
                except:
                    pass
                self.ai_osc_client = None
            
            if hasattr(self.main_app, 'ai_osc_status_label'):
                self.main_app.ai_osc_status_label.config(text="未连接", foreground="red")
            if hasattr(self.main_app, 'ai_osc_connect_btn'):
                self.main_app.ai_osc_connect_btn.config(text="连接VRC")
            self.main_app.log("AI OSC已断开")
        except Exception as e:
            self.main_app.log(f"断开AI OSC异常: {e}")
    
    def refresh_audio_service_status(self):
        """刷新音频服务状态"""
        try:
            if hasattr(self.main_app, 'ai_audio_status_label'):
                self.main_app.ai_audio_status_label.config(text="正常", foreground="green")
            self.main_app.log("音频服务已刷新")
        except Exception as e:
            self.main_app.log(f"刷新音频服务状态异常: {e}")

    
    def ai_send_text_message(self):
        """AI发送文本消息"""
        try:
            if not hasattr(self.main_app, 'ai_text_entry'):
                return
            message = self.main_app.ai_text_entry.get().strip()
            if not message:
                return
            if not self.ai_is_connected:
                messagebox.showwarning("提示", "请先连接VRC")
                return
            self.main_app.log(f"[AI文本] {message}")
            self.main_app.ai_text_entry.delete(0, tk.END)
        except Exception as e:
            self.main_app.log(f"AI发送文本消息异常: {e}")
    
    def ai_upload_voice_file(self):
        """AI上传语音文件"""
        try:
            file_path = filedialog.askopenfilename(
                title="选择语音文件",
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
                self.main_app.log(f"已选择AI语音文件: {os.path.basename(file_path)}")
                audio_data, sample_rate = sf.read(file_path)
                if len(audio_data.shape) > 1:
                    audio_data = np.mean(audio_data, axis=1)
                audio_data = audio_data.astype(np.float32)
                self.ai_selected_voice_file = file_path
                if hasattr(self.main_app, 'ai_voice_file_label'):
                    self.main_app.ai_voice_file_label.config(
                        text=f"已选择: {os.path.basename(file_path)}", 
                        foreground="blue"
                    )
                self.main_app.log(f"AI语音文件已加载")
            except Exception as load_error:
                messagebox.showerror("加载失败", f"加载语音文件失败: {load_error}")
                self.main_app.log(f"加载AI语音文件异常: {load_error}")
        except Exception as e:
            self.main_app.log(f"AI上传语音文件异常: {e}")