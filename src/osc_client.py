#!/usr/bin/env python3
"""
OSC客户端 - 纯网络通信逻辑，不包含语音识别
"""

import threading
import time
from typing import Optional, Callable, Any
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer


class OSCClient:
    """OSC通信客户端类 - 只负责OSC消息的发送和接收"""
    
    def __init__(self, host: str = "127.0.0.1", send_port: int = 9000, receive_port: int = 9001):
        """
        初始化OSC客户端
        
        Args:
            host: 目标主机地址
            send_port: 发送端口
            receive_port: 接收端口
        """
        self.host = host
        self.send_port = send_port
        self.receive_port = receive_port
        
        # 创建OSC客户端用于发送消息
        self.client = udp_client.SimpleUDPClient(host, send_port)
        
        # 创建OSC服务器用于接收消息
        self.dispatcher = Dispatcher()
        self._setup_dispatcher()
        
        # 服务器实例
        self.server: Optional[BlockingOSCUDPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # 回调函数
        self.parameter_callback: Optional[Callable] = None
        self.message_callback: Optional[Callable] = None
        
        # VRChat状态
        self.vrc_is_speaking = False
        self.vrc_voice_level = 0.0
        
        # 调试设置
        self.debug_mode = False
        self.voice_parameters_received = set()  # 记录收到的语音相关参数
        
        # 扩展语音参数监听列表
        self.voice_parameter_names = [
            "Voice", "VoiceLevel", "Viseme", "MouthOpen", "VoiceGain",
            "VoiceThreshold", "MicLevel", "IsSpeaking", "IsListening",
            "VRC_Voice", "VRC_VoiceLevel", "VRC_Viseme", "Speech",
            "Talking", "MouthMove", "VoiceActivity"
        ]
        
        print(f"OSC客户端初始化完成")
        print(f"发送地址: {host}:{send_port}")
        print(f"接收端口: {receive_port}")
    
    def _setup_dispatcher(self):
        """设置OSC消息分发器"""
        # 处理聊天消息
        self.dispatcher.map("/chatbox/input", self._handle_chatbox_input)
        self.dispatcher.map("/chatbox/typing", self._handle_chatbox_typing)
        
        # 处理参数变化
        self.dispatcher.map("/avatar/parameters/*", self._handle_parameter_change)
        
        # 处理通用消息
        self.dispatcher.set_default_handler(self._handle_default_message)
    
    def _handle_chatbox_input(self, address: str, *args):
        """处理聊天框输入消息"""
        if args and self.message_callback:
            self.message_callback("chatbox_input", args[0])
    
    def _handle_chatbox_typing(self, address: str, *args):
        """处理聊天框打字状态"""
        if args and self.message_callback:
            self.message_callback("chatbox_typing", bool(args[0]))
    
    def _handle_parameter_change(self, address: str, *args):
        """处理参数变化"""
        if args:
            parameter_name = address.split("/")[-1]
            value = args[0]
            
            # 调试模式：记录所有参数
            if self.debug_mode:
                print(f"[OSC调试] 参数: {parameter_name} = {value} (地址: {address})")
            
            # 处理语音相关参数
            if parameter_name in self.voice_parameter_names:
                # 记录收到的语音参数
                self.voice_parameters_received.add(parameter_name)
                
                # 更新语音状态和强度
                old_speaking = self.vrc_is_speaking
                old_level = self.vrc_voice_level
                
                # 尝试从不同参数获取语音强度
                if parameter_name in ["Voice", "VoiceLevel", "MicLevel", "VRC_VoiceLevel"]:
                    self.vrc_voice_level = float(value) if value else 0.0
                elif parameter_name in ["IsSpeaking", "Talking", "VoiceActivity", "Speech"]:
                    # 布尔类型的语音状态
                    self.vrc_is_speaking = bool(value)
                    if self.vrc_is_speaking and self.vrc_voice_level <= 0.01:
                        self.vrc_voice_level = 0.5  # 设置默认强度
                elif parameter_name in ["Viseme", "MouthOpen", "MouthMove"]:
                    # 嘴部动作参数，可能表示说话
                    mouth_value = float(value) if value else 0.0
                    if mouth_value > 0.1:
                        self.vrc_voice_level = max(self.vrc_voice_level, mouth_value)
                
                # 更新说话状态 (使用更灵活的阈值)
                if parameter_name not in ["IsSpeaking", "Talking", "VoiceActivity", "Speech"]:
                    self.vrc_is_speaking = self.vrc_voice_level > 0.005  # 降低阈值
                
                # 调试输出语音状态变化
                if self.debug_mode or (self.vrc_is_speaking != old_speaking):
                    status_text = "开始说话" if self.vrc_is_speaking else "停止说话"
                    print(f"VRChat语音状态: {status_text} (参数: {parameter_name}, 值: {value}, Level: {self.vrc_voice_level:.4f})")
                
                # 通知状态变化
                if self.parameter_callback:
                    self.parameter_callback(parameter_name, value)
                    if self.vrc_is_speaking != old_speaking:
                        self.parameter_callback("vrc_speaking_state", self.vrc_is_speaking)
            
            # 通知所有参数变化
            elif self.parameter_callback:
                self.parameter_callback(parameter_name, value)
    
    def _handle_default_message(self, address: str, *args):
        """处理默认消息"""
        # 只记录非参数消息
        if "/avatar/parameters/" not in address and self.message_callback:
            self.message_callback("osc_message", (address, args))
    
    def start_server(self):
        """启动OSC服务器"""
        if self.is_running:
            return False
            
        try:
            self.server = BlockingOSCUDPServer(("127.0.0.1", self.receive_port), self.dispatcher)
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.is_running = True
            self.server_thread.start()
            print(f"OSC服务器已启动，监听端口: {self.receive_port}")
            return True
        except Exception as e:
            print(f"启动服务器失败: {e}")
            self.is_running = False
            return False
    
    def _run_server(self):
        """运行OSC服务器"""
        try:
            self.server.serve_forever()
        except Exception as e:
            print(f"服务器运行错误: {e}")
        finally:
            self.is_running = False
    
    def stop_server(self):
        """停止OSC服务器"""
        if self.server and self.is_running:
            self.server.shutdown()
            self.is_running = False
            print("OSC服务器已停止")
    
    def send_chatbox_message(self, message: str, send_immediately: bool = True, show_in_chatbox: bool = True):
        """发送聊天框消息"""
        try:
            self.client.send_message("/chatbox/input", [message, send_immediately, show_in_chatbox])
            return True
        except Exception as e:
            print(f"发送消息失败: {e}")
            return False
    
    def send_parameter(self, parameter_name: str, value: Any):
        """发送Avatar参数"""
        try:
            address = f"/avatar/parameters/{parameter_name}"
            self.client.send_message(address, value)
            return True
        except Exception as e:
            print(f"发送参数失败: {e}")
            return False
    
    def set_parameter_callback(self, callback: Callable):
        """设置参数变化回调函数"""
        self.parameter_callback = callback
    
    def set_message_callback(self, callback: Callable):
        """设置消息回调函数"""
        self.message_callback = callback
    
    def get_vrc_speaking_state(self) -> bool:
        """获取VRChat说话状态"""
        return self.vrc_is_speaking
    
    def get_vrc_voice_level(self) -> float:
        """获取VRChat语音强度"""
        return self.vrc_voice_level
    
    def set_debug_mode(self, enabled: bool):
        """设置调试模式"""
        self.debug_mode = enabled
        if enabled:
            print("OSC调试模式已启用")
        else:
            print("OSC调试模式已禁用")
    
    def get_received_voice_parameters(self) -> set:
        """获取已接收到的语音参数列表"""
        return self.voice_parameters_received.copy()
    
    def get_debug_info(self) -> dict:
        """获取调试信息"""
        return {
            "debug_mode": self.debug_mode,
            "is_running": self.is_running,
            "vrc_is_speaking": self.vrc_is_speaking,
            "vrc_voice_level": self.vrc_voice_level,
            "received_voice_parameters": list(self.voice_parameters_received),
            "monitoring_parameters": self.voice_parameter_names
        }