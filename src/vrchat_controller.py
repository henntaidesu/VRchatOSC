#!/usr/bin/env python3
"""
VRChat控制器 - 整合OSC通信和语音识别
"""

import threading
import time
import numpy as np
from typing import Optional, Callable
from .osc_client import OSCClient
from .speech_engine import SpeechEngine


class VRChatController:
    """VRChat控制器 - 协调OSC通信和语音识别的主控制器"""
    
    def __init__(self, host: str = "127.0.0.1", send_port: int = 9000, receive_port: int = 9001, 
                 speech_device: str = "auto"):
        """
        初始化VRChat控制器
        
        Args:
            host: VRChat主机地址
            send_port: 发送端口
            receive_port: 接收端口
            speech_device: 语音识别设备 ("auto", "cuda", "cpu")
        """
        # 创建OSC客户端
        self.osc_client = OSCClient(host, send_port, receive_port)
        
        # 创建语音引擎，使用指定设备
        self.speech_engine = SpeechEngine(device=speech_device)
        
        # 语音识别状态
        self.is_voice_listening = False
        self.voice_thread: Optional[threading.Thread] = None
        
        # 回调函数
        self.voice_result_callback: Optional[Callable] = None
        self.status_change_callback: Optional[Callable] = None
        
        # 设置OSC回调
        self.osc_client.set_parameter_callback(self._on_parameter_change)
        self.osc_client.set_message_callback(self._on_message_received)
    
    
    def _on_parameter_change(self, param_name: str, value):
        """处理OSC参数变化"""
        if param_name == "vrc_speaking_state":
            # VRChat说话状态变化
            if self.status_change_callback:
                self.status_change_callback("vrc_speaking", value)
        
        # 通知外部状态变化
        if self.status_change_callback:
            self.status_change_callback("parameter", (param_name, value))
    
    def _on_message_received(self, msg_type: str, content):
        """处理OSC消息"""
        if self.status_change_callback:
            self.status_change_callback("message", (msg_type, content))
    
    def start_osc_server(self) -> bool:
        """启动OSC服务器"""
        return self.osc_client.start_server()
    
    def stop_osc_server(self):
        """停止OSC服务器"""
        self.osc_client.stop_server()
    
    def send_text_message(self, message: str) -> bool:
        """发送文字消息"""
        return self.osc_client.send_chatbox_message(message)
    
    def send_parameter(self, param_name: str, value) -> bool:
        """发送Avatar参数"""
        return self.osc_client.send_parameter(param_name, value)
    
    def record_and_recognize(self, duration: int = 5, language: str = "ja-JP") -> Optional[str]:
        """
        录制并识别语音 - 现在使用动态语音检测
        
        Args:
            duration: 录制时长 (已弃用，保持兼容性)
            language: 识别语言
            
        Returns:
            识别结果文本
        """
        if not self.speech_engine.is_model_loaded():
            return None
        
        # 使用动态录制替代固定时长录制
        audio_data = self.speech_engine.record_audio_dynamic()
        if audio_data is None:
            return None
        
        # 识别语音
        return self.speech_engine.recognize_audio(audio_data, 16000, language)
    
    def start_voice_listening(self, language: str = "ja-JP"):
        """开始基于VRChat状态的语音监听"""
        if self.is_voice_listening:
            return False
        
        if not self.speech_engine.is_model_loaded():
            print("语音引擎未就绪")
            return False
        
        self.is_voice_listening = True
        self.voice_thread = threading.Thread(
            target=self._voice_listening_loop, 
            args=(language,), 
            daemon=True
        )
        self.voice_thread.start()
        return True
    
    def stop_voice_listening(self):
        """停止语音监听"""
        self.is_voice_listening = False
        if self.voice_thread:
            self.voice_thread.join(timeout=1)
    
    def _voice_listening_loop(self, language: str):
        """语音监听循环"""
        print("开始语音监听循环...")
        print(f"使用语言: {language}")
        print(f"语音引擎就绪: {self.speech_engine.is_model_loaded()}")
        
        consecutive_failures = 0
        max_failures = 5
        last_recognition_time = 0
        recognition_interval = 1.0  # 至少间隔1秒进行下一次识别
        
        while self.is_voice_listening:
            try:
                current_time = time.time()
                
                # 重要：只有当VRChat检测到说话时才录制和识别
                if not self.osc_client.get_vrc_speaking_state():
                    time.sleep(0.1)  # VRChat未检测到语音，继续等待
                    continue
                
                # 防止过于频繁的识别
                if current_time - last_recognition_time < recognition_interval:
                    time.sleep(0.1)
                    continue
                
                print(f"VRChat检测到语音状态，开始录制...")
                
                # 使用动态语音检测录制音频
                audio_data = self.speech_engine.record_audio_dynamic()
                
                if audio_data is None:
                    print("录制失败，继续监听...")
                    time.sleep(0.1)
                    continue
                
                last_recognition_time = current_time
                
                # 后台识别
                def recognize():
                    nonlocal consecutive_failures
                    try:
                        # 再次确认VRChat状态（防止状态在录制期间改变）
                        if not self.osc_client.get_vrc_speaking_state():
                            print("VRChat语音状态已结束，跳过识别")
                            return
                        
                        # 检测语音活动
                        if not self.speech_engine.detect_voice_activity(audio_data):
                            print("录制的音频中未检测到语音活动")
                            return
                        
                        print("VRChat语音状态确认，开始语音识别...")
                        
                        # 识别语音
                        text = self.speech_engine.recognize_audio(audio_data, 16000, language)
                        
                        if text and text.strip():
                            consecutive_failures = 0
                            print(f"VRC语音识别结果: {text.strip()}")
                            if self.voice_result_callback:
                                self.voice_result_callback(text.strip())
                        else:
                            consecutive_failures += 1
                            print("语音识别结果为空")
                            
                    except Exception as e:
                        consecutive_failures += 1
                        print(f"识别错误: {e}")
                    
                    # 连续失败处理
                    if consecutive_failures >= max_failures:
                        print(f"连续失败{max_failures}次，暂停2秒...")
                        time.sleep(2)
                        consecutive_failures = 0
                
                threading.Thread(target=recognize, daemon=True).start()
                
            except Exception as e:
                print(f"语音监听错误: {e}")
                time.sleep(1)
        
        print("语音监听循环已停止")
    
    def set_voice_result_callback(self, callback: Callable):
        """设置语音识别结果回调"""
        self.voice_result_callback = callback
    
    def set_status_change_callback(self, callback: Callable):
        """设置状态变化回调"""
        self.status_change_callback = callback
    
    def set_voice_threshold(self, threshold: float):
        """设置语音激活阈值"""
        self.speech_engine.set_voice_threshold(threshold)
    
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "osc_connected": self.osc_client.is_running,
            "vrc_speaking": self.osc_client.get_vrc_speaking_state(),
            "vrc_voice_level": self.osc_client.get_vrc_voice_level(),
            "voice_listening": self.is_voice_listening,
            "speech_engine_ready": self.speech_engine.is_model_loaded()
        }
    
    def cleanup(self):
        """清理资源"""
        self.stop_voice_listening()
        self.stop_osc_server()