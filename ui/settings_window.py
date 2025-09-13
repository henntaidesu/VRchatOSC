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
    
    def __init__(self, parent, callback=None, main_app=None):
        """
        初始化设置窗口
        
        Args:
            parent: 父窗口
            callback: 设置保存后的回调函数
            main_app: 主应用程序引用，用于获取多语言文本
        """
        self.parent = parent
        self.callback = callback
        self.main_app = main_app
        self.config = config_manager
        
        # 创建设置窗口
        self.window = tk.Toplevel(parent)
        self.window.title(self._get_text("advanced_settings_title"))
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
    
    def _get_text(self, key, default=None):
        """获取多语言文本"""
        if self.main_app and hasattr(self.main_app, 'get_text'):
            return self.main_app.get_text(key)
        return default or key
    
    def _backup_config(self):
        """备份当前配置"""
        sections = ['OSC', 'Voice', 'Recording', 'Modes', 'Interface', 'Advanced', 'LLM']
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
        self.create_llm_tab()
        
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
        self.notebook.add(osc_frame, text=self.main_app.get_text("osc_connection"))
        
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
        ttk.Checkbutton(osc_frame, text=self.main_app.get_text("enable_osc_debug_mode"), variable=self.debug_mode_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
        
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
                                     values=["zh", "ja", "en"], width=18, state="readonly")
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
        ttk.Checkbutton(modes_frame, text=self.main_app.get_text("disable_backup_mode"), 
                       variable=self.disable_fallback_var).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        
        # VRChat检测超时
        row += 1
        ttk.Label(modes_frame, text=self.main_app.get_text("vrchat_detection_timeout")).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
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
        
        # 使用语言显示名称
        from ui.languages.language_dict import get_language_display_names, DISPLAY_TO_LANGUAGE_MAP, LANGUAGE_DISPLAY_MAP
        language_display_names = get_language_display_names()
        current_display_name = LANGUAGE_DISPLAY_MAP.get(self.config.ui_language, "中文")
        self.ui_language_display_var = tk.StringVar(value=current_display_name)
        
        ui_lang_combo = ttk.Combobox(interface_frame, textvariable=self.ui_language_display_var,
                                    values=language_display_names, width=18, state="readonly")
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
        """创建OSC参数过滤设置选项卡"""
        advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(advanced_frame, text=self._get_text("osc_parameter_filtering", "OSC参数过滤"))
        
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
        
        # OSC参数过滤设置
        row += 1
        ttk.Label(advanced_frame, text=self._get_text("filter_osc_parameters", "过滤OSC参数:")).grid(row=row, column=0, sticky=tk.NW, padx=10, pady=5)
        
        # 参数过滤总开关
        row += 1
        self.enable_filtering_var = tk.BooleanVar(value=self.config.enable_parameter_filtering)
        ttk.Checkbutton(advanced_frame, text=self._get_text("enable_parameter_filtering", "启用参数过滤"), 
                       variable=self.enable_filtering_var,
                       command=self._on_filtering_toggle).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        
        # 创建可滚动的参数勾选框列表
        row += 1
        filter_frame = ttk.LabelFrame(advanced_frame, text=self._get_text("parameter_filter_list", "参数过滤列表"), padding="5")
        filter_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
        
        # 创建Canvas和Scrollbar用于滚动 - 减小高度以节省空间
        canvas = tk.Canvas(filter_frame, height=150)
        scrollbar_params = ttk.Scrollbar(filter_frame, orient="vertical", command=canvas.yview)
        scrollable_params_frame = ttk.Frame(canvas)
        
        scrollable_params_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_params_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_params.set)
        
        # 添加滚轮支持
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind('<Enter>', _bind_to_mousewheel)
        canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_params.pack(side="right", fill="y")
        
        # 定义OSC参数分类和列表
        self.osc_parameter_categories = {
            "基本状态参数": [
                ("AvatarVersion", "Avatar版本信息"),
                ("Grounded", "是否接地状态"),
                ("InStation", "是否在Station中"),
                ("Seated", "是否坐着"),
                ("AFK", "是否挂机"),
                ("MuteSelf", "是否静音"),
                ("Earmuffs", "是否戴耳机"),
                ("AFKTimer", "挂机计时器"),
            ],
            "手势控制参数": [
                ("GestureLeft", "左手手势"),
                ("GestureRight", "右手手势"),
                ("GestureLeftWeight", "左手手势权重"),
                ("GestureRightWeight", "右手手势权重"),
            ],
            "身体部位参数": [
                ("Hips_SwimsuitGrab_Angle", "臀部泳装抓取角度"),
                ("Chest_SwimsuitGrab_Angle", "胸部泳装抓取角度"),
                ("Thigh_L_SwimsuitGrab_Angle", "左大腿泳装抓取角度"),
                ("Thigh_R_SwimsuitGrab_Angle", "右大腿泳装抓取角度"),
            ],
            "表情控制参数": [
                ("FaceEmoHappy", "开心表情"),
                ("FaceEmoSad", "悲伤表情"),
                ("FaceEmoAngry", "愤怒表情"),
                ("FaceEmoSurprised", "惊讶表情"),
            ],
            "跟踪系统参数": [
                ("TrackingType", "跟踪类型"),
                ("UpRight", "直立状态"),
                ("VRMode", "VR模式"),
            ],
            # 保留扩展空间 - 可以在这里添加更多分类
            "自定义参数": [
                # 未来可以添加更多参数
            ]
        }
        
        # 创建参数勾选框
        self.param_checkboxes = {}
        current_params_config = self.config.get_osc_parameter_config()
        
        # 使用循环创建分类和参数
        for category_name, params in self.osc_parameter_categories.items():
            if not params:  # 跳过空分类
                continue
                
            # 创建分类标题
            category_label = ttk.Label(scrollable_params_frame, 
                                     text=f"▼ {category_name}", 
                                     font=("", 9, "bold"),
                                     foreground="#0066CC")
            category_label.pack(anchor=tk.W, padx=5, pady=(10, 2))
            
            # 创建该分类下的参数勾选框
            for param_name, description in params:
                # 从JSON配置中获取当前状态
                is_enabled = current_params_config.get(param_name, {}).get('enabled', False)
                self._create_parameter_checkbox(scrollable_params_frame, 
                                              param_name, description, 
                                              is_enabled)
        
        # 添加全选/全不选按钮
        row += 1
        button_frame = ttk.Frame(advanced_frame)
        button_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
        
        ttk.Button(button_frame, text=self._get_text("select_all", "全选"), 
                  command=self._select_all_params).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=self._get_text("select_none", "全不选"), 
                  command=self._select_no_params).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=self._get_text("select_recommended", "推荐设置"), 
                  command=self._select_recommended_params).pack(side=tk.LEFT, padx=(0, 10))
        
        # 添加自定义参数按钮
        ttk.Button(button_frame, text=self._get_text("add_custom_param", "添加自定义"), 
                  command=self._add_custom_parameter).pack(side=tk.LEFT)
        
        advanced_frame.columnconfigure(1, weight=1)
        advanced_frame.rowconfigure(row-2, weight=2)  # 给参数过滤框更多扩展权重
    
    def _create_parameter_checkbox(self, parent, param_name, description, is_checked=False):
        """创建单个参数的勾选框
        
        Args:
            parent: 父组件
            param_name: 参数名
            description: 参数描述
            is_checked: 是否默认选中
        """
        checkbox_frame = ttk.Frame(parent)
        checkbox_frame.pack(fill=tk.X, padx=15, pady=1)  # 缩进显示分类下的参数
        
        # 创建勾选框变量
        var = tk.BooleanVar(value=is_checked)
        self.param_checkboxes[param_name] = var
        
        # 创建勾选框
        checkbox = ttk.Checkbutton(checkbox_frame, variable=var)
        checkbox.pack(side=tk.LEFT)
        
        # 参数名标签 - 使用等宽字体便于对齐
        param_label = ttk.Label(checkbox_frame, text=param_name, 
                               font=("Consolas", 9), width=25)
        param_label.pack(side=tk.LEFT, padx=(5, 5))
        
        # 描述标签
        desc_label = ttk.Label(checkbox_frame, text=f"- {description}", 
                             foreground="gray", font=("", 8))
        desc_label.pack(side=tk.LEFT)
    
    def _on_filtering_toggle(self):
        """参数过滤总开关切换回调"""
        enabled = self.enable_filtering_var.get()
        # 可以在这里添加额外的UI更新逻辑
        print(f"参数过滤已{'启用' if enabled else '禁用'}")
    
    def _select_all_params(self):
        """全选所有参数进行过滤"""
        for var in self.param_checkboxes.values():
            var.set(True)
    
    def _select_no_params(self):
        """全不选，不过滤任何参数"""
        for var in self.param_checkboxes.values():
            var.set(False)
    
    def _select_recommended_params(self):
        """选择推荐的过滤参数"""
        # 推荐过滤的参数（通常是不重要的参数）
        recommended_params = {
            "Hips_SwimsuitGrab_Angle", "Chest_SwimsuitGrab_Angle",
            "Thigh_L_SwimsuitGrab_Angle", "Thigh_R_SwimsuitGrab_Angle",
            "AvatarVersion", "MuteSelf", "Grounded", "InStation", 
            "Seated", "AFK", "Earmuffs", "AFKTimer"
        }
        
        for param_name, var in self.param_checkboxes.items():
            var.set(param_name in recommended_params)
    
    def _add_custom_parameter(self):
        """添加自定义参数"""
        from tkinter import simpledialog
        
        # 弹出对话框让用户输入参数名
        param_name = simpledialog.askstring(
            self._get_text("add_custom_param", "添加自定义参数"), 
            self._get_text("enter_param_name", "请输入参数名称:")
        )
        
        if param_name and param_name.strip():
            param_name = param_name.strip()
            
            # 检查是否已存在
            if param_name in self.param_checkboxes:
                messagebox.showwarning(
                    self._get_text("warning", "警告"), 
                    self._get_text("param_already_exists", "参数已存在!")
                )
                return
            
            # 使用新配置管理器添加自定义参数
            success = self.config.add_custom_osc_parameter(param_name, "用户自定义参数")
            if success:
                # 添加到自定义分类中用于UI显示
                if "自定义参数" not in self.osc_parameter_categories:
                    self.osc_parameter_categories["自定义参数"] = []
                self.osc_parameter_categories["自定义参数"].append((param_name, "用户自定义参数"))
                
                # 添加到勾选框
                var = tk.BooleanVar(value=True)  # 新添加的参数默认启用过滤
                self.param_checkboxes[param_name] = var
                
                messagebox.showinfo(
                    self._get_text("success", "成功"), 
                    self._get_text("param_added_success", f"参数 '{param_name}' 已添加，保存设置后生效")
                )
            else:
                messagebox.showwarning(
                    self._get_text("warning", "警告"),
                    self._get_text("param_already_exists", "参数已存在!")
                )
    
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
        self.config.set('user_osc', 'host', self.host_var.get())
        self.config.set('user_osc', 'send_port', int(self.send_port_var.get()))
        self.config.set('user_osc', 'receive_port', int(self.receive_port_var.get()))
        self.config.set('user_osc', 'debug_mode', self.debug_mode_var.get())
        
        # 语音设置
        self.config.set('voice', 'language', self.language_var.get())
        self.config.set('voice', 'device', self.device_var.get())
        self.config.set('voice', 'voice_threshold', self.voice_threshold_var.get())
        self.config.set('voice', 'energy_threshold', self.energy_threshold_var.get())
        
        # 录制设置
        self.config.set('recording', 'max_speech_duration', self.max_duration_var.get())
        self.config.set('recording', 'min_speech_duration', self.min_duration_var.get())
        self.config.set('recording', 'silence_duration', self.silence_duration_var.get())
        self.config.set('recording', 'sentence_pause_threshold', self.sentence_pause_var.get())
        
        # 模式设置
        self.config.set('modes', 'use_fallback_mode', self.use_fallback_var.get())
        self.config.set('modes', 'disable_fallback_mode', self.disable_fallback_var.get())
        self.config.set('modes', 'vrc_detection_timeout', self.timeout_var.get())
        
        # 界面设置
        # 将显示名称转换为语言代码
        from ui.languages.language_dict import DISPLAY_TO_LANGUAGE_MAP
        display_name = self.ui_language_display_var.get()
        language_code = DISPLAY_TO_LANGUAGE_MAP.get(display_name, "zh")
        self.config.set('interface', 'ui_language', language_code)
        self.config.set('interface', 'window_width', int(self.window_width_var.get()))
        self.config.set('interface', 'window_height', int(self.window_height_var.get()))
        
        # 高级设置
        self.config.set('advanced', 'energy_drop_ratio', self.energy_drop_var.get())
        self.config.set('advanced', 'recognition_interval', self.recognition_interval_var.get())
        
        # OSC参数过滤设置
        if hasattr(self, 'enable_filtering_var'):
            self.config.enable_parameter_filtering = self.enable_filtering_var.get()
        
        if hasattr(self, 'param_checkboxes'):
            # 更新每个参数的启用状态
            for param_name, var in self.param_checkboxes.items():
                self.config.set_osc_parameter_enabled(param_name, var.get())
        
        # LLM设置
        self.config.set('LLM', 'gemini_api_key', self.gemini_api_key_var.get())
        self.config.set('LLM', 'gemini_model', self.gemini_model_var.get())
        self.config.set('LLM', 'enable_llm', self.enable_llm_var.get())
        self.config.set('LLM', 'temperature', self.temperature_var.get())
        self.config.set('LLM', 'max_output_tokens', int(self.max_tokens_var.get()))
        self.config.set('LLM', 'conversation_history_length', int(self.history_length_var.get()))
        self.config.set('LLM', 'system_prompt', self.system_prompt_var.get())
    
    def restore_defaults(self):
        """恢复默认设置"""
        if messagebox.askyesno("确认", "确定要恢复所有设置为默认值吗？"):
            # 重新创建默认配置
            self.config._create_default_config()
            messagebox.showinfo("成功", "已恢复默认设置，请重新打开设置窗口查看")
            self.window.destroy()
    
    def create_llm_tab(self):
        """创建LLM设置选项卡"""
        llm_frame = ttk.Frame(self.notebook)
        self.notebook.add(llm_frame, text=self.main_app.get_text("llm_settings"))
        
        # 创建滚动框架
        canvas = tk.Canvas(llm_frame)
        scrollbar = ttk.Scrollbar(llm_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 启用LLM功能
        row = 0
        ttk.Label(scrollable_frame, text=self.main_app.get_text("enable_llm")).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.enable_llm_var = tk.BooleanVar(value=self.config.enable_llm)
        ttk.Checkbutton(scrollable_frame, variable=self.enable_llm_var).grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
        
        # API Key设置
        row += 1
        ttk.Label(scrollable_frame, text=self.main_app.get_text("gemini_api_key")).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.gemini_api_key_var = tk.StringVar(value=self.config.gemini_api_key)
        api_key_entry = ttk.Entry(scrollable_frame, textvariable=self.gemini_api_key_var, width=40, show="*")
        api_key_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5, columnspan=2)
        
        # 显示/隐藏API Key按钮
        row += 1
        def toggle_api_key_visibility():
            if api_key_entry.cget('show') == '*':
                api_key_entry.config(show='')
                show_hide_btn.config(text=self._get_text("hide"))
            else:
                api_key_entry.config(show='*')
                show_hide_btn.config(text=self._get_text("show"))
        
        show_hide_btn = ttk.Button(scrollable_frame, text=self._get_text("show"), command=toggle_api_key_visibility)
        show_hide_btn.grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)
        
        # 模型选择
        row += 1
        ttk.Label(scrollable_frame, text=self.main_app.get_text("gemini_model")).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.gemini_model_var = tk.StringVar(value=self.config.gemini_model)
        model_combo = ttk.Combobox(scrollable_frame, textvariable=self.gemini_model_var, width=25, state="readonly")
        model_combo['values'] = [
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-1.0-pro',
            'gemini-2.5-flash',
            'gemini-2.5-pro',
            'gemini-2.0-pro',
        ]
        model_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 温度参数
        row += 1
        ttk.Label(scrollable_frame, text=self.main_app.get_text("temperature")).grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.temperature_var = tk.DoubleVar(value=self.config.llm_temperature)
        temp_scale = tk.Scale(scrollable_frame, from_=0.0, to=1.0, resolution=0.1, orient=tk.HORIZONTAL, 
                             variable=self.temperature_var, length=200)
        temp_scale.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 最大输出长度
        row += 1
        ttk.Label(scrollable_frame, text="最大输出长度:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.max_tokens_var = tk.StringVar(value=str(self.config.llm_max_output_tokens))
        ttk.Entry(scrollable_frame, textvariable=self.max_tokens_var, width=20).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 对话历史长度
        row += 1
        ttk.Label(scrollable_frame, text="对话历史长度:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        self.history_length_var = tk.StringVar(value=str(self.config.llm_conversation_history_length))
        ttk.Entry(scrollable_frame, textvariable=self.history_length_var, width=20).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 系统提示词
        row += 1
        ttk.Label(scrollable_frame, text="系统提示词:").grid(row=row, column=0, sticky=(tk.W, tk.N), padx=10, pady=5)
        self.system_prompt_var = tk.StringVar(value=self.config.llm_system_prompt)
        
        # 创建文本框用于多行输入
        text_frame = ttk.Frame(scrollable_frame)
        text_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=10, pady=5, columnspan=2)
        
        system_prompt_text = tk.Text(text_frame, height=4, width=50, wrap=tk.WORD)
        system_prompt_text.insert('1.0', self.config.llm_system_prompt)
        system_prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        text_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=system_prompt_text.yview)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        system_prompt_text.config(yscrollcommand=text_scrollbar.set)
        
        # 绑定文本框内容到变量
        def update_system_prompt(*args):
            self.system_prompt_var.set(system_prompt_text.get('1.0', tk.END).strip())
        
        system_prompt_text.bind('<KeyRelease>', update_system_prompt)
        
        # 测试连接按钮
        row += 1
        def test_gemini_connection():
            """测试Gemini连接"""
            api_key = self.gemini_api_key_var.get().strip()
            if not api_key:
                messagebox.showwarning("警告", "请先输入API Key")
                return
            
            try:
                # 临时创建客户端测试连接
                from src.llm.GeminiLLM import GeminiClient
                temp_client = GeminiClient(api_key, self.gemini_model_var.get())
                
                if temp_client.test_connection():
                    messagebox.showinfo("成功", "[成功] Gemini API连接测试成功！")
                else:
                    messagebox.showerror("失败", "[错误] Gemini API连接测试失败，请检查API Key和网络连接")
            except ImportError:
                messagebox.showerror("错误", "[错误] 无法导入Gemini客户端，请检查代码")
            except Exception as e:
                messagebox.showerror("错误", f"[错误] 连接测试异常: {e}")
        
        test_btn = ttk.Button(scrollable_frame, text="测试连接", command=test_gemini_connection)
        test_btn.grid(row=row, column=1, sticky=tk.W, padx=10, pady=10)
        
        # 添加说明文本
        row += 1
        info_text = """
        [日志] LLM功能说明:
        • 启用后可将语音识别结果发送到Gemini进行智能回复
        • 需要有效的Google Gemini API Key
        • Temperature控制回复的创造性 (0.0=保守, 1.0=创新)
        • 可自定义系统提示词来调整AI的回复风格
        • 建议使用gemini-1.5-flash模型获得更快响应速度
        """
        
        info_label = ttk.Label(scrollable_frame, text=info_text, justify=tk.LEFT, 
                              font=("", 9), foreground="gray")
        info_label.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # 配置列权重
        scrollable_frame.columnconfigure(1, weight=1)
    
    def on_closing(self):
        """窗口关闭事件"""
        self.window.destroy()