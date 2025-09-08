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
        
        # 位置追踪
        self.player_position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.position_callback: Optional[Callable] = None
        
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
        
        # 音频传输相关
        self.audio_chunks = {}  # 存储接收到的音频块
        self.audio_total_chunks = 0
        self.audio_duration = 0.0
        self.audio_receiving = False
        
        # 实时语音识别缓冲区
        self.audio_buffer = []  # 累积的音频数据
        self.buffer_size_limit = 4  # 缓冲区大小限制（秒）
        self.recognition_interval = 0.8  # 识别间隔（秒）- 稍微缩短提高响应
        self.last_recognition_time = 0
        self.sample_rate = 16000  # 假设采样率
        self.min_recognition_chunks = 8  # 最少需要0.8秒数据才识别
        self.overlap_chunks = 6  # 重叠保留0.6秒数据，避免截断
        
        # 语音边界检测
        self.silence_threshold = 0.001  # 静音阈值
        self.speech_activity_history = []  # 语音活动历史
        
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
        
        # 处理位置数据 (VRChat提供的位置信息)
        self.dispatcher.map("/tracking/head/position", self._handle_position_update)
        self.dispatcher.map("/tracking/head/rotation", self._handle_rotation_update)
        self.dispatcher.map("/avatar/change", self._handle_avatar_change)
        
        # 处理音频传输消息
        self.dispatcher.map("/vrchat/audio/start", self._handle_audio_start)
        self.dispatcher.map("/vrchat/audio/chunk", self._handle_audio_chunk)
        self.dispatcher.map("/vrchat/audio/end", self._handle_audio_end)
        
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
                print(f"[OSC收到] {parameter_name} = {value}")
                
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
                    # 如果有语音强度参数，使用阈值判断
                    if parameter_name in ["Voice", "VoiceLevel", "MicLevel", "VRC_VoiceLevel"]:
                        self.vrc_is_speaking = self.vrc_voice_level > 0.005
                    # 如果是嘴部动作参数，使用更宽松的条件
                    elif parameter_name in ["Viseme", "MouthOpen", "MouthMove"]:
                        self.vrc_is_speaking = self.vrc_is_speaking or (float(value) if value else 0.0) > 0.02
                
                # 调试输出语音状态变化
                if self.debug_mode or (self.vrc_is_speaking != old_speaking):
                    status_text = "开始说话" if self.vrc_is_speaking else "停止说话"
                    print(f"[OSC] {parameter_name}={value} -> {status_text} (强度:{self.vrc_voice_level:.3f})")
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
    
    def send_message(self, address: str, value: Any):
        """发送通用OSC消息"""
        try:
            self.client.send_message(address, value)
            return True
        except Exception as e:
            print(f"发送OSC消息失败 {address}: {e}")
            return False
    
    def send_input_command(self, command: str, value: float):
        """发送输入控制指令到VRChat"""
        address = f"/input/{command}"
        return self.send_message(address, value)
    
    def send_movement_command(self, direction: str, speed: float):
        """发送移动控制指令"""
        movement_commands = {
            "forward": "MoveForward",
            "backward": "MoveBackward", 
            "left": "MoveLeft",
            "right": "MoveRight",
            "turn_left": "LookHorizontal",
            "turn_right": "LookHorizontal",
            "look_up": "LookVertical",
            "look_down": "LookVertical",
            "jump": "Jump"
        }
        
        if direction in movement_commands:
            command = movement_commands[direction]
            # 对于左转，使用负值
            if direction == "turn_left":
                speed = -speed
            # 对于下看，使用负值
            elif direction == "look_down":
                speed = -speed
            # 跳跃使用固定值
            elif direction == "jump":
                speed = 1.0
            return self.send_input_command(command, speed)
        else:
            print(f"未知的移动方向: {direction}")
            return False
    
    def set_parameter_callback(self, callback: Callable):
        """设置参数变化回调函数"""
        self.parameter_callback = callback
    
    def set_message_callback(self, callback: Callable):
        """设置消息回调函数"""
        self.message_callback = callback
    
    def set_speech_recognition_callback(self, callback: Callable):
        """设置语音识别回调函数"""
        self.speech_recognition_callback = callback
    
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
    
    def _handle_position_update(self, address: str, *args):
        """处理位置更新"""
        if len(args) >= 3:
            x, y, z = args[0], args[1], args[2]
            self.player_position = {"x": float(x), "y": float(y), "z": float(z)}
            
            if self.debug_mode:
                print(f"[OSC调试] 位置更新: X={x:.2f}, Y={y:.2f}, Z={z:.2f}")
            
            if self.position_callback:
                self.position_callback(float(x), float(y), float(z))
    
    def _handle_rotation_update(self, address: str, *args):
        """处理旋转更新"""
        if self.debug_mode and args:
            print(f"[OSC调试] 旋转更新: {args}")
    
    def _handle_avatar_change(self, address: str, *args):
        """处理Avatar变更"""
        if self.debug_mode and args:
            print(f"[OSC调试] Avatar变更: {args}")
    
    def set_position_callback(self, callback: Callable):
        """设置位置变化回调函数"""
        self.position_callback = callback
    
    def get_player_position(self):
        """获取玩家当前位置"""
        return self.player_position.copy()
    
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
            "monitoring_parameters": self.voice_parameter_names,
            "connection_info": {
                "host": self.host,
                "send_port": self.send_port,
                "receive_port": self.receive_port,
                "server_running": self.is_running
            }
        }
    
    def get_vrchat_connection_diagnosis(self) -> dict:
        """获取VRChat连接诊断信息"""
        diagnosis = {
            "status": "unknown",
            "issues": [],
            "suggestions": []
        }
        
        if not self.is_running:
            diagnosis["status"] = "server_not_running"
            diagnosis["issues"].append("OSC服务器未运行")
            diagnosis["suggestions"].append("重新连接到VRChat")
            return diagnosis
        
        if not self.voice_parameters_received:
            diagnosis["status"] = "no_vrchat_data"
            diagnosis["issues"].append("未收到任何VRChat语音参数")
            diagnosis["suggestions"].extend([
                "检查VRChat设置 → OSC → 启用OSC",
                "确认VRChat正在运行",
                "检查端口是否被占用",
                "重启VRChat应用程序",
                "确认麦克风权限"
            ])
        elif not self.vrc_is_speaking and self.vrc_voice_level == 0:
            diagnosis["status"] = "receiving_data_but_no_voice"
            diagnosis["issues"].append("收到VRChat参数但无语音状态")
            diagnosis["suggestions"].extend([
                "在VRChat中说话测试",
                "检查VRChat麦克风设置",
                "调整语音激活阈值"
            ])
        else:
            diagnosis["status"] = "working"
            diagnosis["issues"] = []
            diagnosis["suggestions"] = ["VRChat OSC连接正常"]
        
        return diagnosis
    
    def _handle_audio_start(self, address: str, *args):
        """处理音频传输开始"""
        if len(args) >= 2:
            self.audio_total_chunks = int(args[0])
            self.audio_duration = float(args[1])
            self.audio_chunks = {}
            self.audio_receiving = True
            
            # 重置实时识别缓冲区
            self.audio_buffer = []
            self.last_recognition_time = 0
            
            print(f"开始接收音频数据，共{self.audio_total_chunks}块，时长{self.audio_duration:.2f}秒")
            print("实时语音识别已启动")
    
    def _handle_audio_chunk(self, address: str, *args):
        """处理音频数据块并进行实时识别"""
        if len(args) >= 2 and self.audio_receiving:
            chunk_index = int(args[0])
            chunk_data = str(args[1])
            self.audio_chunks[chunk_index] = chunk_data
            print(f"接收音频块 {chunk_index + 1}/{self.audio_total_chunks}")
            
            # 实时处理：尝试识别当前可用的音频数据
            self._process_audio_chunk_realtime(chunk_index, chunk_data)
    
    def _process_audio_chunk_realtime(self, chunk_index: int, chunk_data: str):
        """实时处理音频块，智能边界检测"""
        try:
            import base64
            import time
            import numpy as np
            import soundfile as sf
            import tempfile
            import os
            
            # 解码当前音频块
            chunk_bytes = base64.b64decode(chunk_data)
            
            # 将音频块添加到缓冲区
            self.audio_buffer.append(chunk_bytes)
            
            # 分析当前块的语音活动
            try:
                # 临时解码分析语音活动
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(chunk_bytes)
                    temp_path = temp_file.name
                
                audio_data, _ = sf.read(temp_path)
                rms_energy = np.sqrt(np.mean(audio_data ** 2))
                is_speech = rms_energy > self.silence_threshold
                
                # 更新语音活动历史
                self.speech_activity_history.append(is_speech)
                if len(self.speech_activity_history) > 10:  # 保留最近10个块的历史
                    self.speech_activity_history.pop(0)
                
                os.unlink(temp_path)
                
            except Exception:
                is_speech = True  # 出错时默认为语音
            
            # 检查是否应该进行识别
            current_time = time.time()
            buffer_duration = len(self.audio_buffer) * 0.1  # 估算时长
            
            should_recognize = False
            reason = ""
            
            # 条件1：时间间隔达到
            if (current_time - self.last_recognition_time) >= self.recognition_interval:
                should_recognize = True
                reason = "时间间隔"
            
            # 条件2：缓冲区达到大小限制
            elif len(self.audio_buffer) >= int(self.buffer_size_limit * 10):
                should_recognize = True
                reason = "缓冲区满"
            
            # 条件3：智能边界检测 - 检测到语音停顿
            elif (len(self.audio_buffer) >= self.min_recognition_chunks and 
                  len(self.speech_activity_history) >= 3):
                # 检查最近是否有语音停顿（静音）
                recent_activity = self.speech_activity_history[-3:]
                if not any(recent_activity):  # 最近3个块都是静音
                    should_recognize = True
                    reason = "语音停顿"
            
            # 确保有足够的音频数据
            if should_recognize and len(self.audio_buffer) >= self.min_recognition_chunks:
                self.last_recognition_time = current_time
                
                # 合并缓冲区中的音频数据
                combined_audio = b''.join(self.audio_buffer)
                
                # 创建临时文件进行识别
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(combined_audio)
                    temp_audio_path = temp_file.name
                
                print(f"实时识别触发: {reason}, 处理{len(self.audio_buffer)}个音频块 ({buffer_duration:.1f}秒)")
                
                # 异步进行语音识别，避免阻塞音频接收
                import threading
                recognition_thread = threading.Thread(
                    target=self._perform_realtime_recognition,
                    args=(temp_audio_path, reason),
                    daemon=True
                )
                recognition_thread.start()
                
                # 智能重叠保留：保留更多数据避免截断
                if reason == "语音停顿":
                    # 如果是因为停顿触发，保留较少数据
                    self.audio_buffer = self.audio_buffer[-2:]
                else:
                    # 其他情况保留更多重叠数据
                    self.audio_buffer = self.audio_buffer[-self.overlap_chunks:]
                
                # 清理语音活动历史
                self.speech_activity_history = self.speech_activity_history[-3:]
                
        except Exception as e:
            print(f"实时音频处理失败: {e}")
    
    def _perform_realtime_recognition(self, temp_audio_path: str, trigger_reason: str = ""):
        """执行实时语音识别"""
        try:
            import soundfile as sf
            import os
            
            # 读取音频数据
            audio_data, sample_rate = sf.read(temp_audio_path)
            
            # 调用语音识别回调
            if hasattr(self, 'speech_recognition_callback') and self.speech_recognition_callback:
                recognized_text = self.speech_recognition_callback(audio_data, sample_rate)
                if recognized_text and recognized_text.strip():
                    print(f"实时识别结果 ({trigger_reason}): {recognized_text}")
                    # 通知上层处理识别结果
                    if self.message_callback:
                        self.message_callback("speech_recognized_realtime", {
                            'text': recognized_text,
                            'trigger_reason': trigger_reason,
                            'audio_duration': len(audio_data) / sample_rate
                        })
                else:
                    print(f"实时识别无结果 ({trigger_reason})")
            
            # 清理临时文件
            try:
                os.unlink(temp_audio_path)
            except:
                pass
                
        except Exception as e:
            print(f"实时语音识别失败: {e}")
    
    def _handle_audio_end(self, address: str, *args):
        """处理音频传输结束并进行语音识别"""
        if not self.audio_receiving:
            return
        
        print("音频数据接收完成，开始重组并进行语音识别")
        
        try:
            # 重组音频数据
            complete_audio_data = ""
            for i in range(self.audio_total_chunks):
                if i in self.audio_chunks:
                    complete_audio_data += self.audio_chunks[i]
                else:
                    print(f"缺少音频块 {i}")
                    return
            
            # 解码音频数据
            import base64
            import tempfile
            import os
            import numpy as np
            import soundfile as sf
            
            audio_bytes = base64.b64decode(complete_audio_data)
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_audio_path = temp_file.name
            
            print(f"音频文件已保存到临时位置: {temp_audio_path}")
            
            # 进行语音识别
            print("开始语音识别...")
            try:
                # 读取音频数据进行识别
                audio_data, sample_rate = sf.read(temp_audio_path)
                
                # 调用语音识别回调（如果设置了）
                if hasattr(self, 'speech_recognition_callback') and self.speech_recognition_callback:
                    recognized_text = self.speech_recognition_callback(audio_data, sample_rate)
                    if recognized_text:
                        print(f"语音识别结果: {recognized_text}")
                        # 通知上层处理识别结果
                        if self.message_callback:
                            self.message_callback("speech_recognized", recognized_text)
                    else:
                        print("语音识别失败或未识别出内容")
                else:
                    print("未设置语音识别回调函数")
            except Exception as e:
                print(f"语音识别过程中出错: {e}")
            
            # 清理临时文件
            try:
                os.unlink(temp_audio_path)
                print("临时音频文件已清理")
            except:
                pass
            
        except Exception as e:
            print(f"处理接收到的音频数据失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 重置接收状态
            self.audio_receiving = False
            self.audio_chunks = {}
            self.audio_total_chunks = 0
    
    def _play_audio_to_virtual_microphone_for_vrc(self, temp_audio_path: str, duration: float) -> bool:
        """专门为VRC播放音频到虚拟麦克风设备"""
        try:
            # 优先使用sounddevice进行精确的音频设备控制
            try:
                import sounddevice as sd
                import soundfile as sf
                
                print("🔍 检测可用音频设备...")
                devices = sd.query_devices()
                virtual_device_id = None
                
                # 寻找VB-Audio Virtual Cable设备
                for i, device in enumerate(devices):
                    device_name = device['name']
                    print(f"   设备 {i:2d}: {device_name} ({'输出' if device['max_output_channels'] > 0 else '输入'})")
                    
                    # 寻找CABLE Input设备（这是我们要播放到的设备）
                    if device['max_output_channels'] > 0:  # 必须是输出设备
                        device_name_lower = device_name.lower()
                        if any(keyword in device_name_lower for keyword in [
                            'cable input', 'vb-audio virtual cable', 'voicemeeter input', 'vb-cable'
                        ]):
                            virtual_device_id = i
                            print(f"🎤 找到虚拟麦克风设备: {device_name} (ID: {i})")
                            break
                
                if virtual_device_id is not None:
                    # 读取音频文件
                    data, sample_rate = sf.read(temp_audio_path)
                    
                    print(f"📡 播放音频到虚拟麦克风设备 {virtual_device_id}")
                    print(f"   音频参数: {len(data)} samples, {sample_rate} Hz")
                    
                    # 播放音频并等待完成
                    sd.play(data, sample_rate, device=virtual_device_id)
                    sd.wait()  # 等待播放完成
                    
                    print("🎤 虚拟麦克风播放完成")
                    return True
                else:
                    print("⚠️  未找到合适的虚拟麦克风设备")
                    print("💡 需要安装VB-Audio Virtual Cable: https://vb-audio.com/Cable/")
                    return False
                    
            except ImportError:
                print("❌ sounddevice未安装")
                print("💡 请运行: pip install sounddevice soundfile")
                return False
            except Exception as e:
                print(f"❌ sounddevice播放失败: {e}")
                return False
                
        except Exception as e:
            print(f"❌ 虚拟麦克风播放完全失败: {e}")
            return False

    def _play_audio_to_virtual_microphone(self, temp_audio_path: str, duration: float) -> bool:
        """播放音频到虚拟麦克风设备 (AI端VRChat使用)"""
        try:
            # 方法1：尝试使用sounddevice播放到虚拟设备
            try:
                import sounddevice as sd
                import soundfile as sf
                
                # 读取音频文件
                data, sample_rate = sf.read(temp_audio_path)
                
                # 寻找虚拟麦克风设备
                devices = sd.query_devices()
                virtual_device_id = None
                
                for i, device in enumerate(devices):
                    device_name = device['name'].lower()
                    if any(keyword in device_name for keyword in [
                        'cable input', 'vb-audio', 'virtual audio', 
                        'voicemeeter input', 'microphone (vb-audio'
                    ]):
                        if device['max_output_channels'] > 0:
                            virtual_device_id = i
                            print(f"🎤 找到虚拟麦克风设备: {device['name']} (ID: {i})")
                            break
                
                if virtual_device_id is not None:
                    print(f"📡 播放音频到虚拟麦克风设备 {virtual_device_id}")
                    sd.play(data, sample_rate, device=virtual_device_id)
                    sd.wait()  # 等待播放完成
                    print("🎤 虚拟麦克风播放完成")
                    return True
                else:
                    print("⚠️  未找到虚拟麦克风设备")
                    return False
                    
            except ImportError:
                print("sounddevice未安装，尝试pygame方案")
                return self._play_audio_with_pygame(temp_audio_path)
            except Exception as e:
                print(f"sounddevice播放失败: {e}")
                return self._play_audio_with_pygame(temp_audio_path)
                
        except Exception as e:
            print(f"虚拟麦克风播放失败: {e}")
            return False
    
    def _play_audio_with_pygame(self, temp_audio_path: str) -> bool:
        """使用pygame播放音频 (备选方案)"""
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            
            # 等待前一个音频播放完成
            while pygame.mixer.music.get_busy():
                import time
                time.sleep(0.1)
            
            # 播放音频
            pygame.mixer.music.load(temp_audio_path)
            pygame.mixer.music.play()
            
            print("🔊 pygame音频播放完成 (备选方案)")
            return True
            
        except Exception as e:
            print(f"pygame播放失败: {e}")
            return False
    
    def _play_audio_to_system_output(self, temp_audio_path: str) -> bool:
        """播放音频到系统默认输出 (最后备选方案)"""
        try:
            import subprocess
            import platform
            system = platform.system()
            
            if system == "Windows":
                subprocess.Popen(['start', temp_audio_path], shell=True)
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', temp_audio_path])
            elif system == "Linux":
                subprocess.Popen(['xdg-open', temp_audio_path])
            
            print("🔊 系统默认播放器播放音频")
            return True
            
        except Exception as e:
            print(f"系统播放器失败: {e}")
            return False