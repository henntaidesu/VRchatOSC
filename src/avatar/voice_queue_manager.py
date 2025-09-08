#!/usr/bin/env python3
"""
语音队列管理器 - 管理VOICEVOX生成的语音按顺序输出
"""

import threading
import time
import queue
import os
import tempfile
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from enum import Enum


class VoiceItemType(Enum):
    """语音项目类型"""
    VOICEVOX = "voicevox"    # VOICEVOX生成的语音
    FILE = "file"            # 语音文件


@dataclass
class VoiceQueueItem:
    """语音队列项目"""
    item_id: str              # 唯一ID
    item_type: VoiceItemType  # 项目类型
    text: str                 # 文本内容
    file_path: str            # 语音文件路径
    character_name: str       # AI角色名称
    created_time: float       # 创建时间
    emotion: str = "neutral"  # 情感类型
    speaker_id: int = 0       # VOICEVOX说话人ID
    status: str = "pending"   # 状态: pending, processing, completed, error


class VoiceQueueManager:
    """语音队列管理器"""
    
    def __init__(self, voicevox_client=None, ai_manager=None):
        """初始化语音队列管理器
        
        Args:
            voicevox_client: VOICEVOX客户端
            ai_manager: AI角色管理器
        """
        self.voicevox_client = voicevox_client
        self.ai_manager = ai_manager
        
        # 语音队列
        self.voice_queue = queue.Queue()
        self.processing_thread = None
        self.is_processing = False
        
        # 状态跟踪
        self.current_item: Optional[VoiceQueueItem] = None
        self.completed_items: List[VoiceQueueItem] = []
        self.failed_items: List[VoiceQueueItem] = []
        
        # 回调函数
        self.status_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        
        # 临时文件管理
        self.temp_dir = tempfile.mkdtemp(prefix="vrc_voice_")
        
        print(f"语音队列管理器初始化完成，临时目录: {self.temp_dir}")
    
    def start_processing(self):
        """开始处理语音队列"""
        if self.is_processing:
            return
        
        self.is_processing = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        print("语音队列处理已启动")
    
    def stop_processing(self):
        """停止处理语音队列"""
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        print("语音队列处理已停止")
    
    def add_voicevox_item(self, text: str, character_name: str, 
                         speaker_id: int = 0, emotion: str = "neutral") -> str:
        """添加VOICEVOX语音项目到队列
        
        Args:
            text: 要合成的文本
            character_name: AI角色名称
            speaker_id: VOICEVOX说话人ID
            emotion: 情感类型
            
        Returns:
            str: 项目ID
        """
        item_id = f"vox_{int(time.time() * 1000)}_{len(text)}"
        
        item = VoiceQueueItem(
            item_id=item_id,
            item_type=VoiceItemType.VOICEVOX,
            text=text,
            file_path="",  # 将在处理时生成
            character_name=character_name,
            created_time=time.time(),
            emotion=emotion,
            speaker_id=speaker_id
        )
        
        self.voice_queue.put(item)
        print(f"添加VOICEVOX语音到队列: {text[:30]}... (角色: {character_name})")
        
        if self.status_callback:
            self.status_callback("item_added", item)
        
        return item_id
    
    def add_voice_file(self, file_path: str, character_name: str, 
                      text: str = "", emotion: str = "neutral") -> str:
        """添加语音文件项目到队列
        
        Args:
            file_path: 语音文件路径
            character_name: AI角色名称
            text: 描述文本
            emotion: 情感类型
            
        Returns:
            str: 项目ID
        """
        item_id = f"file_{int(time.time() * 1000)}_{os.path.basename(file_path)}"
        
        item = VoiceQueueItem(
            item_id=item_id,
            item_type=VoiceItemType.FILE,
            text=text or os.path.basename(file_path),
            file_path=file_path,
            character_name=character_name,
            created_time=time.time(),
            emotion=emotion
        )
        
        self.voice_queue.put(item)
        print(f"添加语音文件到队列: {file_path} (角色: {character_name})")
        
        if self.status_callback:
            self.status_callback("item_added", item)
        
        return item_id
    
    def _processing_loop(self):
        """语音队列处理主循环"""
        print("语音队列处理主循环已启动")
        while self.is_processing:
            try:
                # 从队列获取项目（超时1秒）
                try:
                    item = self.voice_queue.get(timeout=1)
                    print(f"从队列获取到项目: {item.item_id}")
                except queue.Empty:
                    continue
                
                self.current_item = item
                item.status = "processing"
                
                if self.status_callback:
                    self.status_callback("processing", item)
                
                print(f"开始处理语音项目: {item.item_id} ({item.text[:30]}...)")
                
                # 根据类型处理项目
                success = False
                if item.item_type == VoiceItemType.VOICEVOX:
                    print(f"处理VOICEVOX语音项目: {item.item_id}")
                    success = self._process_voicevox_item(item)
                elif item.item_type == VoiceItemType.FILE:
                    print(f"处理语音文件项目: {item.item_id}")
                    success = self._process_file_item(item)
                
                # 更新状态
                if success:
                    item.status = "completed"
                    self.completed_items.append(item)
                    print(f"语音项目处理成功: {item.item_id}")
                    
                    if self.completion_callback:
                        self.completion_callback(item)
                else:
                    item.status = "error"
                    self.failed_items.append(item)
                    print(f"语音项目处理失败: {item.item_id}")
                
                if self.status_callback:
                    self.status_callback("completed" if success else "error", item)
                
                self.current_item = None
                self.voice_queue.task_done()
                
                # 处理完成后稍等，避免过于频繁
                time.sleep(0.5)
                
            except Exception as e:
                print(f"语音队列处理错误: {e}")
                if self.current_item:
                    self.current_item.status = "error"
                    self.failed_items.append(self.current_item)
                    if self.status_callback:
                        self.status_callback("error", self.current_item)
                    self.current_item = None
                time.sleep(1)
    
    def _process_voicevox_item(self, item: VoiceQueueItem) -> bool:
        """处理VOICEVOX语音项目"""
        print(f"开始处理VOICEVOX项目: {item.item_id}")
        
        if not self.voicevox_client:
            print("VOICEVOX客户端未连接")
            return False
        
        try:
            # 生成临时文件路径
            temp_file = os.path.join(self.temp_dir, f"{item.item_id}.wav")
            print(f"临时文件路径: {temp_file}")
            
            # 设置说话人ID
            if item.speaker_id > 0:
                self.voicevox_client.set_speaker(item.speaker_id)
                print(f"设置说话人ID: {item.speaker_id}")
            
            # 使用VOICEVOX合成语音并保存到文件
            print(f"开始合成语音: {item.text[:50]}...")
            success = self.voicevox_client.save_audio(
                text=item.text,
                output_path=temp_file
            )
            
            if not success or not os.path.exists(temp_file):
                print(f"VOICEVOX语音合成失败: {item.text}")
                return False
            
            print(f"语音文件生成成功: {temp_file}")
            item.file_path = temp_file
            
            # 发送到AI角色的VRC
            print(f"准备发送语音到VRC角色: {item.character_name}")
            result = self._send_voice_to_character(item)
            print(f"发送到VRC结果: {result}")
            return result
            
        except Exception as e:
            print(f"处理VOICEVOX项目时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _process_file_item(self, item: VoiceQueueItem) -> bool:
        """处理语音文件项目"""
        try:
            if not os.path.exists(item.file_path):
                print(f"语音文件不存在: {item.file_path}")
                return False
            
            # 发送到AI角色的VRC
            return self._send_voice_to_character(item)
            
        except Exception as e:
            print(f"处理语音文件项目时出错: {e}")
            return False
    
    def _send_voice_to_character(self, item: VoiceQueueItem) -> bool:
        """将语音发送到指定AI角色的VRC实例"""
        print(f"尝试发送语音到角色: {item.character_name}")
        
        if not self.ai_manager:
            print("AI管理器未设置")
            return False
        
        try:
            # 检查AI管理器类型，支持SingleAIVRCManager
            osc_client = None
            avatar_controller = None
            
            # 处理SingleAIVRCManager类型
            if hasattr(self.ai_manager, 'vrc_controller') and self.ai_manager.vrc_controller:
                osc_client = self.ai_manager.vrc_controller.osc_client
                # 尝试从AI角色获取avatar_controller
                if hasattr(self.ai_manager, 'ai_character') and self.ai_manager.ai_character:
                    avatar_controller = getattr(self.ai_manager.ai_character, 'avatar_controller', None)
                else:
                    avatar_controller = None
                print(f"找到SingleAI VRC控制器的OSC客户端: {osc_client}")
                print(f"AI角色Avatar控制器: {avatar_controller}")
            
            # 处理传统的多AI管理器类型
            elif hasattr(self.ai_manager, 'osc_clients'):
                print(f"获取OSC客户端列表: {list(self.ai_manager.osc_clients.keys())}")
                osc_client = self.ai_manager.osc_clients.get(item.character_name)
                avatar_controller = self.ai_manager.avatar_controllers.get(item.character_name)
            
            if not osc_client:
                print(f"未找到AI角色 '{item.character_name}' 的OSC客户端")
                if hasattr(self.ai_manager, 'osc_clients'):
                    print(f"可用的OSC客户端: {list(self.ai_manager.osc_clients.keys())}")
                return False
            
            print(f"找到OSC客户端: {osc_client}")
            
            # 设置Avatar表情（基于emotion）
            if avatar_controller:
                print(f"设置Avatar表情: {item.emotion}")
                if hasattr(avatar_controller, 'start_speaking'):
                    avatar_controller.start_speaking(item.text, item.emotion, voice_level=0.8)
                else:
                    print("Avatar控制器不支持start_speaking方法")
            else:
                print("未找到Avatar控制器")
            
            # 发送语音文件到VRChat
            print(f"开始发送语音文件到VRChat: {item.file_path}")
            success = self._upload_voice_to_vrc(osc_client, item.file_path)
            print(f"语音文件发送结果: {success}")
            
            if success:
                print(f"语音已发送到VRChat角色: {item.character_name}")
                
                # 语音播放完成后停止说话状态
                if avatar_controller:
                    # 估算播放时长
                    duration = self._estimate_audio_duration(item.file_path)
                    print(f"预计播放时长: {duration}秒")
                    if hasattr(avatar_controller, 'stop_speaking'):
                        threading.Timer(duration, lambda: avatar_controller.stop_speaking()).start()
                    else:
                        print("Avatar控制器不支持stop_speaking方法")
            
            return success
            
        except Exception as e:
            print(f"发送语音到角色时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _upload_voice_to_vrc(self, osc_client, file_path: str) -> bool:
        """播放音频到本地VRChat麦克风（无需OSC音频传输）"""
        try:
            import os
            
            if not os.path.exists(file_path):
                print(f"语音文件不存在: {file_path}")
                return False
            
            print(f"准备播放音频到VRC虚拟麦克风: {file_path}")
            
            # 方案1: 尝试使用9003端口的远程音频服务
            success = self._use_remote_audio_service(file_path)
            if success:
                print("通过远程音频服务播放成功")
                return True
            
            # 方案2: 回退到OSC音频传输（如果远程音频服务不可用）
            print("远程音频服务不可用，使用OSC音频传输")
            return self._use_osc_audio_transmission(osc_client, file_path)
            
        except Exception as e:
            print(f"播放音频失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _play_to_virtual_microphone(self, file_path: str, duration: float) -> bool:
        """播放音频到虚拟麦克风设备"""
        try:
            # 使用专门的虚拟麦克风模块
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            from ..audio.virtual_microphone import virtual_microphone
            
            print(f"开始播放到虚拟麦克风: {file_path}")
            success = virtual_microphone.play_audio_with_mic_simulation(file_path)
            
            if success:
                print(f"✅ 虚拟麦克风播放成功，时长{duration:.2f}秒")
            else:
                print("❌ 虚拟麦克风播放失败")
            
            return success
            
        except Exception as e:
            print(f"虚拟麦克风播放失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _play_audio_to_system(self, file_path: str) -> bool:
        """播放音频到系统默认输出"""
        try:
            import pygame
            
            # 初始化pygame mixer
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            
            # 等待前一个音频播放完成
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # 播放音频
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            return True
            
        except Exception as e:
            print(f"系统音频播放失败: {e}")
            return False
    
    def _use_remote_audio_service(self, file_path: str) -> bool:
        """使用9003端口的远程音频服务（连接AI端IP）"""
        try:
            # 导入远程音频客户端
            import sys
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.path.append(project_root)
            
            from remote_audio import RemoteAudioClient
            
            # 获取AI端IP地址（从ai_manager获取）
            ai_host = self._get_ai_host_address()
            if not ai_host:
                print("❌ 无法获取AI端IP地址")
                return False
            
            print(f"🔌 尝试连接远程音频服务: {ai_host}:9003")
            
            # 连接远程AI端的音频服务
            client = RemoteAudioClient(host=ai_host, port=9003)
            
            # 测试连接
            if not client.ping():
                print(f"❌ 无法连接到远程音频服务 ({ai_host}:9003)")
                print("💡 请在AI端机器上运行: python remote_audio.py")
                return False
            
            print(f"✅ 成功连接到远程音频服务 ({ai_host}:9003)")
            
            # 预处理音频文件 - 转换为44100Hz
            processed_file = self._preprocess_audio_for_vrc(file_path)
            if not processed_file:
                print("❌ 音频预处理失败")
                return False
            
            # 播放预处理后的音频文件
            success = client.play_audio_file(processed_file)
            
            # 清理临时文件
            if processed_file != file_path:
                try:
                    os.unlink(processed_file)
                except:
                    pass
            
            if success:
                print("🎤 远程音频服务播放完成")
                return True
            else:
                print("❌ 远程音频服务播放失败")
                return False
                
        except Exception as e:
            print(f"远程音频服务调用失败: {e}")
            return False
    
    def _preprocess_audio_for_vrc(self, file_path: str, target_sample_rate: int = 44100) -> str:
        """预处理音频文件用于VRChat传输
        
        Args:
            file_path: 原始音频文件路径
            target_sample_rate: 目标采样率，默认44100Hz
            
        Returns:
            str: 处理后的音频文件路径，失败返回None
        """
        try:
            import soundfile as sf
            import numpy as np
            import tempfile
            
            print(f"🔄 预处理音频文件: {os.path.basename(file_path)}")
            
            # 读取原始音频
            data, original_sample_rate = sf.read(file_path)
            duration = len(data) / original_sample_rate
            
            print(f"   原始: {original_sample_rate} Hz, {duration:.1f}秒, {len(data)} samples")
            
            # 检查是否需要转换采样率
            if original_sample_rate == target_sample_rate:
                print(f"   ✅ 采样率已是 {target_sample_rate} Hz，无需转换")
                return file_path
            
            # 进行采样率转换
            print(f"   🔄 采样率转换: {original_sample_rate} → {target_sample_rate} Hz")
            
            try:
                # 优先使用scipy的高质量重采样
                from scipy.signal import resample
                new_sample_count = int(len(data) * target_sample_rate / original_sample_rate)
                resampled_data = resample(data, new_sample_count)
                print(f"   ✅ scipy重采样完成: {len(resampled_data)} samples")
                
            except ImportError:
                # 回退到线性插值
                print("   ⚠️ scipy未安装，使用线性插值重采样")
                ratio = target_sample_rate / original_sample_rate
                new_length = int(len(data) * ratio)
                
                # 处理单声道和立体声
                if data.ndim == 1:
                    # 单声道
                    resampled_data = np.interp(
                        np.linspace(0, len(data) - 1, new_length),
                        np.arange(len(data)),
                        data
                    )
                else:
                    # 立体声或多声道
                    resampled_data = np.zeros((new_length, data.shape[1]))
                    for channel in range(data.shape[1]):
                        resampled_data[:, channel] = np.interp(
                            np.linspace(0, len(data) - 1, new_length),
                            np.arange(len(data)),
                            data[:, channel]
                        )
                
                print(f"   ✅ 线性插值重采样完成: {len(resampled_data)} samples")
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            sf.write(temp_path, resampled_data, target_sample_rate)
            
            # 验证输出文件
            verify_data, verify_sr = sf.read(temp_path)
            new_duration = len(verify_data) / verify_sr
            print(f"   ✅ 输出: {verify_sr} Hz, {new_duration:.1f}秒, {len(verify_data)} samples")
            
            return temp_path
            
        except ImportError as e:
            print(f"   ❌ 缺少音频处理库: {e}")
            print("   💡 请安装: pip install soundfile scipy numpy")
            return None
        except Exception as e:
            print(f"   ❌ 音频预处理失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_ai_host_address(self) -> str:
        """获取AI端主机地址"""
        try:
            # 优先从AI管理器的配置获取主机地址
            if hasattr(self.ai_manager, 'ai_host') and self.ai_manager.ai_host:
                print(f"从AI管理器配置获取主机地址: {self.ai_manager.ai_host}")
                return self.ai_manager.ai_host
            
            # 从VRC控制器获取主机地址
            if hasattr(self.ai_manager, 'vrc_controller') and self.ai_manager.vrc_controller:
                if hasattr(self.ai_manager.vrc_controller, 'osc_client'):
                    host = self.ai_manager.vrc_controller.osc_client.host
                    print(f"从VRC控制器获取主机地址: {host}")
                    return host
            
            # 从传统多AI管理器获取
            if hasattr(self.ai_manager, 'osc_clients'):
                for client in self.ai_manager.osc_clients.values():
                    if hasattr(client, 'host'):
                        host = client.host
                        print(f"从OSC客户端获取主机地址: {host}")
                        return host
            
            print("无法从AI管理器获取主机地址，使用默认127.0.0.1")
            return "127.0.0.1"
            
        except Exception as e:
            print(f"获取AI主机地址失败: {e}")
            return "127.0.0.1"
    
    def _use_osc_audio_transmission(self, osc_client, file_path: str) -> bool:
        """使用OSC音频传输（备选方案）"""
        try:
            import base64
            
            # 读取音频文件并编码
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            # 将音频数据编码为base64，通过OSC发送
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 估算播放时长
            duration = self._estimate_audio_duration(file_path)
            
            # 通过自定义OSC消息发送音频数据
            chunk_size = 8192  # 每块大小
            total_chunks = len(audio_base64) // chunk_size + (1 if len(audio_base64) % chunk_size else 0)
            
            print(f"📦 OSC音频传输：分块发送{total_chunks}块")
            
            # 发送音频开始信号
            osc_client.send_message("/vrchat/audio/start", [total_chunks, duration])
            
            # 分块发送音频数据
            for i in range(total_chunks):
                start_idx = i * chunk_size
                end_idx = min((i + 1) * chunk_size, len(audio_base64))
                chunk_data = audio_base64[start_idx:end_idx]
                
                osc_client.send_message("/vrchat/audio/chunk", [i, chunk_data])
                time.sleep(0.01)  # 小延迟确保传输顺序
            
            # 发送音频结束信号
            osc_client.send_message("/vrchat/audio/end", [])
            
            print(f"📡 OSC音频传输完成，预计播放{duration:.2f}秒")
            return True
            
        except Exception as e:
            print(f"OSC音频传输失败: {e}")
            return False
    
    def _estimate_audio_duration(self, file_path: str) -> float:
        """估算音频文件时长"""
        try:
            import soundfile as sf
            with sf.SoundFile(file_path) as f:
                return len(f) / f.samplerate
        except:
            # 如果无法读取，使用文本长度估算
            return len(self.current_item.text) * 0.15 if self.current_item else 2.0
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        return {
            "queue_size": self.voice_queue.qsize(),
            "is_processing": self.is_processing,
            "current_item": self.current_item.text[:50] + "..." if self.current_item else None,
            "completed_count": len(self.completed_items),
            "failed_count": len(self.failed_items)
        }
    
    def get_recent_items(self, count: int = 10) -> List[Dict]:
        """获取最近的项目列表"""
        recent = []
        
        # 添加当前处理项目
        if self.current_item:
            recent.append({
                "id": self.current_item.item_id,
                "text": self.current_item.text[:50],
                "character": self.current_item.character_name,
                "status": self.current_item.status,
                "time": time.strftime('%H:%M:%S', time.localtime(self.current_item.created_time))
            })
        
        # 添加最近完成的项目
        for item in self.completed_items[-count:]:
            recent.append({
                "id": item.item_id,
                "text": item.text[:50],
                "character": item.character_name,
                "status": item.status,
                "time": time.strftime('%H:%M:%S', time.localtime(item.created_time))
            })
        
        return recent[-count:]
    
    def set_status_callback(self, callback: Callable):
        """设置状态变化回调"""
        self.status_callback = callback
    
    def set_completion_callback(self, callback: Callable):
        """设置完成回调"""
        self.completion_callback = callback
    
    def clear_queue(self):
        """清空队列"""
        while not self.voice_queue.empty():
            try:
                self.voice_queue.get_nowait()
            except queue.Empty:
                break
        print("语音队列已清空")
    
    def cleanup(self):
        """清理资源"""
        self.stop_processing()
        self.clear_queue()
        
        # 清理临时文件
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                print(f"已清理临时目录: {self.temp_dir}")
        except Exception as e:
            print(f"清理临时文件时出错: {e}")