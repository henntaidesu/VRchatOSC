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
        while self.is_processing:
            try:
                # 从队列获取项目（超时1秒）
                try:
                    item = self.voice_queue.get(timeout=1)
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
                    success = self._process_voicevox_item(item)
                elif item.item_type == VoiceItemType.FILE:
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
        if not self.voicevox_client:
            print("VOICEVOX客户端未连接")
            return False
        
        try:
            # 生成临时文件路径
            temp_file = os.path.join(self.temp_dir, f"{item.item_id}.wav")
            
            # 设置说话人ID
            if item.speaker_id > 0:
                self.voicevox_client.set_speaker(item.speaker_id)
            
            # 使用VOICEVOX合成语音并保存到文件
            success = self.voicevox_client.save_audio(
                text=item.text,
                output_path=temp_file
            )
            
            if not success or not os.path.exists(temp_file):
                print(f"VOICEVOX语音合成失败: {item.text}")
                return False
            
            item.file_path = temp_file
            
            # 发送到AI角色的VRC
            return self._send_voice_to_character(item)
            
        except Exception as e:
            print(f"处理VOICEVOX项目时出错: {e}")
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
        if not self.ai_manager:
            print("AI管理器未设置")
            return False
        
        try:
            # 获取AI角色对应的OSC客户端
            osc_client = self.ai_manager.osc_clients.get(item.character_name)
            if not osc_client:
                print(f"未找到AI角色 '{item.character_name}' 的OSC客户端")
                return False
            
            # 设置Avatar表情（基于emotion）
            avatar_controller = self.ai_manager.avatar_controllers.get(item.character_name)
            if avatar_controller:
                avatar_controller.start_speaking(item.text, item.emotion, voice_level=0.8)
            
            # 发送语音文件到VRChat（这里需要实现具体的VRC语音发送逻辑）
            # 注意：VRChat OSC目前不直接支持语音文件上传，这里可能需要其他方式
            success = self._upload_voice_to_vrc(osc_client, item.file_path)
            
            if success:
                print(f"语音已发送到VRChat角色: {item.character_name}")
                
                # 语音播放完成后停止说话状态
                if avatar_controller:
                    # 估算播放时长
                    duration = self._estimate_audio_duration(item.file_path)
                    threading.Timer(duration, lambda: avatar_controller.stop_speaking()).start()
            
            return success
            
        except Exception as e:
            print(f"发送语音到角色时出错: {e}")
            return False
    
    def _upload_voice_to_vrc(self, osc_client, file_path: str) -> bool:
        """模拟麦克风发声（通过OSC控制麦克风状态 + 音频播放）"""
        try:
            import pygame
            import os
            
            if not os.path.exists(file_path):
                print(f"语音文件不存在: {file_path}")
                return False
            
            # 1. 通过OSC取消静音（模拟按下麦克风）
            osc_client.send_message("/input/Voice", 1)
            print("OSC: 取消麦克风静音")
            
            # 等待前一个语音播放完成（顺序播放）
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # 2. 播放音频文件（通过默认音频设备，VRC可以通过虚拟音频线接收）
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            print(f"开始播放语音文件并模拟麦克风发声: {file_path}")
            
            # 3. 等待播放完成
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # 4. 通过OSC静音麦克风（模拟松开麦克风）
            osc_client.send_message("/input/Voice", 0)
            print("OSC: 麦克风静音")
            
            # 5. 重置OSC状态（解决已知的OSC Voice bug）
            time.sleep(0.1)
            osc_client.send_message("/input/Voice", 0)
            
            print("语音播放完成，麦克风状态已重置")
            return True
            
        except Exception as e:
            print(f"模拟麦克风发声失败: {e}")
            # 确保在错误情况下也重置麦克风状态
            try:
                osc_client.send_message("/input/Voice", 0)
                osc_client.send_message("/input/Voice", 0)  # 重置状态
            except:
                pass
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