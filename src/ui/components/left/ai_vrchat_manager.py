# -*- coding: utf-8 -*-
"""
AI VRChat管理UI功能类
负责处理AI VRChat相关的UI交互逻辑
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os


class AIVRChatManager:
    """AI VRChat管理UI功能类"""
    
    def __init__(self, main_app):
        """
        初始化AI VRChat管理器
        
        Args:
            main_app: 主应用程序实例
        """
        self.main_app = main_app
        self.current_scenario = "学習疲労"
        self.scenario_data = {}
        self.ai_osc_client = None
        self.ai_is_connected = False
        self.ai_selected_voice_file = None
        self.movement_speed = 1.0
        self.is_walking_mode = False  # 走路模式状态
        
        # 读取AI_CHARACTER_VRC配置
        self._load_ai_config()
    
    def _load_ai_config(self):
        """加载AI角色配置"""
        self.ai_host = self.main_app.config.ai_character_host
        self.ai_send_port = self.main_app.config.ai_character_send_port  
        self.ai_receive_port = self.main_app.config.ai_character_receive_port
        self.auto_connect = self.main_app.config.ai_character_auto_connect
        self.connection_timeout = self.main_app.config.ai_character_connection_timeout
        self.last_character_name = self.main_app.config.ai_character_last_name
        self.last_character_personality = self.main_app.config.ai_character_last_personality
    
    def setup_ai_character_interface(self, parent_frame):
        """设置AI角色管理界面"""
        # 场景选择区域
        self._setup_scenario_section(parent_frame)
        
        # AI角色移动控制区域
        self._setup_movement_section(parent_frame)
        
        # AI OSC连接区域
        self._setup_connection_section(parent_frame)
        
        # AI语音控制区域
        self._setup_voice_section(parent_frame)
        
        # 加载场景数据
        self._load_scenario_data()
    
    def _setup_scenario_section(self, parent_frame):
        """设置场景选择区域"""
        scenario_frame = ttk.LabelFrame(parent_frame, text="AI场景选择", padding="5")
        scenario_frame.pack(fill=tk.X, pady=(0, 5))

        scenario_row = ttk.Frame(scenario_frame)
        scenario_row.pack(fill=tk.X)

        ttk.Label(scenario_row, text="当前场景", width=6).pack(side=tk.LEFT)
        self.main_app.scenario_var = tk.StringVar(value="学習疲労")
        self.main_app.scenario_combo = ttk.Combobox(scenario_row, textvariable=self.main_app.scenario_var,
                                         values=["学習疲労", "研究ストレス", "就職活動不安"],
                                         width=15, state="readonly")
        self.main_app.scenario_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.main_app.scenario_combo.bind('<<ComboboxSelected>>', self.on_scenario_change)

        # 应用场景按钮
        self.main_app.apply_scenario_btn = ttk.Button(scenario_row, text="应用场景", 
                                                     command=self.apply_scenario, width=10)
        self.main_app.apply_scenario_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 运行模式选择（已禁用）
        ttk.Label(scenario_row, text="模式", width=5).pack(side=tk.LEFT)
        self.main_app.runtime_mode_var = tk.StringVar(value="user")
        self.main_app.runtime_mode_combo = ttk.Combobox(scenario_row, textvariable=self.main_app.runtime_mode_var,
                                             values=["user"],
                                             width=10, state="disabled")
        self.main_app.runtime_mode_combo.pack(side=tk.LEFT, padx=(0, 5))

        # 场景描述标签
        self.main_app.scenario_desc_label = ttk.Label(scenario_frame, text="学習疲労・勉強に疲れた時のサポート", 
                                           foreground="gray", font=("", 8))
        self.main_app.scenario_desc_label.pack(fill=tk.X, pady=(5, 0))
    
    def _setup_movement_section(self, parent_frame):
        """设置移动控制区域"""
        movement_frame = ttk.LabelFrame(parent_frame, text="AI角色移动", padding="5")
        movement_frame.pack(fill=tk.X, pady=(0, 5))

        # 移动控制容器
        control_container = ttk.Frame(movement_frame)
        control_container.pack(pady=(5, 0))

        # 左侧: 移动控制
        movement_grid = ttk.Frame(control_container)
        movement_grid.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(movement_grid, text="移动控制", font=("", 9, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 5))

        # 创建移动按钮网格
        self._create_movement_buttons(movement_grid)

        # 右侧: 镜头控制
        camera_grid = ttk.Frame(control_container)
        camera_grid.pack(side=tk.LEFT, padx=(20, 0))

        ttk.Label(camera_grid, text="镜头控制", font=("", 9, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 5))

        # 创建镜头控制按钮
        self._create_camera_buttons(camera_grid)

        # 移动速度控制
        speed_frame = ttk.Frame(movement_frame)
        speed_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(speed_frame, text="移动速度:").pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.movement_speed_var = tk.DoubleVar(value=1.0)
        self.main_app.movement_speed_scale = ttk.Scale(speed_frame, from_=0.1, to=3.0,
                                                      variable=self.main_app.movement_speed_var,
                                                      orient='horizontal',
                                                      command=self.on_movement_speed_changed)
        self.main_app.movement_speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.main_app.movement_speed_label = ttk.Label(speed_frame, text="1.0x", width=8)
        self.main_app.movement_speed_label.pack(side=tk.LEFT)

        # 移动模式切换
        mode_frame = ttk.Frame(movement_frame)
        mode_frame.pack(fill=tk.X, pady=(5, 0))

        self.main_app.walking_mode_var = tk.BooleanVar(value=False)
        self.main_app.walking_mode_check = ttk.Checkbutton(mode_frame, text="走路模式（勾选=走路，不勾选=跑步）",
                                                          variable=self.main_app.walking_mode_var,
                                                          command=self.toggle_walking_mode)
        self.main_app.walking_mode_check.pack(side=tk.LEFT)
    
    def _create_movement_buttons(self, parent):
        """创建移动按钮"""
        # 第一行：斜向前
        self.main_app.move_forward_left_btn = ttk.Button(parent, text="↖", width=6)
        self.main_app.move_forward_left_btn.grid(row=1, column=0, padx=2, pady=2)
        self.main_app.move_forward_left_btn.bind("<ButtonPress-1>", lambda e: self.move_forward_left())
        self.main_app.move_forward_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.move_forward_btn = ttk.Button(parent, text="↑", width=6)
        self.main_app.move_forward_btn.grid(row=1, column=1, padx=2, pady=2)
        self.main_app.move_forward_btn.bind("<ButtonPress-1>", lambda e: self.move_forward())
        self.main_app.move_forward_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.move_forward_right_btn = ttk.Button(parent, text="↗", width=6)
        self.main_app.move_forward_right_btn.grid(row=1, column=2, padx=2, pady=2)
        self.main_app.move_forward_right_btn.bind("<ButtonPress-1>", lambda e: self.move_forward_right())
        self.main_app.move_forward_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        # 第二行：侧向移动
        self.main_app.strafe_left_btn = ttk.Button(parent, text="←", width=6)
        self.main_app.strafe_left_btn.grid(row=2, column=0, padx=2, pady=2)
        self.main_app.strafe_left_btn.bind("<ButtonPress-1>", lambda e: self.strafe_left())
        self.main_app.strafe_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.crouch_btn = ttk.Button(parent, text="蹲下", width=6)
        self.main_app.crouch_btn.grid(row=2, column=1, padx=2, pady=2)
        self.main_app.crouch_btn.bind("<ButtonPress-1>", lambda e: self.crouch())
        self.main_app.crouch_btn.bind("<ButtonRelease-1>", lambda e: self.stop_crouch())

        self.main_app.strafe_right_btn = ttk.Button(parent, text="→", width=6)
        self.main_app.strafe_right_btn.grid(row=2, column=2, padx=2, pady=2)
        self.main_app.strafe_right_btn.bind("<ButtonPress-1>", lambda e: self.strafe_right())
        self.main_app.strafe_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        # 第三行：斜向后
        self.main_app.move_backward_left_btn = ttk.Button(parent, text="↙", width=6)
        self.main_app.move_backward_left_btn.grid(row=3, column=0, padx=2, pady=2)
        self.main_app.move_backward_left_btn.bind("<ButtonPress-1>", lambda e: self.move_backward_left())
        self.main_app.move_backward_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.move_backward_btn = ttk.Button(parent, text="↓", width=6)
        self.main_app.move_backward_btn.grid(row=3, column=1, padx=2, pady=2)
        self.main_app.move_backward_btn.bind("<ButtonPress-1>", lambda e: self.move_backward())
        self.main_app.move_backward_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        self.main_app.move_backward_right_btn = ttk.Button(parent, text="↘", width=6)
        self.main_app.move_backward_right_btn.grid(row=3, column=2, padx=2, pady=2)
        self.main_app.move_backward_right_btn.bind("<ButtonPress-1>", lambda e: self.move_backward_right())
        self.main_app.move_backward_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_movement())

        # 第四行：跳跃
        self.main_app.jump_btn = ttk.Button(parent, text="跳跃", width=6)
        self.main_app.jump_btn.grid(row=4, column=1, padx=2, pady=2)
        self.main_app.jump_btn.bind("<Button-1>", lambda e: self.jump())
    
    def _create_camera_buttons(self, parent):
        """创建镜头控制按钮"""
        # 第一行：上方视角
        self.main_app.look_up_left_btn = ttk.Button(parent, text="↖视角", width=8)
        self.main_app.look_up_left_btn.grid(row=1, column=0, padx=2, pady=2)
        self.main_app.look_up_left_btn.bind("<ButtonPress-1>", lambda e: self.look_up_left())
        self.main_app.look_up_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_up_btn = ttk.Button(parent, text="↑视角", width=8)
        self.main_app.look_up_btn.grid(row=1, column=1, padx=2, pady=2)
        self.main_app.look_up_btn.bind("<ButtonPress-1>", lambda e: self.look_up())
        self.main_app.look_up_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_up_right_btn = ttk.Button(parent, text="↗视角", width=8)
        self.main_app.look_up_right_btn.grid(row=1, column=2, padx=2, pady=2)
        self.main_app.look_up_right_btn.bind("<ButtonPress-1>", lambda e: self.look_up_right())
        self.main_app.look_up_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        # 第二行：水平视角
        self.main_app.turn_left_btn = ttk.Button(parent, text="←转向", width=8)
        self.main_app.turn_left_btn.grid(row=2, column=0, padx=2, pady=2)
        self.main_app.turn_left_btn.bind("<ButtonPress-1>", lambda e: self.turn_left())
        self.main_app.turn_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.stop_look_btn = ttk.Button(parent, text="停止", width=8)
        self.main_app.stop_look_btn.grid(row=2, column=1, padx=2, pady=2)
        self.main_app.stop_look_btn.bind("<Button-1>", lambda e: self.stop_look())

        self.main_app.turn_right_btn = ttk.Button(parent, text="→转向", width=8)
        self.main_app.turn_right_btn.grid(row=2, column=2, padx=2, pady=2)
        self.main_app.turn_right_btn.bind("<ButtonPress-1>", lambda e: self.turn_right())
        self.main_app.turn_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        # 第三行：下方视角
        self.main_app.look_down_left_btn = ttk.Button(parent, text="↙视角", width=8)
        self.main_app.look_down_left_btn.grid(row=3, column=0, padx=2, pady=2)
        self.main_app.look_down_left_btn.bind("<ButtonPress-1>", lambda e: self.look_down_left())
        self.main_app.look_down_left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_down_btn = ttk.Button(parent, text="↓视角", width=8)
        self.main_app.look_down_btn.grid(row=3, column=1, padx=2, pady=2)
        self.main_app.look_down_btn.bind("<ButtonPress-1>", lambda e: self.look_down())
        self.main_app.look_down_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())

        self.main_app.look_down_right_btn = ttk.Button(parent, text="↘视角", width=8)
        self.main_app.look_down_right_btn.grid(row=3, column=2, padx=2, pady=2)
        self.main_app.look_down_right_btn.bind("<ButtonPress-1>", lambda e: self.look_down_right())
        self.main_app.look_down_right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_look())
    
    def _setup_connection_section(self, parent_frame):
        """设置连接区域"""
        connection_frame = ttk.LabelFrame(parent_frame, text="AI OSC连接", padding="5")
        connection_frame.pack(fill=tk.X, pady=(0, 5))

        # 连接设置行
        connection_row = ttk.Frame(connection_frame)
        connection_row.pack(fill=tk.X)

        # AI Host
        ttk.Label(connection_row, text="AI主机:", width=8).pack(side=tk.LEFT)
        self.main_app.ai_host_var = tk.StringVar(value=self.ai_host)
        self.main_app.ai_host_entry = ttk.Entry(connection_row, textvariable=self.main_app.ai_host_var, width=15)
        self.main_app.ai_host_entry.pack(side=tk.LEFT, padx=(0, 10))

        # 发送端口
        ttk.Label(connection_row, text="发送端口:", width=8).pack(side=tk.LEFT)
        self.main_app.ai_send_port_var = tk.StringVar(value=str(self.ai_send_port))
        self.main_app.ai_send_port_entry = ttk.Entry(connection_row, textvariable=self.main_app.ai_send_port_var, width=8)
        self.main_app.ai_send_port_entry.pack(side=tk.LEFT, padx=(0, 10))

        # 连接按钮
        self.main_app.ai_osc_connect_btn = ttk.Button(connection_row, text="连接AI VRC", 
                                                     command=self.toggle_ai_osc_connection, width=10)
        self.main_app.ai_osc_connect_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 连接状态
        self.main_app.ai_connection_status_label = ttk.Label(connection_row, text="未连接", 
                                                           foreground="red", width=10)
        self.main_app.ai_connection_status_label.pack(side=tk.LEFT)
    
    def _setup_voice_section(self, parent_frame):
        """设置语音控制区域"""
        voice_frame = ttk.LabelFrame(parent_frame, text="AI语音生成", padding="5")
        voice_frame.pack(fill=tk.X, pady=(0, 5))

        # 语音输入行
        voice_input_frame = ttk.Frame(voice_frame)
        voice_input_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(voice_input_frame, text="文本:").pack(side=tk.LEFT, padx=(0, 5))
        self.main_app.ai_voicevox_text_entry = ttk.Entry(voice_input_frame, width=30)
        self.main_app.ai_voicevox_text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.main_app.ai_voicevox_text_entry.bind("<Return>", lambda e: self.ai_generate_and_send_voice())

        self.main_app.ai_generate_voice_btn = ttk.Button(voice_input_frame, text="生成语音", 
                                                        command=self.ai_generate_and_send_voice, width=10)
        self.main_app.ai_generate_voice_btn.pack(side=tk.LEFT)

        # 语音队列显示
        queue_frame = ttk.LabelFrame(voice_frame, text="语音队列", padding="5")
        queue_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.main_app.ai_voice_queue_text = tk.Text(queue_frame, height=6, state='disabled', font=("", 8))
        self.main_app.ai_voice_queue_text.pack(fill=tk.BOTH, expand=True)
    
    def _load_scenario_data(self):
        """加载场景数据"""
        try:
            scenario_file = "scenarios.json"
            if os.path.exists(scenario_file):
                with open(scenario_file, 'r', encoding='utf-8') as f:
                    self.scenario_data = json.load(f)
                self.main_app.log(f"场景数据已加载: {len(self.scenario_data)}个场景")
            else:
                self.main_app.log("scenarios.json文件不存在")
        except Exception as e:
            self.main_app.log(f"加载场景数据失败: {e}")
    
    def on_scenario_change(self, event=None):
        """场景选择变更事件"""
        selected_scenario = self.main_app.scenario_var.get()
        self.current_scenario = selected_scenario
        
        # 更新场景描述
        if selected_scenario in self.scenario_data:
            desc = self.scenario_data[selected_scenario].get("description", "")
            self.main_app.scenario_desc_label.config(text=desc)
        else:
            self.main_app.scenario_desc_label.config(text="场景描述未找到")
        
        self.main_app.log(f"已选择场景: {selected_scenario}")
    
    def apply_scenario(self):
        """应用当前选择的场景"""
        try:
            scenario_name = self.main_app.scenario_var.get()
            if scenario_name in self.scenario_data:
                scenario_info = self.scenario_data[scenario_name]
                
                # 这里可以应用场景相关的设置
                self.main_app.log(f"已应用场景: {scenario_name}")
                messagebox.showinfo("成功", f"场景 '{scenario_name}' 已应用")
            else:
                messagebox.showwarning("警告", f"找不到场景 '{scenario_name}' 的数据")
        except Exception as e:
            self.main_app.log(f"应用场景失败: {e}")
            messagebox.showerror("错误", f"应用场景失败: {e}")
    
    def toggle_ai_osc_connection(self):
        """切换AI OSC连接状态"""
        if not self.ai_is_connected:
            self.connect_ai_osc()
        else:
            self.disconnect_ai_osc()
    
    def connect_ai_osc(self):
        """连接AI OSC"""
        try:
            host = self.main_app.ai_host_var.get().strip()
            send_port = int(self.main_app.ai_send_port_var.get())
            
            # 这里需要实现AI OSC连接逻辑
            # 暂时模拟连接成功
            self.ai_is_connected = True
            self.main_app.ai_osc_connect_btn.config(text="断开AI VRC")
            self.main_app.ai_connection_status_label.config(text="已连接", foreground="green")
            self.main_app.log(f"AI OSC连接成功: {host}:{send_port}")
            
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {e}")
            self.main_app.log(f"AI OSC连接失败: {e}")
    
    def disconnect_ai_osc(self):
        """断开AI OSC连接"""
        try:
            # 这里需要实现AI OSC断开逻辑
            self.ai_is_connected = False
            self.main_app.ai_osc_connect_btn.config(text="连接AI VRC")
            self.main_app.ai_connection_status_label.config(text="未连接", foreground="red")
            self.main_app.log("AI OSC连接已断开")
            
        except Exception as e:
            self.main_app.log(f"断开AI OSC连接失败: {e}")
    
    # 移动控制方法
    def move_forward(self):
        """前进"""
        self._send_movement_command("forward", True)
    
    def move_backward(self):
        """后退"""
        self._send_movement_command("backward", True)
    
    def strafe_left(self):
        """左平移"""
        self._send_movement_command("strafe_left", True)
    
    def strafe_right(self):
        """右平移"""
        self._send_movement_command("strafe_right", True)
    
    def move_forward_left(self):
        """左前进"""
        self._send_movement_command("forward_left", True)
    
    def move_forward_right(self):
        """右前进"""
        self._send_movement_command("forward_right", True)
    
    def move_backward_left(self):
        """左后退"""
        self._send_movement_command("backward_left", True)
    
    def move_backward_right(self):
        """右后退"""
        self._send_movement_command("backward_right", True)
    
    def stop_movement(self):
        """停止移动"""
        self._send_movement_command("stop", False)
    
    def jump(self):
        """跳跃"""
        self._send_movement_command("jump", True, momentary=True)
    
    def crouch(self):
        """蹲下"""
        self._send_movement_command("crouch", True)
    
    def stop_crouch(self):
        """停止蹲下"""
        self._send_movement_command("crouch", False)
    
    # 镜头控制方法
    def look_up(self):
        """向上看"""
        self._send_look_command("up", True)
    
    def look_down(self):
        """向下看"""
        self._send_look_command("down", True)
    
    def turn_left(self):
        """左转"""
        self._send_look_command("left", True)
    
    def turn_right(self):
        """右转"""
        self._send_look_command("right", True)
    
    def look_up_left(self):
        """左上看"""
        self._send_look_command("up_left", True)
    
    def look_up_right(self):
        """右上看"""
        self._send_look_command("up_right", True)
    
    def look_down_left(self):
        """左下看"""
        self._send_look_command("down_left", True)
    
    def look_down_right(self):
        """右下看"""
        self._send_look_command("down_right", True)
    
    def stop_look(self):
        """停止镜头移动"""
        self._send_look_command("stop", False)
    
    def _send_movement_command(self, direction, state, momentary=False):
        """发送移动命令"""
        if not self.ai_is_connected:
            return
        
        try:
            # 这里需要实现实际的OSC命令发送
            speed = self.movement_speed
            walking = self.is_walking_mode
            
            self.main_app.log(f"移动命令: {direction}, 状态: {state}, 速度: {speed}, 走路模式: {walking}")
            
            # TODO: 实现实际的OSC发送逻辑
            
        except Exception as e:
            self.main_app.log(f"发送移动命令失败: {e}")
    
    def _send_look_command(self, direction, state):
        """发送视角命令"""
        if not self.ai_is_connected:
            return
        
        try:
            self.main_app.log(f"视角命令: {direction}, 状态: {state}")
            
            # TODO: 实现实际的OSC发送逻辑
            
        except Exception as e:
            self.main_app.log(f"发送视角命令失败: {e}")
    
    def on_movement_speed_changed(self, value):
        """移动速度变化回调"""
        self.movement_speed = float(value)
        self.main_app.movement_speed_label.config(text=f"{self.movement_speed:.1f}x")
    
    def toggle_walking_mode(self):
        """切换走路/跑步模式"""
        self.is_walking_mode = self.main_app.walking_mode_var.get()
        mode = "走路模式" if self.is_walking_mode else "跑步模式"
        self.main_app.log(f"移动模式切换为: {mode}")
    
    def ai_generate_and_send_voice(self):
        """生成并发送AI语音"""
        text = self.main_app.ai_voicevox_text_entry.get().strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入要合成的文本")
            return
        
        if not self.main_app.voicevox_connected:
            messagebox.showerror("VOICEVOX错误", "VOICEVOX未连接")
            return
        
        try:
            # 这里需要实现语音生成和发送逻辑
            # 暂时只记录日志
            self.main_app.log(f"AI语音生成请求: {text}")
            self.main_app.ai_voicevox_text_entry.delete(0, tk.END)
            
            # 更新语音队列显示
            self.update_voice_queue_display()
            
        except Exception as e:
            messagebox.showerror("错误", f"生成语音时出错: {e}")
            self.main_app.log(f"生成AI语音错误: {e}")
    
    def update_voice_queue_display(self):
        """更新语音队列显示"""
        try:
            # 这里需要获取实际的语音队列数据
            # 暂时显示示例数据
            display_text = "⏳ [示例] 等待处理的语音文本\n"
            
            self.main_app.ai_voice_queue_text.config(state='normal')
            self.main_app.ai_voice_queue_text.delete(1.0, tk.END)
            self.main_app.ai_voice_queue_text.insert(tk.END, display_text)
            self.main_app.ai_voice_queue_text.config(state='disabled')
            
        except Exception as e:
            self.main_app.log(f"更新语音队列显示错误: {e}")
    
    def set_osc_client(self, client):
        """设置OSC客户端"""
        self.ai_osc_client = client
    
    def cleanup(self):
        """清理资源"""
        if self.ai_is_connected:
            self.disconnect_ai_osc()
