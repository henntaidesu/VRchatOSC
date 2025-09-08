# -*- coding: utf-8 -*-
"""
VRChat连接管理模块
负责处理VRChat OSC连接、断开、消息发送、语音监听等功能
"""

import threading
import tkinter as tk
from tkinter import messagebox
from src.vrchat_controller import VRChatController


class VRChatConnection:
    def __init__(self, main_app):
        """初始化VRChat连接管理器
        
        Args:
            main_app: 主应用程序实例
        """
        self.main_app = main_app
        
    def connect_to_vrchat(self):
        """连接到VRChat"""
        try:
            host = self.main_app.host_var.get().strip()
            send_port = int(self.main_app.send_port_var.get())
            receive_port = int(self.main_app.receive_port_var.get())
            device = self.main_app.device_var.get()
            
            # 禁用连接按钮并显示加载状态
            self.main_app.connect_btn.config(text="连接中...", state="disabled")
            self.main_app.progress_bar.grid()  # 显示进度条
            self.main_app.progress_bar.start()  # 开始进度条动画
            self.main_app.log("开始连接VRChat...")
            self.main_app.log(f"正在加载语音识别模型 ({device})...")
            self.main_app.log("提示：首次加载可能需要较长时间，请耐心等待...")
            
            # 在后台线程中连接，避免界面卡顿
            def connect_thread():
                try:
                    # 创建OSC客户端，传递参数（如果与配置不同）
                    use_config_host = host == self.main_app.config.osc_host
                    use_config_ports = (send_port == self.main_app.config.osc_send_port and 
                                       receive_port == self.main_app.config.osc_receive_port)
                    use_config_device = device == self.main_app.config.voice_device
                    
                    # 只传递与配置不同的参数
                    self.main_app.client = VRChatController(
                        host=None if use_config_host else host,
                        send_port=None if use_config_ports else send_port,
                        receive_port=None if use_config_ports else receive_port,
                        speech_device=None if use_config_device else device
                    )
                    
                    # 设置回调函数
                    self.main_app.client.set_status_change_callback(self.on_status_change)
                    self.main_app.client.set_voice_result_callback(self.on_voice_result)
                    
                    # 应用默认设置
                    if hasattr(self.main_app.client, 'set_disable_fallback_mode'):
                        self.main_app.client.set_disable_fallback_mode(self.main_app.disable_fallback_var.get())
                    
                    # 启动服务器
                    success = self.main_app.client.start_osc_server()
                    
                    if success:
                        # 在主线程中更新UI
                        self.main_app.root.after(0, lambda: self._connection_success(host, send_port))
                    else:
                        self.main_app.root.after(0, lambda: self._connection_failed("OSC服务器启动失败"))
                        
                except Exception as e:
                    error_msg = str(e)
                    self.main_app.root.after(0, lambda: self._connection_failed(error_msg))
            
            # 启动连接线程
            threading.Thread(target=connect_thread, daemon=True).start()
            
        except ValueError:
            self.main_app.connect_btn.config(text="连接", state="normal")
            self.main_app.progress_bar.stop()
            self.main_app.progress_bar.grid_remove()
            messagebox.showerror(self.main_app.get_text("error"), self.main_app.get_text("port_must_be_number"))
        except Exception as e:
            self.main_app.connect_btn.config(text="连接", state="normal")
            self.main_app.progress_bar.stop()
            self.main_app.progress_bar.grid_remove()
            messagebox.showerror(self.main_app.get_text("connection_error"), f"{self.main_app.get_text('cannot_connect_vrchat')}: {e}")
            self.main_app.log(f"连接失败: {e}")
    
    def _connection_success(self, host: str, send_port: int):
        """连接成功的UI更新"""
        # 隐藏进度条
        self.main_app.progress_bar.stop()
        self.main_app.progress_bar.grid_remove()
        
        # 设置Avatar控制器
        if self.main_app.client:
            # 设置Avatar控制器的OSC客户端（VRChatController）
            self.main_app.avatar_controller.set_osc_client(self.main_app.client)
            
            # 设置AI移动控制的OSC客户端
            if hasattr(self.main_app, 'ai_vrchat_area') and self.main_app.ai_vrchat_area:
                self.main_app.ai_vrchat_area.set_osc_client(self.main_app.client)
            
            # 通过VRChatController设置位置回调
            self.main_app.client.set_position_callback(self.update_player_position)
        
        self.update_ui_state(True)
        self.main_app.log(f"已连接到VRChat OSC服务器 {host}:{send_port}")
        
        # 语音识别始终启用
        self.main_app.log("语音识别模型加载完成！")
        self.main_app.log(self.main_app.get_text("voice_recognition_ready"))
    
    def _connection_failed(self, error_msg: str):
        """连接失败的UI更新"""
        # 隐藏进度条
        self.main_app.progress_bar.stop()
        self.main_app.progress_bar.grid_remove()
        
        self.main_app.connect_btn.config(text="连接", state="normal")
        messagebox.showerror(self.main_app.get_text("connection_error"), f"{self.main_app.get_text('cannot_connect_vrchat')}: {error_msg}")
        self.main_app.log(f"连接失败: {error_msg}")
    
    def disconnect_from_vrchat(self):
        """断开VRChat连接"""
        try:
            if self.main_app.client:
                # 停止语音监听
                if self.main_app.is_listening:
                    self.main_app.client.stop_voice_listening()
                    self.main_app.is_listening = False
                    self.main_app.listen_btn.config(text="开始监听")
                    self.main_app.log("已停止语音监听")
                
                # 停止OSC服务器
                self.main_app.client.stop_osc_server()
                self.main_app.log("OSC服务器已停止")
                
                # 清理资源
                self.main_app.client.cleanup()
                self.main_app.client = None
                
                # 清理Avatar控制器的OSC客户端
                if hasattr(self.main_app, 'avatar_controller') and self.main_app.avatar_controller:
                    self.main_app.avatar_controller.set_osc_client(None)
                
                # 清理AI移动控制的OSC客户端
                if hasattr(self.main_app, 'ai_vrchat_area') and self.main_app.ai_vrchat_area:
                    self.main_app.ai_vrchat_area.set_osc_client(None)
                
                # 清理单AI角色管理器（如果存在）
                if hasattr(self.main_app, 'single_ai_manager') and self.main_app.single_ai_manager:
                    try:
                        self.main_app.single_ai_manager.cleanup()
                        self.main_app.single_ai_manager = None
                        self.main_app.log("已清理AI角色管理器")
                    except Exception as e:
                        self.main_app.log(f"清理AI角色管理器时出错: {e}")
            
            self.update_ui_state(False)
            self.main_app.log("[成功] 已断开VRChat连接")
            
        except Exception as e:
            self.main_app.log(f"[错误] 断开连接时出错: {e}")
            # 即使出错也要更新UI状态
            self.update_ui_state(False)
    
    def toggle_connection(self):
        """切换连接状态"""
        if not self.main_app.is_connected:
            self.connect_to_vrchat()
        else:
            self.disconnect_from_vrchat()
    
    def update_ui_state(self, connected: bool):
        """更新UI状态"""
        self.main_app.is_connected = connected
        
        if connected:
            self.main_app.connect_btn.config(text=self.main_app.get_text("disconnect"), state="normal")
            self.main_app.status_label.config(text=self.main_app.get_text("connected"), foreground="green")
            # 启用功能按钮
            self.main_app.listen_btn.config(state="normal")
            self.main_app.upload_voice_btn.config(state="normal")
        else:
            self.main_app.connect_btn.config(text=self.main_app.get_text("connect"), state="normal")
            self.main_app.status_label.config(text=self.main_app.get_text("disconnected"), foreground="red")
            # 禁用功能按钮
            self.main_app.listen_btn.config(state="disabled")
            self.main_app.upload_voice_btn.config(state="disabled")
            
            # 停止语音监听
            if self.main_app.is_listening:
                self.main_app.is_listening = False
                self.main_app.listen_btn.config(text=self.main_app.get_text("start_listening"))
    
    def send_text_message(self):
        """发送文字消息"""
        if not self.main_app.is_connected:
            messagebox.showwarning(self.main_app.get_text("warning"), self.main_app.get_text("please_connect_first"))
            return
        
        message = self.main_app.message_entry.get().strip()
        if not message:
            return
        
        try:
            self.main_app.client.send_text_message(message)
            self.main_app.log(f"[发送文字] {message}")
            self.main_app.message_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror(self.main_app.get_text("send_error"), f"{self.main_app.get_text('send_message_failed')}: {e}")
            self.main_app.log(f"发送消息失败: {e}")
    
    def toggle_voice_listening(self):
        """切换语音监听状态"""
        if not self.main_app.is_connected:
            messagebox.showwarning(self.main_app.get_text("warning"), self.main_app.get_text("please_connect_first"))
            return
        
        if not self.main_app.is_listening:
            self.start_voice_listening()
        else:
            self.stop_voice_listening()
    
    def start_voice_listening(self):
        """开始语音监听"""
        try:
            # 检查语音引擎是否就绪
            if not self.main_app.client.speech_engine.is_model_loaded():
                messagebox.showerror(self.main_app.get_text("voice_recognition_error"), self.main_app.get_text("voice_model_not_loaded"))
                self.main_app.log("语音识别模型未加载")
                return
            
            def voice_callback(text, is_realtime=False, trigger_reason="", audio_duration=0):
                if text and text.strip():
                    if is_realtime:
                        # 实时识别结果 - 显示为预览，带触发原因
                        reason_text = f" ({trigger_reason})" if trigger_reason else ""
                        duration_text = f" {audio_duration:.1f}s" if audio_duration > 0 else ""
                        
                        display_text = f"[实时{reason_text}{duration_text}] {text}"
                        self.main_app.add_speech_output(display_text, "实时识别")
                        
                        # 记录到日志，包含更多信息
                        self.main_app.log(f"[实时语音{reason_text}] {text}")
                    else:
                        # 完整识别结果
                        self.main_app.add_speech_output(text, "持续监听")
                        # 发送到VRChat
                        self.main_app.client.send_text_message(f"[语音] {text}")
                        # 记录到日志
                        self.main_app.log(f"[持续语音] {text}")
                        
                        # 如果启用了LLM处理，发送到LLM
                        if self.main_app.llm_enabled and self.main_app.llm_handler and self.main_app.llm_handler.is_client_ready():
                            request_id = self.main_app.llm_handler.submit_voice_text(text)
                            if request_id:
                                self.main_app.log(f"[LLM] 已提交语音到AI处理: {text[:50]}...")
                            else:
                                self.main_app.log("[LLM] 提交语音到AI失败")
                    
                    # 调用原有的语音结果处理
                    self.on_voice_result(text)
            
            # 设置语音结果回调
            self.main_app.client.set_voice_result_callback(voice_callback)
            
            # 启动语音监听
            success = self.main_app.client.start_voice_listening(self.main_app.language_var.get())
            
            if success:
                self.main_app.is_listening = True
                self.main_app.listen_btn.config(text="停止监听", style="Accent.TButton")
                self.main_app.log("开始VRChat语音状态监听...")
                self.main_app.log("提示：只有当VRChat检测到你说话时才会进行语音识别")
            else:
                self.main_app.log("启动语音监听失败")
                messagebox.showerror(self.main_app.get_text("voice_recognition_error"), self.main_app.get_text("voice_listening_failed"))
            
        except Exception as e:
            messagebox.showerror(self.main_app.get_text("voice_recognition_error"), f"{self.main_app.get_text('voice_listening_failed')}: {e}")
            self.main_app.log(f"启动语音监听失败: {e}")
    
    def stop_voice_listening(self):
        """停止语音监听"""
        try:
            self.main_app.is_listening = False
            if self.main_app.client:
                self.main_app.client.stop_voice_listening()
            self.main_app.listen_btn.config(text="开始监听", style="TButton")
            self.main_app.log("停止持续语音识别")
            
        except Exception as e:
            self.main_app.log(f"停止语音监听时出错: {e}")
    
    def send_parameter(self):
        """发送Avatar参数"""
        if not self.main_app.is_connected:
            messagebox.showwarning(self.main_app.get_text("warning"), self.main_app.get_text("please_connect_first"))
            return
        
        param_name = self.main_app.param_name_entry.get().strip()
        param_value_str = self.main_app.param_value_entry.get().strip()
        
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
            
            self.main_app.client.send_parameter(param_name, param_value)
            self.main_app.log(f"[发送参数] {param_name} = {param_value}")
            
            # 清空输入框
            self.main_app.param_name_entry.delete(0, tk.END)
            self.main_app.param_value_entry.delete(0, tk.END)
            
        except Exception as e:
            messagebox.showerror("发送错误", f"发送参数失败: {e}")
            self.main_app.log(f"发送参数失败: {e}")
    
    def on_status_change(self, status_type: str, data):
        """处理状态变化"""
        if status_type == "parameter":
            param_name, value = data
            self.main_app.log(f"[收到参数] {param_name} = {value}")
        elif status_type == "message":
            msg_type, content = data
            self.main_app.log(f"[收到消息] {msg_type}: {content}")
        elif status_type == "vrc_speaking":
            self.main_app.log(f"[VRC语音状态] {'说话中' if data else '静音'}")
    
    def on_voice_result(self, text: str):
        """处理语音识别结果"""
        # 这个方法现在主要用于兼容性，实际显示已经在各个回调中处理
        pass
    
    def update_player_position(self, x, y, z):
        """更新玩家位置（从OSC调用）"""
        # 更新Avatar控制器的位置（这会自动处理角色距离计算）
        self.main_app.avatar_controller.update_player_position(x, y, z)
        
        # 为了兼容性，也保持旧的变量
        self.main_app.player_position = {"x": x, "y": y, "z": z}
        
        # 更新主界面中的位置显示
        if hasattr(self.main_app, 'current_pos_label'):
            pos_text = f"({x:.2f}, {y:.2f}, {z:.2f})"
            self.main_app.root.after(0, lambda: self.main_app.current_pos_label.config(text=pos_text))
        
        # 更新主界面中的距离显示
        self.main_app.root.after(0, self.main_app.update_character_distance_display)
        
        # 更新角色管理窗口中的位置显示
        if hasattr(self.main_app, 'position_label'):
            self.main_app.root.after(0, lambda: self.main_app.position_label.config(
                text=f"当前位置: ({x:.1f}, {y:.1f}, {z:.1f})"
            ))
    
    def update_pause_threshold(self, value):
        """更新断句间隔阈值"""
        threshold = float(value)
        if self.main_app.client and hasattr(self.main_app.client, 'set_sentence_pause_threshold'):
            self.main_app.client.set_sentence_pause_threshold(threshold)
        # 同时更新配置
        self.main_app.config.set('Recording', 'sentence_pause_threshold', threshold)
        self.main_app.pause_label.config(text=f"{threshold:.1f}s")
        self.main_app.log(f"断句间隔已设置为: {threshold:.1f}秒")