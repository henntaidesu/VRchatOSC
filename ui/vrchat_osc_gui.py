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
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vrchat_controller import VRChatController


class VRChatOSCGUI:
    """VRChat OSC GUI界面类"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VRChat OSC 通信工具")
        self.root.geometry("800x900")  # 增大窗口以适应新的语音输出框
        self.root.resizable(True, True)
        
        # OSC客户端
        self.client = None
        self.is_connected = False
        self.is_listening = False
        
        # 设置变量
        self.host_var = tk.StringVar(value="127.0.0.1")
        self.send_port_var = tk.StringVar(value="9000")
        self.receive_port_var = tk.StringVar(value="9001")
        self.language_var = tk.StringVar(value="ja-JP")
        self.device_var = tk.StringVar(value="auto")
        self.ui_language = tk.StringVar(value="zh")  # 界面语言：zh=中文, ja=日语
        
        # 语音文件相关变量
        self.uploaded_audio_data = None
        self.uploaded_audio_sample_rate = None
        self.uploaded_filename = None
        
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
        main_frame.columnconfigure(1, weight=1)
        
        # 连接设置框架
        self.connection_frame = ttk.LabelFrame(main_frame, text=self.get_text("connection_settings"), padding="5")
        self.connection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 主机地址
        ttk.Label(connection_frame, text="主机地址:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(connection_frame, textvariable=self.host_var, width=15).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 发送端口
        ttk.Label(connection_frame, text="发送端口:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        ttk.Entry(connection_frame, textvariable=self.send_port_var, width=8).grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 接收端口
        ttk.Label(connection_frame, text="接收端口:").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        ttk.Entry(connection_frame, textvariable=self.receive_port_var, width=8).grid(row=0, column=5, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 连接按钮
        self.connect_btn = ttk.Button(self.connection_frame, text=self.get_text("connect"), command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=6, padx=(10, 0))
        
        # 语言切换按钮
        self.lang_btn = ttk.Button(self.connection_frame, text="中/日", command=self.change_ui_language)
        self.lang_btn.grid(row=0, column=7, padx=(5, 0))
        
        # 配置连接框架的列权重
        connection_frame.columnconfigure(1, weight=1)
        connection_frame.columnconfigure(3, weight=1)
        connection_frame.columnconfigure(5, weight=1)
        
        # 消息发送框架
        message_frame = ttk.LabelFrame(main_frame, text="消息发送", padding="5")
        message_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
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
        
        # 语言和设备选择在同一行
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
        
        # 语音按钮（第二行）
        self.record_btn = ttk.Button(voice_frame, text="录制语音", command=self.record_voice)
        self.record_btn.grid(row=1, column=0, padx=(0, 5))
        
        self.listen_btn = ttk.Button(voice_frame, text="开始监听", command=self.toggle_voice_listening)
        self.listen_btn.grid(row=1, column=1, padx=(0, 5))
        
        # 语音文件上传按钮
        self.upload_voice_btn = ttk.Button(voice_frame, text="上传语音", command=self.upload_voice_file)
        self.upload_voice_btn.grid(row=1, column=2, padx=(0, 5))
        
        # 发送语音按钮
        self.send_voice_btn = ttk.Button(voice_frame, text="发送语音", command=self.send_voice)
        self.send_voice_btn.grid(row=1, column=3, padx=(0, 5))
        
        # 停止录制按钮（第三行）
        self.stop_record_btn = ttk.Button(voice_frame, text="停止录制", command=self.stop_recording)
        self.stop_record_btn.grid(row=2, column=0, pady=(5, 0), padx=(0, 5))
        
        # 语音阈值设置
        threshold_frame = ttk.Frame(message_frame)
        threshold_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(threshold_frame, text="语音阈值:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.threshold_var = tk.DoubleVar(value=0.02)
        threshold_scale = ttk.Scale(threshold_frame, from_=0.005, to=0.1, 
                                   variable=self.threshold_var, orient='horizontal',
                                   command=self.update_voice_threshold)
        threshold_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.threshold_label = ttk.Label(threshold_frame, text="0.020")
        self.threshold_label.grid(row=0, column=2)
        
        threshold_frame.columnconfigure(1, weight=1)
        
        
        # 参数设置框架
        param_frame = ttk.LabelFrame(main_frame, text="Avatar参数", padding="5")
        param_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
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
        
        # 日志显示框架
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 配置主框架行权重
        main_frame.rowconfigure(3, weight=1)
        
        # 日志文本框 - 减小高度为语音识别框让出空间
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清空日志按钮
        ttk.Button(log_frame, text="清空日志", command=self.clear_log).grid(row=1, column=0, pady=(5, 0))
        
        # 语音识别输出框架
        speech_frame = ttk.LabelFrame(main_frame, text="语音识别输出 (基于VRChat语音状态)", padding="5")
        speech_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        speech_frame.columnconfigure(0, weight=1)
        speech_frame.rowconfigure(0, weight=1)
        
        # 配置主框架行权重 - 为语音识别框分配空间
        main_frame.rowconfigure(4, weight=1)
        
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
        
        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="未连接", foreground="red")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 进度条（默认隐藏）
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        self.progress_bar.grid_remove()  # 初始隐藏
        
        # 初始状态设置
        self.update_ui_state(False)
    
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
            self.connect_btn.config(text="断开")
            self.status_label.config(text="已连接", foreground="green")
            # 启用功能按钮
            self.record_btn.config(state="normal")
            self.listen_btn.config(state="normal")
            self.send_voice_btn.config(state="normal")
            self.stop_record_btn.config(state="normal")
        else:
            self.connect_btn.config(text="连接")
            self.status_label.config(text="未连接", foreground="red")
            # 禁用功能按钮
            self.record_btn.config(state="disabled")
            self.listen_btn.config(state="disabled")
            self.send_voice_btn.config(state="disabled")
            self.stop_record_btn.config(state="disabled")
            
            # 停止语音监听
            if self.is_listening:
                self.is_listening = False
                self.listen_btn.config(text="开始监听")
    
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
                    # 创建OSC客户端，传递设备选择
                    self.client = VRChatController(host, send_port, receive_port, speech_device=device)
                    
                    # 设置回调函数
                    self.client.set_status_change_callback(self.on_status_change)
                    self.client.set_voice_result_callback(self.on_voice_result)
                    
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
            self.log("✅ 已断开VRChat连接")
            
        except Exception as e:
            self.log(f"❌ 断开连接时出错: {e}")
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
    
    def record_voice(self):
        """录制语音"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接到VRChat")
            return
        
        def record_thread():
            try:
                self.root.after(0, lambda: self.record_btn.config(text="录制中...", state="disabled"))
                self.log("开始录制语音...")
                
                text = self.client.record_and_recognize(5, self.language_var.get())
                
                if text:
                    # 显示在语音识别输出框
                    self.add_speech_output(text, "录制语音")
                    # 发送到VRChat
                    self.client.send_text_message(f"[语音] {text}")
                    # 记录到日志
                    self.log(f"[语音识别] {text}")
                else:
                    self.log("语音识别失败")
                
            except Exception as e:
                self.log(f"录制语音失败: {e}")
            finally:
                self.root.after(0, lambda: self.record_btn.config(text="录制语音", state="normal"))
        
        threading.Thread(target=record_thread, daemon=True).start()
    
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
    
    def send_voice(self):
        """发送语音到VRChat"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接到VRChat")
            return
        
        def send_voice_thread():
            try:
                # 优先使用上传的音频文件
                if self.uploaded_audio_data is not None:
                    self.root.after(0, lambda: self.send_voice_btn.config(text="识别中...", state="disabled"))
                    self.log(f"开始识别上传的音频文件: {self.uploaded_filename}")
                    
                    # 识别上传的音频文件
                    text = self.client.speech_engine.recognize_audio(
                        self.uploaded_audio_data, self.uploaded_audio_sample_rate, self.language_var.get()
                    )
                    
                    if text:
                        # 显示在语音识别输出框
                        self.add_speech_output(text, f"文件: {self.uploaded_filename}")
                        # 发送到VRChat
                        self.client.send_text_message(f"[语音文件] {text}")
                        # 记录到日志
                        self.log(f"语音文件识别并发送: {text}")
                        
                        # 清除已发送的上传文件
                        self.uploaded_audio_data = None
                        self.uploaded_audio_sample_rate = None
                        self.uploaded_filename = None
                    else:
                        self.log("语音文件识别失败")
                else:
                    # 使用录制功能
                    self.root.after(0, lambda: self.send_voice_btn.config(text="录制中...", state="disabled"))
                    self.log("开始录制并发送语音到VRChat...")
                    
                    text = self.client.record_and_recognize(5, self.language_var.get())
                    if text:
                        # 显示在语音识别输出框
                        self.add_speech_output(text, "发送语音")
                        # 发送到VRChat
                        self.client.send_text_message(f"[语音] {text}")
                        # 记录到日志
                        self.log(f"语音识别并发送: {text}")
                    else:
                        self.log("语音识别失败")
                
            except Exception as e:
                self.log(f"发送语音失败: {e}")
                messagebox.showerror("语音错误", f"发送语音失败: {e}")
            finally:
                self.root.after(0, lambda: self.send_voice_btn.config(text="发送语音", state="normal"))
        
        threading.Thread(target=send_voice_thread, daemon=True).start()
    
    
    def update_voice_threshold(self, value):
        """更新语音阈值"""
        threshold = float(value)
        if self.client:
            self.client.set_voice_threshold(threshold)
        self.threshold_label.config(text=f"{threshold:.3f}")
        self.log(f"语音阈值已设置为: {threshold:.3f}")
    
    def stop_recording(self):
        """停止当前录制"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接到VRChat")
            return
        
        try:
            self.client.stop_current_recording()
            self.log("已发送停止录制信号")
        except Exception as e:
            self.log(f"停止录制失败: {e}")
            messagebox.showerror("错误", f"停止录制失败: {e}")
    
    def on_closing(self):
        """窗口关闭事件处理"""
        try:
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
            self.log(f"✅ 音频文件加载成功: {self.uploaded_filename}")
            self.log(f"   时长: {duration:.2f}秒, 采样率: {sample_rate}Hz")
            
            # 更新发送语音按钮文本
            self.send_voice_btn.config(text=f"发送 {self.uploaded_filename[:10]}...")
            
        except Exception as e:
            self.log(f"❌ 音频文件加载失败: {e}")
            messagebox.showerror("文件错误", f"无法加载音频文件: {e}")
    
    def change_ui_language(self):
        """切换界面语言"""
        # 切换语言
        current = self.ui_language.get()
        new_lang = "ja" if current == "zh" else "zh"
        self.ui_language.set(new_lang)
        
        # 更新窗口标题
        self.root.title(self.get_text("title"))
        
        # 重新设置UI文本（这里只更新主要标签）
        self.connection_frame.config(text=self.get_text("connection_settings"))
        # 可以添加更多UI元素的更新...
        
        self.log(f"界面语言已切换为: {'中文' if new_lang == 'zh' else '日本語'}")
    
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