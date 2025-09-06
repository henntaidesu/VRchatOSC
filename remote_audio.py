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
from typing import Dict, Any


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
        
        print(f"🎤 远程音频服务初始化，监听端口: {port}")
        
        # 检测音频设备
        self.detect_audio_devices()
    
    def detect_audio_devices(self):
        """检测可用音频设备"""
        try:
            import sounddevice as sd
            
            print("🔍 检测音频设备...")
            devices = sd.query_devices()
            self.audio_devices = []
            
            for i, device in enumerate(devices):
                if device['max_output_channels'] > 0:  # 输出设备
                    self.audio_devices.append({
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_output_channels'],
                        'sample_rate': device['default_samplerate']
                    })
                    
                    print(f"   设备 {i:2d}: {device['name']}")
                    
                    # 检查是否为虚拟麦克风设备
                    device_name_lower = device['name'].lower()
                    if any(keyword in device_name_lower for keyword in [
                        'cable input', 'vb-audio virtual cable', 'voicemeeter input', 
                        'vb-cable', 'virtual audio cable'
                    ]):
                        self.virtual_device_id = i
                        print(f"🎤 找到虚拟麦克风设备: {device['name']} (ID: {i})")
            
            if self.virtual_device_id is None:
                print("⚠️  未找到虚拟麦克风设备")
                print("💡 请安装 VB-Audio Virtual Cable: https://vb-audio.com/Cable/")
                print("🔊 将使用默认音频设备")
                
        except ImportError:
            print("❌ sounddevice未安装")
            print("💡 请运行: pip install sounddevice soundfile")
        except Exception as e:
            print(f"检测音频设备失败: {e}")
    
    def start_server(self):
        """启动音频服务"""
        if self.running:
            return
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('127.0.0.1', self.port))
            self.server_socket.listen(5)
            
            self.running = True
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            
            print(f"✅ 远程音频服务已启动，监听 127.0.0.1:{self.port}")
            
        except Exception as e:
            print(f"启动音频服务失败: {e}")
            self.running = False
    
    def stop_server(self):
        """停止音频服务"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("🛑 远程音频服务已停止")
    
    def _server_loop(self):
        """服务器主循环"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"📡 新的客户端连接: {address}")
                
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
        elif command == 'list_devices':
            return self._handle_list_devices(request)
        elif command == 'set_device':
            return self._handle_set_device(request)
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
            self.virtual_device_id = device_id
            return {"status": "success", "message": f"设备已设置为 {device_id}"}
        else:
            return {"status": "error", "message": "缺少device_id参数"}
    
    def _play_audio_to_virtual_microphone(self, temp_audio_path: str) -> bool:
        """播放音频到虚拟麦克风"""
        try:
            import sounddevice as sd
            import soundfile as sf
            
            # 读取音频文件
            data, sample_rate = sf.read(temp_audio_path)
            
            # 选择播放设备
            device_id = self.virtual_device_id
            if device_id is None:
                print("⚠️  使用默认音频设备")
            
            print(f"🎤 播放音频到设备 {device_id}")
            print(f"   音频参数: {len(data)} samples, {sample_rate} Hz")
            
            # 播放音频并等待完成
            sd.play(data, sample_rate, device=device_id)
            sd.wait()
            
            print("✅ 音频播放完成")
            return True
            
        except ImportError:
            print("❌ sounddevice未安装，无法播放音频")
            return False
        except Exception as e:
            print(f"播放音频失败: {e}")
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
    
    def play_audio_file(self, file_path: str) -> bool:
        """播放音频文件
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            # 读取音频文件
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            # 编码为base64
            audio_data_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 发送请求
            request = {
                "command": "play_audio",
                "audio_data": audio_data_b64
            }
            
            response = self._send_request(request)
            return response.get('status') == 'success'
            
        except Exception as e:
            print(f"播放音频文件失败: {e}")
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
        print("\n🛑 接收到退出信号")
        service.stop_server()


if __name__ == "__main__":
    main()