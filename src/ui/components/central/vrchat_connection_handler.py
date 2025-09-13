# -*- coding: utf-8 -*-
"""
VRChat连接处理UI功能类
负责处理VRChat连接相关的UI交互逻辑
"""

import tkinter as tk
from tkinter import messagebox

try:
    from src.services.vrchat_service import VRChatService
    VRCHAT_SERVICE_AVAILABLE = True
except ImportError:
    VRCHAT_SERVICE_AVAILABLE = False


class VRChatConnectionHandler:
    """VRChat连接管理UI功能类"""
    
    def __init__(self, main_app):
        """
        初始化VRChat连接处理器
        
        Args:
            main_app: 主应用程序实例
        """
        self.main_app = main_app
        
        if VRCHAT_SERVICE_AVAILABLE:
            self.vrchat_service = VRChatService(main_app.config)
            # 设置服务层回调
            self._setup_service_callbacks()
        else:
            self.vrchat_service = None
            self.main_app.log("VRChat服务不可用，相关功能将受限")
    
    def _setup_service_callbacks(self):
        """设置服务层回调函数"""
        self.vrchat_service.set_callbacks(
            status_change_cb=self.on_status_change,
            voice_result_cb=self.on_voice_result,
            connection_status_cb=self.on_connection_status_change,
            log_cb=self.main_app.log
        )
    
    def toggle_connection(self):
        """切换连接状态"""
        if not self.vrchat_service:
            self.main_app.log("VRChat服务不可用")
            return
            
        if not self.vrchat_service.is_connected:
            self.connect_to_vrchat()
        else:
            self.disconnect_from_vrchat()
    
    def connect_to_vrchat(self):
        """连接到VRChat"""
        try:
            host = self.main_app.host_var.get().strip()
            send_port = int(self.main_app.send_port_var.get())
            receive_port = int(self.main_app.receive_port_var.get())
            device = self.main_app.device_var.get()
            
            # 禁用连接按钮并显示加载状态
            self.main_app.connect_btn.config(
                text=self.main_app.get_text("user_vrc_connecting"), 
                state="disabled"
            )
            self.main_app.progress_bar.grid()
            self.main_app.progress_bar.start()
            
            # 异步连接
            success = self.vrchat_service.connect_async(host, send_port, receive_port, device)
            
            if not success:
                self._connection_failed("连接启动失败")
            
        except ValueError:
            self._connection_failed("端口必须是数字")
        except Exception as e:
            self._connection_failed(str(e))
    
    def disconnect_from_vrchat(self):
        """断开VRChat连接"""
        try:
            success = self.vrchat_service.disconnect()
            if success:
                self.update_ui_state(False)
                self.main_app.log("VRChat连接已断开")
            else:
                self.main_app.log("断开连接时出现问题")
                
        except Exception as e:
            self.main_app.log(f"断开连接错误: {e}")
            # 即使出错也要更新UI状态
            self.update_ui_state(False)
    
    def send_text_message(self):
        """发送文字消息"""
        message = self.main_app.message_entry.get().strip()
        if not message:
            return
        
        success = self.vrchat_service.send_text_message(message)
        if success:
            self.main_app.message_entry.delete(0, tk.END)
        else:
            messagebox.showwarning(
                self.main_app.get_text("warning"), 
                self.main_app.get_text("please_connect_first")
            )
    
    def send_parameter(self):
        """发送Avatar参数"""
        param_name = self.main_app.param_name_entry.get().strip()
        param_value_str = self.main_app.param_value_entry.get().strip()
        
        if not param_name or not param_value_str:
            messagebox.showwarning(
                self.main_app.get_text("warning"), 
                self.main_app.get_text("user_vrc_param_empty_warning")
            )
            return
        
        success = self.vrchat_service.send_parameter(param_name, param_value_str)
        if success:
            # 清空输入框
            self.main_app.param_name_entry.delete(0, tk.END)
            self.main_app.param_value_entry.delete(0, tk.END)
        else:
            messagebox.showwarning(
                self.main_app.get_text("warning"),
                self.main_app.get_text("please_connect_first")
            )
    
    def toggle_voice_listening(self):
        """切换语音监听状态"""
        if not self.vrchat_service.is_connected:
            messagebox.showwarning(
                self.main_app.get_text("warning"), 
                self.main_app.get_text("please_connect_first")
            )
            return
        
        if not self.vrchat_service.is_listening:
            self.start_voice_listening()
        else:
            self.stop_voice_listening()
    
    def start_voice_listening(self):
        """开始语音监听"""
        language = self.main_app.language_var.get()
        success = self.vrchat_service.start_voice_listening(language)
        
        if success:
            self.main_app.is_listening = True
            self.main_app.listen_btn.config(
                text=self.main_app.get_text("user_vrc_stop_listening"), 
                style="Accent.TButton"
            )
            self.main_app.log("语音监听已启动")
        else:
            messagebox.showerror(
                self.main_app.get_text("voice_recognition_error"), 
                self.main_app.get_text("voice_listening_failed")
            )
    
    def stop_voice_listening(self):
        """停止语音监听"""
        success = self.vrchat_service.stop_voice_listening()
        
        if success:
            self.main_app.is_listening = False
            self.main_app.listen_btn.config(
                text=self.main_app.get_text("user_vrc_start_listening"), 
                style="TButton"
            )
    
    def update_voice_threshold(self, value):
        """更新语音阈值"""
        threshold = float(value)
        self.vrchat_service.update_voice_threshold(threshold)
        self.main_app.threshold_label.config(text=f"{threshold:.3f}")
    
    def update_pause_threshold(self, value):
        """更新断句间隔阈值"""
        threshold = float(value)
        self.vrchat_service.update_pause_threshold(threshold)
        self.main_app.pause_label.config(text=f"{threshold:.1f}s")
    
    def on_connection_status_change(self, connected: bool, info: str = None):
        """连接状态变化回调"""
        # 在主线程中更新UI
        self.main_app.root.after(0, lambda: self._update_connection_ui(connected, info))
    
    def _update_connection_ui(self, connected: bool, info: str = None):
        """更新连接相关UI（在主线程中调用）"""
        # 隐藏进度条
        self.main_app.progress_bar.stop()
        self.main_app.progress_bar.grid_remove()
        
        if connected:
            self._connection_success(info)
        else:
            self._connection_failed(info or "连接失败")
    
    def _connection_success(self, info: str):
        """连接成功的UI更新"""
        # 设置Avatar控制器
        if self.vrchat_service.client:
            self.main_app.avatar_controller.set_osc_client(self.vrchat_service.client)
            
            # 设置AI移动控制的OSC客户端
            if hasattr(self.main_app, 'ai_vrchat_manager') and self.main_app.ai_vrchat_manager:
                self.main_app.ai_vrchat_manager.set_osc_client(self.vrchat_service.client)
        
        self.update_ui_state(True)
        self.main_app.log(f"VRChat连接成功: {info}")
    
    def _connection_failed(self, error_msg: str):
        """连接失败的UI更新"""
        self.main_app.connect_btn.config(
            text=self.main_app.get_text("connect"), 
            state="normal"
        )
        messagebox.showerror(
            self.main_app.get_text("connection_error"), 
            f"{self.main_app.get_text('cannot_connect_vrchat')}: {error_msg}"
        )
        self.main_app.log(f"VRChat连接失败: {error_msg}")
    
    def update_ui_state(self, connected: bool):
        """更新UI状态"""
        self.main_app.is_connected = connected
        
        if connected:
            self.main_app.connect_btn.config(
                text=self.main_app.get_text("disconnect"), 
                state="normal"
            )
            self.main_app.status_label.config(
                text=self.main_app.get_text("connected"), 
                foreground="green"
            )
            # 启用功能按钮
            self.main_app.listen_btn.config(state="normal")
            self.main_app.upload_voice_btn.config(state="normal")
        else:
            self.main_app.connect_btn.config(
                text=self.main_app.get_text("connect"), 
                state="normal"
            )
            self.main_app.status_label.config(
                text=self.main_app.get_text("disconnected"), 
                foreground="red"
            )
            # 禁用功能按钮
            self.main_app.listen_btn.config(state="disabled")
            self.main_app.upload_voice_btn.config(state="disabled")
            
            # 停止语音监听
            if self.main_app.is_listening:
                self.main_app.is_listening = False
                self.main_app.listen_btn.config(
                    text=self.main_app.get_text("start_listening")
                )
    
    def on_status_change(self, status_type: str, data):
        """处理状态变化"""
        if status_type == "parameter":
            param_name, value = data
            self.main_app.log(f"[接收参数] {param_name} = {value}")
        elif status_type == "message":
            msg_type, content = data
            self.main_app.log(f"[接收消息] {msg_type}: {content}")
        elif status_type == "vrc_speaking":
            self.main_app.log(f"[语音状态] {'说话中' if data else '静音'}")
        elif status_type == "player_position":
            x, y, z = data
            self.update_player_position(x, y, z)
    
    def on_voice_result(self, text: str, source: str = None, final: bool = False):
        """处理语音识别结果"""
        # 显示语音识别结果
        self.main_app.add_speech_output(text, source or "语音识别")
        
        # 如果是最终结果，发送到LLM处理
        if final and hasattr(self.main_app, 'llm_processor') and self.main_app.llm_processor:
            try:
                success = self.main_app.llm_processor.process_voice_text(text.strip())
                if success:
                    self.main_app.log(f"[LLM] 文本已发送: {text.strip()}")
                else:
                    self.main_app.log(f"[LLM] 发送失败: {text.strip()}")
            except Exception as e:
                self.main_app.log(f"[LLM] 处理错误: {e}")
    
    def update_player_position(self, x: float, y: float, z: float):
        """更新玩家位置"""
        # 更新Avatar控制器的位置
        if hasattr(self.main_app, 'avatar_controller'):
            self.main_app.avatar_controller.update_player_position(x, y, z)
        
        # 更新主界面中的位置显示
        if hasattr(self.main_app, 'current_pos_label'):
            pos_text = f"({x:.2f}, {y:.2f}, {z:.2f})"
            self.main_app.root.after(0, 
                lambda: self.main_app.current_pos_label.config(text=pos_text)
            )
    
    def cleanup(self):
        """清理资源"""
        if self.vrchat_service:
            self.vrchat_service.cleanup()
