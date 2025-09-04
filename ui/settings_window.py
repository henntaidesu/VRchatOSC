#!/usr/bin/env python3
"""
设置窗口 - 弹出式配置界面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from config_manager import config_manager


class SettingsWindow:
    """设置窗口类"""
    
    def __init__(self, parent, callback=None):
        """
        初始化设置窗口
        
        Args:
            parent: 父窗口
            callback: 设置保存后的回调函数
        """
        self.parent = parent
        self.callback = callback
        self.config = config_manager
        
        # 创建设置窗口
        self.window = tk.Toplevel(parent)
        self.window.title("高级设置")
        self.window.geometry("600x700")
        self.window.resizable(False, False)
        
        # 设置窗口居中
        self.window.transient(parent)
        self.window.grab_set()
        
        # 存储原始配置值
        self.original_config = {}
        self._backup_config()
        
        # 创建界面
        self.setup_ui()
        
        # 窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _backup_config(self):
        """备份当前配置"""
        sections = ['OSC', 'Voice', 'Recording', 'Modes', 'Interface', 'Advanced']
        for section in sections:
            self.original_config[section] = self.config.get_section(section)
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架和滚动条
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建Notebook（选项卡）
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建各个选项卡
        self.create_osc_tab()
        self.create_voice_tab()
        self.create_recording_tab()
        self.create_modes_tab()
        self.create_interface_tab()
        self.create_advanced_tab()
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 按钮
        ttk.Button(button_frame, text="恢复默认", command=self.restore_defaults).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="取消", command=self.on_closing).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="应用", command=self.apply_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="保存", command=self.save_settings).pack(side=tk.RIGHT, padx=(5, 0))
    
    def create_osc_tab(self):
        """创建OSC设置选项卡"""
        osc_frame = ttk.Frame(self.notebook)
        self.notebook.add(osc_frame, text="OSC连接")
        
        # 主机地址
        row = 0
        ttk.Label(osc_frame, text="主机地址:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.host_var = tk.StringVar(value=self.config.osc_host)
        ttk.Entry(osc_frame, textvariable=self.host_var, width=20).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 发送端口
        row += 1
        ttk.Label(osc_frame, text="发送端口:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.send_port_var = tk.StringVar(value=str(self.config.osc_send_port))
        ttk.Entry(osc_frame, textvariable=self.send_port_var, width=20).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 接收端口
        row += 1
        ttk.Label(osc_frame, text="接收端口:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.receive_port_var = tk.StringVar(value=str(self.config.osc_receive_port))
        ttk.Entry(osc_frame, textvariable=self.receive_port_var, width=20).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 调试模式
        row += 1
        self.debug_mode_var = tk.BooleanVar(value=self.config.osc_debug_mode)
        ttk.Checkbutton(osc_frame, text="启用OSC调试模式", variable=self.debug_mode_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
        
        osc_frame.columnconfigure(1, weight=1)
    
    def create_voice_tab(self):
        """创建语音设置选项卡"""
        voice_frame = ttk.Frame(self.notebook)
        self.notebook.add(voice_frame, text="语音识别")
        
        # 识别语言
        row = 0
        ttk.Label(voice_frame, text="识别语言:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.language_var = tk.StringVar(value=self.config.voice_language)
        language_combo = ttk.Combobox(voice_frame, textvariable=self.language_var, 
                                     values=["zh-CN", "ja-JP"], width=18, state="readonly")
        language_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 计算设备
        row += 1
        ttk.Label(voice_frame, text="计算设备:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.device_var = tk.StringVar(value=self.config.voice_device)
        device_combo = ttk.Combobox(voice_frame, textvariable=self.device_var,
                                   values=["auto", "cuda", "cpu"], width=18, state="readonly")
        device_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 语音阈值
        row += 1
        ttk.Label(voice_frame, text="语音阈值:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        threshold_frame = ttk.Frame(voice_frame)
        threshold_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.voice_threshold_var = tk.DoubleVar(value=self.config.voice_threshold)
        threshold_scale = ttk.Scale(threshold_frame, from_=0.005, to=0.05,
                                   variable=self.voice_threshold_var, orient='horizontal')
        threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.threshold_label = ttk.Label(threshold_frame, text=f"{self.config.voice_threshold:.3f}")
        self.threshold_label.pack(side=tk.RIGHT, padx=(10, 0))
        threshold_scale.config(command=lambda v: self.threshold_label.config(text=f"{float(v):.3f}"))
        
        # 能量阈值
        row += 1
        ttk.Label(voice_frame, text="能量阈值:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        energy_frame = ttk.Frame(voice_frame)
        energy_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.energy_threshold_var = tk.DoubleVar(value=self.config.energy_threshold)
        energy_scale = ttk.Scale(energy_frame, from_=0.001, to=0.05,
                                variable=self.energy_threshold_var, orient='horizontal')
        energy_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.energy_label = ttk.Label(energy_frame, text=f"{self.config.energy_threshold:.3f}")
        self.energy_label.pack(side=tk.RIGHT, padx=(10, 0))
        energy_scale.config(command=lambda v: self.energy_label.config(text=f"{float(v):.3f}"))
        
        voice_frame.columnconfigure(1, weight=1)
    
    def create_recording_tab(self):
        """创建录制设置选项卡"""
        recording_frame = ttk.Frame(self.notebook)
        self.notebook.add(recording_frame, text="录制参数")
        
        # 最大录制时长
        row = 0
        ttk.Label(recording_frame, text="最大录制时长 (秒):").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        max_duration_frame = ttk.Frame(recording_frame)
        max_duration_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.max_duration_var = tk.DoubleVar(value=self.config.max_speech_duration)
        max_duration_scale = ttk.Scale(max_duration_frame, from_=3.0, to=20.0,
                                      variable=self.max_duration_var, orient='horizontal')
        max_duration_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.max_duration_label = ttk.Label(max_duration_frame, text=f"{self.config.max_speech_duration:.1f}s")
        self.max_duration_label.pack(side=tk.RIGHT, padx=(10, 0))
        max_duration_scale.config(command=lambda v: self.max_duration_label.config(text=f"{float(v):.1f}s"))
        
        # 最小录制时长
        row += 1
        ttk.Label(recording_frame, text="最小录制时长 (秒):").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        min_duration_frame = ttk.Frame(recording_frame)
        min_duration_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.min_duration_var = tk.DoubleVar(value=self.config.min_speech_duration)
        min_duration_scale = ttk.Scale(min_duration_frame, from_=0.1, to=2.0,
                                      variable=self.min_duration_var, orient='horizontal')
        min_duration_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.min_duration_label = ttk.Label(min_duration_frame, text=f"{self.config.min_speech_duration:.1f}s")
        self.min_duration_label.pack(side=tk.RIGHT, padx=(10, 0))
        min_duration_scale.config(command=lambda v: self.min_duration_label.config(text=f"{float(v):.1f}s"))
        
        # 静音检测时长
        row += 1
        ttk.Label(recording_frame, text="静音检测时长 (秒):").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        silence_frame = ttk.Frame(recording_frame)
        silence_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.silence_duration_var = tk.DoubleVar(value=self.config.silence_duration)
        silence_scale = ttk.Scale(silence_frame, from_=0.3, to=3.0,
                                 variable=self.silence_duration_var, orient='horizontal')
        silence_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.silence_label = ttk.Label(silence_frame, text=f"{self.config.silence_duration:.1f}s")
        self.silence_label.pack(side=tk.RIGHT, padx=(10, 0))
        silence_scale.config(command=lambda v: self.silence_label.config(text=f"{float(v):.1f}s"))
        
        # 句子停顿阈值
        row += 1
        ttk.Label(recording_frame, text="断句间隔 (秒):").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        sentence_frame = ttk.Frame(recording_frame)
        sentence_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.sentence_pause_var = tk.DoubleVar(value=self.config.sentence_pause_threshold)
        sentence_scale = ttk.Scale(sentence_frame, from_=0.2, to=2.0,
                                  variable=self.sentence_pause_var, orient='horizontal')
        sentence_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.sentence_label = ttk.Label(sentence_frame, text=f"{self.config.sentence_pause_threshold:.1f}s")
        self.sentence_label.pack(side=tk.RIGHT, padx=(10, 0))
        sentence_scale.config(command=lambda v: self.sentence_label.config(text=f"{float(v):.1f}s"))
        
        recording_frame.columnconfigure(1, weight=1)
    
    def create_modes_tab(self):
        """创建模式设置选项卡"""
        modes_frame = ttk.Frame(self.notebook)
        self.notebook.add(modes_frame, text="录制模式")
        
        # 强制备用模式
        row = 0
        self.use_fallback_var = tk.BooleanVar(value=self.config.use_fallback_mode)
        ttk.Checkbutton(modes_frame, text="强制备用模式（使用纯音频检测）", 
                       variable=self.use_fallback_var).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        
        # 禁用备用模式
        row += 1
        self.disable_fallback_var = tk.BooleanVar(value=self.config.disable_fallback_mode)
        ttk.Checkbutton(modes_frame, text="禁用备用模式（只使用VRChat状态）", 
                       variable=self.disable_fallback_var).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        
        # VRChat检测超时
        row += 1
        ttk.Label(modes_frame, text="VRChat检测超时 (秒):").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        timeout_frame = ttk.Frame(modes_frame)
        timeout_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.timeout_var = tk.DoubleVar(value=self.config.vrc_detection_timeout)
        timeout_scale = ttk.Scale(timeout_frame, from_=10.0, to=120.0,
                                 variable=self.timeout_var, orient='horizontal')
        timeout_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.timeout_label = ttk.Label(timeout_frame, text=f"{self.config.vrc_detection_timeout:.0f}s")
        self.timeout_label.pack(side=tk.RIGHT, padx=(10, 0))
        timeout_scale.config(command=lambda v: self.timeout_label.config(text=f"{float(v):.0f}s"))
        
        modes_frame.columnconfigure(1, weight=1)
    
    def create_interface_tab(self):
        """创建界面设置选项卡"""
        interface_frame = ttk.Frame(self.notebook)
        self.notebook.add(interface_frame, text="界面设置")
        
        # 界面语言
        row = 0
        ttk.Label(interface_frame, text="界面语言:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.ui_language_var = tk.StringVar(value=self.config.ui_language)
        ui_lang_combo = ttk.Combobox(interface_frame, textvariable=self.ui_language_var,
                                    values=["zh", "ja"], width=18, state="readonly")
        ui_lang_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 窗口宽度
        row += 1
        ttk.Label(interface_frame, text="窗口宽度:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.window_width_var = tk.StringVar(value=str(self.config.window_width))
        ttk.Entry(interface_frame, textvariable=self.window_width_var, width=20).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 窗口高度
        row += 1
        ttk.Label(interface_frame, text="窗口高度:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.window_height_var = tk.StringVar(value=str(self.config.window_height))
        ttk.Entry(interface_frame, textvariable=self.window_height_var, width=20).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        interface_frame.columnconfigure(1, weight=1)
    
    def create_advanced_tab(self):
        """创建高级设置选项卡"""
        advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(advanced_frame, text="高级设置")
        
        # 能量下降比例
        row = 0
        ttk.Label(advanced_frame, text="能量下降比例:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        energy_drop_frame = ttk.Frame(advanced_frame)
        energy_drop_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.energy_drop_var = tk.DoubleVar(value=self.config.get('Advanced', 'energy_drop_ratio'))
        energy_drop_scale = ttk.Scale(energy_drop_frame, from_=0.1, to=1.0,
                                     variable=self.energy_drop_var, orient='horizontal')
        energy_drop_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        energy_drop_value = self.config.get('Advanced', 'energy_drop_ratio')
        self.energy_drop_label = ttk.Label(energy_drop_frame, text=f"{energy_drop_value:.2f}")
        self.energy_drop_label.pack(side=tk.RIGHT, padx=(10, 0))
        energy_drop_scale.config(command=lambda v: self.energy_drop_label.config(text=f"{float(v):.2f}"))
        
        # 识别间隔
        row += 1
        ttk.Label(advanced_frame, text="识别间隔 (秒):").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        interval_frame = ttk.Frame(advanced_frame)
        interval_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.recognition_interval_var = tk.DoubleVar(value=self.config.get('Advanced', 'recognition_interval'))
        interval_scale = ttk.Scale(interval_frame, from_=0.5, to=5.0,
                                  variable=self.recognition_interval_var, orient='horizontal')
        interval_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        interval_value = self.config.get('Advanced', 'recognition_interval')
        self.interval_label = ttk.Label(interval_frame, text=f"{interval_value:.1f}s")
        self.interval_label.pack(side=tk.RIGHT, padx=(10, 0))
        interval_scale.config(command=lambda v: self.interval_label.config(text=f"{float(v):.1f}s"))
        
        advanced_frame.columnconfigure(1, weight=1)
    
    def apply_settings(self):
        """应用设置（不保存到文件）"""
        try:
            self._update_config()
            if self.callback:
                self.callback(apply_only=True)
            messagebox.showinfo("成功", "设置已应用到当前会话")
        except Exception as e:
            messagebox.showerror("错误", f"应用设置失败: {e}")
    
    def save_settings(self):
        """保存设置"""
        try:
            self._update_config()
            self.config.save_config()
            if self.callback:
                self.callback(apply_only=False)
            messagebox.showinfo("成功", "设置已保存")
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败: {e}")
    
    def _update_config(self):
        """更新配置"""
        # OSC设置
        self.config.set('OSC', 'host', self.host_var.get())
        self.config.set('OSC', 'send_port', int(self.send_port_var.get()))
        self.config.set('OSC', 'receive_port', int(self.receive_port_var.get()))
        self.config.set('OSC', 'debug_mode', self.debug_mode_var.get())
        
        # 语音设置
        self.config.set('Voice', 'language', self.language_var.get())
        self.config.set('Voice', 'device', self.device_var.get())
        self.config.set('Voice', 'voice_threshold', self.voice_threshold_var.get())
        self.config.set('Voice', 'energy_threshold', self.energy_threshold_var.get())
        
        # 录制设置
        self.config.set('Recording', 'max_speech_duration', self.max_duration_var.get())
        self.config.set('Recording', 'min_speech_duration', self.min_duration_var.get())
        self.config.set('Recording', 'silence_duration', self.silence_duration_var.get())
        self.config.set('Recording', 'sentence_pause_threshold', self.sentence_pause_var.get())
        
        # 模式设置
        self.config.set('Modes', 'use_fallback_mode', self.use_fallback_var.get())
        self.config.set('Modes', 'disable_fallback_mode', self.disable_fallback_var.get())
        self.config.set('Modes', 'vrc_detection_timeout', self.timeout_var.get())
        
        # 界面设置
        self.config.set('Interface', 'ui_language', self.ui_language_var.get())
        self.config.set('Interface', 'window_width', int(self.window_width_var.get()))
        self.config.set('Interface', 'window_height', int(self.window_height_var.get()))
        
        # 高级设置
        self.config.set('Advanced', 'energy_drop_ratio', self.energy_drop_var.get())
        self.config.set('Advanced', 'recognition_interval', self.recognition_interval_var.get())
    
    def restore_defaults(self):
        """恢复默认设置"""
        if messagebox.askyesno("确认", "确定要恢复所有设置为默认值吗？"):
            # 重新创建默认配置
            self.config._create_default_config()
            messagebox.showinfo("成功", "已恢复默认设置，请重新打开设置窗口查看")
            self.window.destroy()
    
    def on_closing(self):
        """窗口关闭事件"""
        self.window.destroy()