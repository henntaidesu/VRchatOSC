# -*- coding: utf-8 -*-
"""
VRChat服务层
负责处理VRChat OSC连接、断开、消息发送、语音监听等纯业务逻辑
与UI层分离，只处理数据和业务操作
"""

import threading
import time
import os

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    
try:
    from src.vrchat_controller import VRChatController
    VRCHAT_CONTROLLER_AVAILABLE = True
except ImportError:
    VRCHAT_CONTROLLER_AVAILABLE = False


class VRChatService:
    def __init__(self, config_manager):
        """
        初始化VRChat服务
        
        Args:
            config_manager: 配置管理器
        """
        self.config = config_manager
        self.client = None
        self.is_connected = False
        self.is_listening = False
        
        # 分段识别相关
        self.segment_texts = []
        self.is_segmented_recognition = False
        
        # 回调函数
        self.status_change_callback = None
        self.voice_result_callback = None
        self.connection_status_callback = None
        self.log_callback = None
        
    def set_callbacks(self, status_change_cb=None, voice_result_cb=None, 
                     connection_status_cb=None, log_cb=None):
        """设置回调函数"""
        if status_change_cb:
            self.status_change_callback = status_change_cb
        if voice_result_cb:
            self.voice_result_callback = voice_result_cb
        if connection_status_cb:
            self.connection_status_callback = connection_status_cb
        if log_cb:
            self.log_callback = log_cb
    
    def log(self, message: str):
        """日志记录"""
        if self.log_callback:
            self.log_callback(message)
    
    def connect_async(self, host=None, send_port=None, receive_port=None, device=None):
        """
        异步连接到VRChat
        
        Args:
            host: 主机地址
            send_port: 发送端口
            receive_port: 接收端口  
            device: 设备类型
            
        Returns:
            bool: 连接是否成功启动（实际连接结果通过回调返回）
        """
        try:
            # 获取连接参数
            host = host or self.config.osc_host
            send_port = send_port or self.config.osc_send_port
            receive_port = receive_port or self.config.osc_receive_port
            device = device or self.config.voice_device
            
            self.log(f"开始连接VRChat: {host}:{send_port}")
            self.log(f"正在加载语音模型 ({device})...")
            self.log("首次加载可能需要较长时间，请耐心等待...")
            
            # 在后台线程中连接，避免界面卡顿
            def connect_thread():
                try:
                    # 创建OSC客户端
                    use_config_host = host == self.config.osc_host
                    use_config_ports = (send_port == self.config.osc_send_port and 
                                       receive_port == self.config.osc_receive_port)
                    use_config_device = device == self.config.voice_device
                    
                    if not VRCHAT_CONTROLLER_AVAILABLE:
                        raise Exception("VRChatController模块不可用，请检查依赖是否正确安装")
                        
                    self.client = VRChatController(
                        host=None if use_config_host else host,
                        send_port=None if use_config_ports else send_port,
                        receive_port=None if use_config_ports else receive_port,
                        speech_device=None if use_config_device else device
                    )
                    
                    # 设置回调函数
                    self.client.set_status_change_callback(self.on_status_change)
                    self.client.set_voice_result_callback(self.on_voice_result)
                    
                    # 启动服务器
                    success = self.client.start_osc_server()
                    
                    if success:
                        self.is_connected = True
                        self.log(f"VRChat连接成功: {host}:{send_port}")
                        self.log("语音模型加载完成，语音识别功能已就绪")
                        
                        if self.connection_status_callback:
                            self.connection_status_callback(True, host, send_port)
                    else:
                        self.log("OSC服务器启动失败")
                        if self.connection_status_callback:
                            self.connection_status_callback(False, "OSC服务器启动失败")
                        
                except Exception as e:
                    self.log(f"VRChat连接失败: {e}")
                    if self.connection_status_callback:
                        self.connection_status_callback(False, str(e))
            
            # 启动连接线程
            threading.Thread(target=connect_thread, daemon=True).start()
            return True
            
        except Exception as e:
            self.log(f"启动VRChat连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开VRChat连接"""
        try:
            if self.client:
                # 停止语音监听
                if self.is_listening:
                    self.stop_voice_listening()
                
                # 停止OSC服务器
                self.client.stop_osc_server()
                self.log("OSC服务器已停止")
                
                # 清理资源
                self.client.cleanup()
                self.client = None
                
                self.is_connected = False
                self.log("VRChat连接已断开")
                
                if self.connection_status_callback:
                    self.connection_status_callback(False, "主动断开连接")
                
                return True
            
        except Exception as e:
            self.log(f"断开VRChat连接时出错: {e}")
            # 即使出错也要重置状态
            self.is_connected = False
            if self.connection_status_callback:
                self.connection_status_callback(False, "断开连接出错")
            return False
    
    def send_text_message(self, message: str) -> bool:
        """
        发送文字消息
        
        Args:
            message: 要发送的消息
            
        Returns:
            bool: 是否发送成功
        """
        if not self.is_connected or not self.client:
            self.log("VRChat未连接，无法发送消息")
            return False
        
        if not message.strip():
            return False
        
        try:
            self.client.send_text_message(message)
            self.log(f"[发送文本] {message}")
            return True
        except Exception as e:
            self.log(f"发送消息失败: {e}")
            return False
    
    def send_parameter(self, param_name: str, param_value) -> bool:
        """
        发送Avatar参数
        
        Args:
            param_name: 参数名
            param_value: 参数值
            
        Returns:
            bool: 是否发送成功
        """
        if not self.is_connected or not self.client:
            self.log("VRChat未连接，无法发送参数")
            return False
        
        if not param_name.strip():
            return False
        
        try:
            # 尝试转换参数值类型
            converted_value = self._convert_parameter_value(str(param_value))
            
            self.client.send_parameter(param_name, converted_value)
            self.log(f"[发送参数] {param_name} = {converted_value}")
            return True
        except Exception as e:
            self.log(f"发送参数失败: {e}")
            return False
    
    def _convert_parameter_value(self, param_value_str: str):
        """转换参数值类型"""
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
        return param_value
    
    def start_voice_listening(self, language: str = None) -> bool:
        """
        开始语音监听
        
        Args:
            language: 识别语言
            
        Returns:
            bool: 是否启动成功
        """
        if not self.is_connected or not self.client:
            self.log("VRChat未连接，无法启动语音监听")
            return False
        
        try:
            # 检查语音引擎是否就绪
            if not self.client.speech_engine.is_model_loaded():
                self.log("语音模型未加载")
                return False
            
            # 重置分段识别状态
            self.segment_texts = []
            self.is_segmented_recognition = False
            
            # 创建语音回调函数
            def voice_callback(text, is_realtime=False, trigger_reason="", audio_duration=0):
                self._handle_voice_result(text, is_realtime, trigger_reason, audio_duration)
            
            # 设置语音结果回调
            self.client.set_voice_result_callback(voice_callback)
            
            # 启动语音监听
            language = language or self.config.voice_language
            success = self.client.start_voice_listening(language)
            
            if success:
                self.is_listening = True
                self.log("语音监听已启动")
                self.log("提示：在VRChat中开启麦克风或说话时会自动识别")
                return True
            else:
                self.log("语音监听启动失败")
                return False
            
        except Exception as e:
            self.log(f"启动语音监听失败: {e}")
            return False
    
    def stop_voice_listening(self) -> bool:
        """
        停止语音监听
        
        Returns:
            bool: 是否停止成功
        """
        try:
            self.is_listening = False
            if self.client:
                self.client.stop_voice_listening()
            self.log("语音监听已停止")
            return True
            
        except Exception as e:
            self.log(f"停止语音监听失败: {e}")
            return False
    
    def _handle_voice_result(self, text: str, is_realtime: bool, trigger_reason: str, audio_duration: float):
        """处理语音识别结果的内部逻辑"""
        if not text or not text.strip():
            return
        
        try:
            if is_realtime:
                # 实时识别结果处理
                reason_text = f" ({trigger_reason})" if trigger_reason else ""
                duration_text = f" {audio_duration:.1f}s" if audio_duration > 0 else ""
                
                # 检查是否启动分段识别（超过4.8秒）
                if audio_duration > 4.8 and not self.is_segmented_recognition:
                    self.is_segmented_recognition = True
                    self.segment_texts = []
                    self.log("[分段识别] 检测到长音频，启动分段识别模式")
                
                # 分段识别模式处理
                if self.is_segmented_recognition:
                    if trigger_reason == "silence_detected" or trigger_reason == "mic_closed":
                        # 添加这一段文本
                        if text.strip() and text.strip() not in self.segment_texts:
                            self.segment_texts.append(text.strip())
                            self.log(f"[分段识别] 添加片段: {text.strip()}")
                        
                        # 如果是麦克风关闭，合并所有片段
                        if trigger_reason == "mic_closed" and self.segment_texts:
                            combined_text = " ".join(self.segment_texts)
                            self.log(f"[分段识别] 麦克风关闭，合并文本: {combined_text}")
                            self._send_complete_recognition(combined_text)
                            
                            # 重置分段识别状态
                            self.is_segmented_recognition = False
                            self.segment_texts = []
                    else:
                        # 实时显示当前片段
                        display_text = f"[分段识别{reason_text}{duration_text}] {text}"
                        if self.voice_result_callback:
                            self.voice_result_callback(display_text, "分段识别")
                else:
                    # 普通实时识别显示
                    display_text = f"[实时识别{reason_text}{duration_text}] {text}"
                    if self.voice_result_callback:
                        self.voice_result_callback(display_text, "实时识别")
                
                self.log(f"[实时识别{reason_text}] {text}")
            else:
                # 完整识别结果
                if not self.is_segmented_recognition:
                    # 单次完整识别
                    if self.voice_result_callback:
                        self.voice_result_callback(text, "完整识别")
                    self.log(f"[完整语音] {text} - 立即处理")
                    self._send_complete_recognition(text)
                else:
                    # 分段模式中的完整结果会被分段逻辑处理
                    self.log(f"[分段模式处理] 完整识别已被分段逻辑处理: {text}")
                    
        except Exception as e:
            self.log(f"处理语音结果时出错: {e}")
    
    def _send_complete_recognition(self, text: str):
        """发送完整的识别结果（用于LLM处理等）"""
        if self.voice_result_callback:
            # 通过特殊标识告知这是最终完整结果
            self.voice_result_callback(text, "最终结果", final=True)
    
    def on_status_change(self, status_type: str, data):
        """处理状态变化"""
        try:
            if self.status_change_callback:
                self.status_change_callback(status_type, data)
            
            if status_type == "parameter":
                param_name, value = data
                self.log(f"[接收参数] {param_name} = {value}")
            elif status_type == "message":
                msg_type, content = data
                self.log(f"[接收消息] {msg_type}: {content}")
            elif status_type == "vrc_speaking":
                self.log(f"[语音状态] {'说话中' if data else '静音'}")
                
        except Exception as e:
            self.log(f"处理状态变化时出错: {e}")
    
    def on_voice_result(self, text: str, is_realtime=False, trigger_reason="", audio_duration=0):
        """处理语音识别结果（供外部调用）"""
        if self.voice_result_callback:
            self.voice_result_callback(text, "语音识别")
        self.log(f"[语音识别] {text}")
    
    def update_voice_threshold(self, threshold: float):
        """更新语音阈值"""
        if self.client and hasattr(self.client, 'set_voice_threshold'):
            self.client.set_voice_threshold(threshold)
            self.config.set('Voice', 'voice_threshold', threshold)
            self.log(f"语音阈值已设置为: {threshold:.3f}")
    
    def update_pause_threshold(self, threshold: float):
        """更新断句间隔阈值"""
        if self.client and hasattr(self.client, 'set_sentence_pause_threshold'):
            self.client.set_sentence_pause_threshold(threshold)
            self.config.set('Recording', 'sentence_pause_threshold', threshold)
            self.log(f"断句间隔阈值已设置为: {threshold:.1f}秒")
    
    def update_player_position(self, x: float, y: float, z: float):
        """更新玩家位置"""
        if self.status_change_callback:
            self.status_change_callback("player_position", (x, y, z))
    
    def get_connection_status(self) -> dict:
        """获取连接状态信息"""
        return {
            'is_connected': self.is_connected,
            'is_listening': self.is_listening,
            'client_ready': self.client is not None,
            'speech_engine_ready': self.client.speech_engine.is_model_loaded() if self.client else False
        }
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.is_connected:
                self.disconnect()
            self.client = None
            self.is_connected = False
            self.is_listening = False
        except Exception as e:
            self.log(f"清理VRChat服务资源时出错: {e}")
