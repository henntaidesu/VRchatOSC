#!/usr/bin/env python3
"""
远程音频服务 - 独立的虚拟麦克风音频播放服务
通过9003端口接收音频播放请求，并输出到虚拟麦克风设备
"""

import socket
import threading
import json
import base64
import tempfile
import os
import time
import queue
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AudioQueueItem:
    """音频队列项目"""
    item_id: str              # 唯一ID
    audio_data: bytes         # 音频数据
    filename: str             # 文件名
    created_time: float       # 创建时间
    priority: int = 0         # 优先级(数字越小优先级越高)
    status: str = "pending"   # 状态: pending, processing, completed, error


class RemoteAudioService:
    """远程音频服务"""
    
    def __init__(self, port: int = 9003):
        """初始化远程音频服务
        
        Args:
            port: 监听端口，默认9003
        """
        self.port = port
        self.running = False
        self.server_socket = None
        self.server_thread = None
        
        # 虚拟麦克风设备
        self.virtual_device_id = None
        self.audio_devices = []
        
        # 音频队列系统 - 使用FIFO队列确保按发送顺序播放
        self.audio_queue = queue.Queue()  # 改为普通队列，确保先进先出
        self.queue_thread = None
        self.queue_processing = False
        self.current_item: Optional[AudioQueueItem] = None
        self.completed_items = []
        self.failed_items = []
        self.queue_counter = 0  # 用于生成唯一的序列号
        
        print(f"远程音频服务初始化，监听端口: {port}")
        
        # 检测音频设备
        self.detect_audio_devices()
    
    def detect_audio_devices(self):
        """检测可用音频设备"""
        try:
            import sounddevice as sd
            
            print("检测音频设备...")
            devices = sd.query_devices()
            self.audio_devices = []
            
            print("\n可用音频设备:")
            
            # 分别处理输入和输出设备
            virtual_cable_pairs = {}  # 用于匹配CABLE Input/Output对
            virtual_inputs = []
            output_devices = []
            cable_outputs = []
            
            for i, device in enumerate(devices):
                device_name = device['name']
                device_name_lower = device_name.lower()
                
                # 检查是否为虚拟音频设备
                is_virtual_audio = any(keyword in device_name_lower for keyword in [
                    'cable', 'vb-audio', 'voicemeeter', 'virtual audio', 'vb-cable', 'point'
                ])
                
                # 处理输出设备 (我们播放音频到这些设备)
                if device['max_output_channels'] > 0:
                    device_info = {
                        'id': i,
                        'name': device_name,
                        'channels': device['max_output_channels'],
                        'sample_rate': device['default_samplerate'],
                        'type': 'virtual_mic' if is_virtual_audio else 'speaker'
                    }
                    self.audio_devices.append(device_info)
                    
                    if is_virtual_audio:
                        virtual_inputs.append((i, device))
                        # 尝试匹配CABLE对
                        if 'cable input' in device_name_lower:
                            cable_name = device_name_lower.replace('cable input', 'cable output')
                            virtual_cable_pairs[i] = {'input': device, 'output_name': cable_name}
                        
                        print(f"   {i:2d}: {device_name} (播放目标 - {device['default_samplerate']:.0f} Hz)")
                    else:
                        output_devices.append((i, device))
                        print(f"   {i:2d}: {device_name} (扬声器 - {device['default_samplerate']:.0f} Hz)")
                
                # 处理输入设备 (显示CABLE Output，但不用于播放)
                elif device['max_input_channels'] > 0 and is_virtual_audio:
                    cable_outputs.append((i, device))
                    if 'cable output' in device_name_lower:
                        print(f"   {i:2d}: {device_name} (VRChat音频源 - {device['default_samplerate']:.0f} Hz)")
                    elif 'output' in device_name_lower and 'point' in device_name_lower:
                        print(f"   {i:2d}: {device_name} (VRChat音频源 - {device['default_samplerate']:.0f} Hz)")
            
            # 显示虚拟音频链路说明
            if virtual_inputs and cable_outputs:
                print(f"\n💡 虚拟音频链路说明:")
                print(f"   AI语音 → 🎤CABLE Input (ID {virtual_inputs[0][0]}) → 📥CABLE Output → VRChat麦克风")
            
            # 优先选择虚拟麦克风设备
            if virtual_inputs and self.virtual_device_id is None:
                self.virtual_device_id = virtual_inputs[0][0]
                print(f"        自动选择: {virtual_inputs[0][1]['name']} (ID: {self.virtual_device_id})")
            
            print(f"\n 设备总结:")
            print(f"   虚拟麦克风设备: {len(virtual_inputs)} 个")  
            print(f"   扬声器设备: {len(output_devices)} 个")
            
            if self.virtual_device_id is None:
                print("\n未找到虚拟麦克风设备")
                print(" VRChat需要虚拟麦克风来传输AI语音:")
                print("   1. 安装 VB-Audio Virtual Cable: https://vb-audio.com/Cable/")
                print("   2. 或使用设备选择功能手动指定合适的设备")
                print("   3. 在VRChat中设置麦克风为虚拟音频设备")
            else:
                selected_device = next((d for d in self.audio_devices if d['id'] == self.virtual_device_id), None)
                if selected_device:
                    device_type = "虚拟麦克风" if selected_device['type'] == 'virtual_mic' else "扬声器"
                    print(f"\n🎤 当前选中设备: {selected_device['name']} ({device_type}, ID: {self.virtual_device_id})")
            
            # 提供设备选择选项
            self.show_device_selection_prompt()
                
        except ImportError:
            print("❌ sounddevice未安装")
            print("💡 请运行: pip install sounddevice soundfile scipy")
        except Exception as e:
            print(f"检测音频设备失败: {e}")
    
    def show_device_selection_prompt(self):
        """显示设备选择提示"""
        print("\n" + "=" * 60)
        print("音频设备选择")
        print("=" * 60)
        print("如果自动选择的设备有问题，可以手动选择其他设备：")
        print(f"   当前设备ID: {self.virtual_device_id}")
        print("   选择方法:")
        print("   1. 通过客户端发送 set_device 命令")
        print("   2. 重启服务时手动输入设备ID")
        print("   3. 使用 GUI 界面选择")
        
        # 询问是否要手动选择设备
        try:
            print(f"\n是否要手动选择音频设备? (输入设备ID或按回车使用当前设备)")
            print(f"   当前: {self.virtual_device_id} - {self.get_device_name(self.virtual_device_id)}")
            
            user_input = input("请输入设备ID (或按回车跳过): ").strip()
            
            if user_input:
                try:
                    new_device_id = int(user_input)
                    if self.is_valid_device_id(new_device_id):
                        self.virtual_device_id = new_device_id
                        device_name = self.get_device_name(new_device_id)
                        print(f"已选择设备: {device_name} (ID: {new_device_id})")
                    else:
                        print(f"无效的设备ID: {new_device_id}")
                except ValueError:
                    print("请输入有效的数字")
            else:
                print("使用当前设备")
                
        except (KeyboardInterrupt, EOFError):
            print("\n跳过设备选择")
        
        print("=" * 60)
    
    def get_device_name(self, device_id):
        """获取设备名称"""
        if device_id is None:
            return "默认设备"
        
        for device in self.audio_devices:
            if device['id'] == device_id:
                return device['name']
        return f"未知设备 (ID: {device_id})"
    
    def is_valid_device_id(self, device_id):
        """检查设备ID是否有效"""
        return any(device['id'] == device_id for device in self.audio_devices)
    
    def start_server(self):
        """启动音频服务"""
        if self.running:
            return
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 绑定到所有接口，允许远程连接
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            
            self.running = True
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            
            # 启动音频队列处理
            self.start_queue_processing()
            
            print(f"   远程音频服务已启动，监听所有接口:{self.port}")
            print(f"   本地访问: 127.0.0.1:{self.port}")
            print(f"   远程访问: <本机IP>:{self.port}")
            print(f"   音频队列处理已启动")
            
        except Exception as e:
            print(f"启动音频服务失败: {e}")
            self.running = False
    
    def stop_server(self):
        """停止音频服务"""
        self.running = False
        self.stop_queue_processing()
        if self.server_socket:
            self.server_socket.close()
        print("远程音频服务已停止")
    
    def start_queue_processing(self):
        """启动音频队列处理"""
        if self.queue_processing:
            return
        
        self.queue_processing = True
        self.queue_thread = threading.Thread(target=self._queue_processing_loop, daemon=True)
        self.queue_thread.start()
        print("音频队列处理已启动")
    
    def stop_queue_processing(self):
        """停止音频队列处理"""
        self.queue_processing = False
        if self.queue_thread:
            self.queue_thread.join(timeout=5)
        print("音频队列处理已停止")
    
    def _queue_processing_loop(self):
        """音频队列处理主循环"""
        print("音频队列处理主循环已启动")
        while self.queue_processing:
            try:
                # 从FIFO队列获取项目，确保按发送顺序播放
                try:
                    item = self.audio_queue.get(timeout=1)
                    print(f"从队列获取音频项目: {item.item_id} ({item.filename})")
                except queue.Empty:
                    continue
                
                self.current_item = item
                item.status = "processing"
                
                print(f"开始播放音频: {item.filename}")
                
                # 播放音频
                success = self._play_queued_audio(item)
                
                # 更新状态
                if success:
                    item.status = "completed"
                    self.completed_items.append(item)
                    print(f"音频播放完成: {item.filename}")
                else:
                    item.status = "error"
                    self.failed_items.append(item)
                    print(f"音频播放失败: {item.filename}")
                
                self.current_item = None
                self.audio_queue.task_done()
                
                # 处理完成后稍等，避免过于频繁
                time.sleep(0.1)
                
            except Exception as e:
                print(f"音频队列处理错误: {e}")
                if self.current_item:
                    self.current_item.status = "error"
                    self.failed_items.append(self.current_item)
                    self.current_item = None
                time.sleep(1)
    
    def add_audio_to_queue(self, audio_data: bytes, filename: str = "audio.wav", priority: int = 0) -> str:
        """添加音频到队列
        
        Args:
            audio_data: 音频数据
            filename: 文件名
            priority: 优先级(保留参数，但使用FIFO队列)
            
        Returns:
            str: 音频项目ID
        """
        self.queue_counter += 1
        item_id = f"audio_{self.queue_counter}_{int(time.time() * 1000)}"
        
        item = AudioQueueItem(
            item_id=item_id,
            audio_data=audio_data,
            filename=filename,
            created_time=time.time(),
            priority=priority
        )
        
        # 直接添加到FIFO队列，确保按发送顺序播放
        self.audio_queue.put(item)
        
        print(f"音频已添加到播放队列: {filename} (序号: {self.queue_counter}, ID: {item_id})")
        return item_id
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "queue_size": self.audio_queue.qsize(),
            "is_processing": self.queue_processing,
            "current_item": self.current_item.filename if self.current_item else None,
            "completed_count": len(self.completed_items),
            "failed_count": len(self.failed_items)
        }
    
    def _play_queued_audio(self, item: AudioQueueItem) -> bool:
        """播放队列中的音频"""
        try:
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(item.audio_data)
                temp_audio_path = temp_file.name
            
            print(f"临时音频文件: {temp_audio_path}")
            
            # 播放音频
            success = self._play_audio_to_virtual_microphone(temp_audio_path)
            
            # 清理临时文件
            try:
                os.unlink(temp_audio_path)
            except:
                pass
            
            return success
            
        except Exception as e:
            print(f"播放队列音频失败: {e}")
            return False
    
    def _server_loop(self):
        """服务器主循环"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"新的客户端连接: {address}")
                
                # 在新线程中处理客户端
                client_thread = threading.Thread(
                    target=self._handle_client, 
                    args=(client_socket,), 
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:  # 只有在服务运行时才报错
                    print(f"服务器循环错误: {e}")
    
    def _handle_client(self, client_socket):
        """处理客户端请求"""
        try:
            # 接收数据
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                
                # 检查是否接收完整的JSON消息
                try:
                    message = json.loads(data.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    continue  # 继续接收数据
            
            if not data:
                return
            
            # 解析请求
            request = json.loads(data.decode('utf-8'))
            response = self._process_request(request)
            
            # 发送响应
            response_json = json.dumps(response, ensure_ascii=False).encode('utf-8')
            client_socket.send(response_json)
            
        except Exception as e:
            print(f"处理客户端请求错误: {e}")
            error_response = {
                "status": "error",
                "message": str(e)
            }
            try:
                response_json = json.dumps(error_response).encode('utf-8')
                client_socket.send(response_json)
            except:
                pass
        finally:
            client_socket.close()
    
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理音频请求"""
        command = request.get('command')
        
        if command == 'play_audio':
            return self._handle_play_audio(request)
        elif command == 'play_audio_queued':
            return self._handle_play_audio_queued(request)
        elif command == 'list_devices':
            return self._handle_list_devices(request)
        elif command == 'set_device':
            return self._handle_set_device(request)
        elif command == 'queue_status':
            return self._handle_queue_status(request)
        elif command == 'ping':
            return {"status": "success", "message": "pong"}
        else:
            return {"status": "error", "message": f"未知命令: {command}"}
    
    def _handle_play_audio(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理播放音频请求"""
        try:
            # 获取音频数据
            audio_data_b64 = request.get('audio_data')
            if not audio_data_b64:
                return {"status": "error", "message": "缺少音频数据"}
            
            # 解码音频数据
            audio_data = base64.b64decode(audio_data_b64)
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_audio_path = temp_file.name
            
            print(f"📥 接收到音频数据，文件大小: {len(audio_data)} bytes")
            
            # 播放音频
            success = self._play_audio_to_virtual_microphone(temp_audio_path)
            
            # 清理临时文件
            try:
                os.unlink(temp_audio_path)
            except:
                pass
            
            if success:
                return {
                    "status": "success", 
                    "message": "音频播放成功",
                    "device_id": self.virtual_device_id
                }
            else:
                return {"status": "error", "message": "音频播放失败"}
                
        except Exception as e:
            print(f"播放音频错误: {e}")
            return {"status": "error", "message": str(e)}
    
    def _handle_play_audio_queued(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理队列音频播放请求"""
        try:
            # 获取音频数据
            audio_data_b64 = request.get('audio_data')
            if not audio_data_b64:
                return {"status": "error", "message": "缺少音频数据"}
            
            # 解码音频数据
            audio_data = base64.b64decode(audio_data_b64)
            
            # 获取文件名和优先级
            filename = request.get('filename', 'audio.wav')
            priority = request.get('priority', 0)
            
            print(f"接收到队列音频数据: {filename}, 大小: {len(audio_data)} bytes, 优先级: {priority}")
            
            # 添加到队列
            item_id = self.add_audio_to_queue(audio_data, filename, priority)
            
            return {
                "status": "success",
                "message": "音频已添加到队列",
                "item_id": item_id,
                "queue_size": self.audio_queue.qsize(),
                "device_id": self.virtual_device_id
            }
            
        except Exception as e:
            print(f"队列音频播放错误: {e}")
            return {"status": "error", "message": str(e)}
    
    def _handle_queue_status(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理队列状态查询请求"""
        try:
            status = self.get_queue_status()
            return {
                "status": "success",
                "queue_status": status
            }
        except Exception as e:
            print(f"获取队列状态错误: {e}")
            return {"status": "error", "message": str(e)}
    
    def _handle_list_devices(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理设备列表请求"""
        return {
            "status": "success",
            "devices": self.audio_devices,
            "current_device": self.virtual_device_id
        }
    
    def _handle_set_device(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理设备设置请求"""
        device_id = request.get('device_id')
        if device_id is not None:
            if self.is_valid_device_id(device_id):
                old_device_name = self.get_device_name(self.virtual_device_id)
                self.virtual_device_id = device_id
                new_device_name = self.get_device_name(device_id)
                
                print(f"设备已更改: {old_device_name} -> {new_device_name} (ID: {device_id})")
                
                return {
                    "status": "success", 
                    "message": f"设备已设置为 {new_device_name} (ID: {device_id})",
                    "device_id": device_id,
                    "device_name": new_device_name
                }
            else:
                return {"status": "error", "message": f"无效的设备ID: {device_id}"}
        else:
            return {"status": "error", "message": "缺少device_id参数"}
    
    def _play_audio_to_virtual_microphone(self, temp_audio_path: str) -> bool:
        """播放音频到虚拟麦克风"""
        try:
            print(f"开始播放音频文件: {temp_audio_path}")
            
            # 检查文件是否存在
            import os
            if not os.path.exists(temp_audio_path):
                print(f"音频文件不存在: {temp_audio_path}")
                return False
            
            file_size = os.path.getsize(temp_audio_path)
            print(f"音频文件大小: {file_size} bytes")
            
            import sounddevice as sd
            import soundfile as sf
            import numpy as np
            
            # 检查soundfile是否能读取文件
            try:
                data, sample_rate = sf.read(temp_audio_path)
                print(f"音频参数: {len(data)} samples, {sample_rate} Hz, 时长: {len(data)/sample_rate:.2f}秒")
            except Exception as e:
                print(f"读取音频文件失败: {e}")
                return False
            
            # 检查音频设备列表和支持的采样率
            print("当前可用音频设备:")
            try:
                devices = sd.query_devices()
                target_device_info = None
                
                for i, device in enumerate(devices):
                    if device['max_output_channels'] > 0:
                        is_target = '✓' if i == self.virtual_device_id else ' '
                        print(f"   {i:2d}: {device['name']} ({is_target}) 默认采样率: {device['default_samplerate']}")
                        
                        # 获取目标设备信息
                        if i == self.virtual_device_id:
                            target_device_info = device
                            
            except Exception as e:
                print(f"查询音频设备失败: {e}")
                return False
            
            # 选择播放设备
            device_id = self.virtual_device_id
            if device_id is None:
                print("未找到虚拟麦克风，使用默认音频设备")
                target_sample_rate = 44100  # 默认采样率
            else:
                print(f"使用虚拟麦克风设备 {device_id}")
                target_sample_rate = int(target_device_info['default_samplerate']) if target_device_info else 44100
            
            # 检查采样率兼容性
            if sample_rate != target_sample_rate:
                print(f"接收到的音频采样率 {sample_rate} Hz 与目标设备 {target_sample_rate} Hz 不匹配")
                print(f"建议在发送端预处理音频为 {target_sample_rate} Hz")
                # 继续使用原始采样率播放，让设备自己处理
                print(f"尝试使用原始采样率 {sample_rate} Hz 播放...")
            
            # 播放音频并等待完成
            try:
                print(f"开始播放音频 (采样率: {sample_rate} Hz)...")
                sd.play(data, sample_rate, device=device_id)
                sd.wait()  # 等待播放完成
                print("音频播放完成")
                return True
            except Exception as e:
                print(f"   音频播放失败: {e}")
                print(f"   设备ID: {device_id}")
                print(f"   采样率: {sample_rate}")
                print(f"   数据长度: {len(data)}")
                
                # 如果指定设备播放失败，尝试使用默认设备
                if device_id is not None:
                    print("尝试使用默认音频设备播放...")
                    try:
                        sd.play(data, sample_rate)
                        sd.wait()
                        print("默认设备播放成功")
                        return True
                    except Exception as e2:
                        print(f"默认设备也播放失败: {e2}")
                
                return False
            
        except ImportError as e:
            print(f" 导入模块失败: {e}")
            print("请运行: pip install sounddevice soundfile scipy")
            return False
        except Exception as e:
            print(f"播放音频时发生未知错误: {e}")
            import traceback
            traceback.print_exc()
            return False


class RemoteAudioClient:
    """远程音频客户端"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9003):
        """初始化客户端
        
        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self.host = host
        self.port = port
    
    def play_audio_file(self, file_path: str, use_queue: bool = True, priority: int = 0) -> bool:
        """播放音频文件
        
        Args:
            file_path: 音频文件路径
            use_queue: 是否使用队列播放（默认True）
            priority: 优先级（数字越小优先级越高）
            
        Returns:
            bool: 是否成功
        """
        try:
            print(f"客户端：准备发送音频文件 {file_path}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"客户端：音频文件不存在 {file_path}")
                return False
            
            # 读取音频文件
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            print(f"客户端：音频文件大小 {len(audio_data)} bytes")
            
            # 编码为base64
            audio_data_b64 = base64.b64encode(audio_data).decode('utf-8')
            print(f"客户端：base64编码后大小 {len(audio_data_b64)} chars")
            
            # 发送请求
            if use_queue:
                # 使用队列播放
                request = {
                    "command": "play_audio_queued",
                    "audio_data": audio_data_b64,
                    "filename": os.path.basename(file_path),
                    "priority": priority
                }
                print(f"客户端：发送队列播放请求到远程服务器... (优先级: {priority})")
            else:
                # 直接播放
                request = {
                    "command": "play_audio",
                    "audio_data": audio_data_b64
                }
                print("客户端：发送直接播放请求到远程服务器...")
            
            response = self._send_request(request)
            
            if response.get('status') == 'success':
                if use_queue:
                    item_id = response.get('item_id', 'unknown')
                    queue_size = response.get('queue_size', 0)
                    print(f"客户端：音频已添加到队列 (ID: {item_id}, 队列长度: {queue_size})")
                else:
                    print("客户端：远程音频播放成功")
                return True
            else:
                error_msg = response.get('message', '未知错误')
                print(f" 客户端：远程音频播放失败 - {error_msg}")
                return False
            
        except Exception as e:
            print(f" 客户端：播放音频文件失败 - {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def ping(self) -> bool:
        """测试连接"""
        try:
            request = {"command": "ping"}
            response = self._send_request(request)
            return response.get('status') == 'success'
        except:
            return False
    
    def list_devices(self) -> list:
        """获取设备列表"""
        try:
            request = {"command": "list_devices"}
            response = self._send_request(request)
            if response.get('status') == 'success':
                return response.get('devices', [])
            return []
        except:
            return []
    
    def set_device(self, device_id: int) -> bool:
        """设置音频设备"""
        try:
            request = {"command": "set_device", "device_id": device_id}
            response = self._send_request(request)
            if response.get('status') == 'success':
                print(f"设备已设置: {response.get('device_name', f'ID {device_id}')}")
                return True
            else:
                print(f" 设置设备失败: {response.get('message', '未知错误')}")
                return False
        except Exception as e:
            print(f" 设置设备时出错: {e}")
            return False
    
    def get_queue_status(self) -> dict:
        """获取音频队列状态"""
        try:
            request = {"command": "queue_status"}
            response = self._send_request(request)
            if response.get('status') == 'success':
                return response.get('queue_status', {})
            else:
                print(f" 获取队列状态失败: {response.get('message', '未知错误')}")
                return {}
        except Exception as e:
            print(f" 获取队列状态时出错: {e}")
            return {}
    
    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """发送请求到服务器"""
        try:
            # 连接服务器
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.host, self.port))
            
            # 发送请求
            request_json = json.dumps(request, ensure_ascii=False).encode('utf-8')
            client_socket.send(request_json)
            
            # 接收响应
            response_data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                # 尝试解析JSON
                try:
                    response = json.loads(response_data.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    continue
            
            client_socket.close()
            return response
            
        except Exception as e:
            print(f"发送请求失败: {e}")
            return {"status": "error", "message": str(e)}


def main():
    """主函数 - 启动远程音频服务"""
    print("🎤 远程音频服务启动中...")
    
    service = RemoteAudioService(port=9003)
    service.start_server()
    
    try:
        print("按 Ctrl+C 退出服务")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n接收到退出信号")
        service.stop_server()


if __name__ == "__main__":
    main()