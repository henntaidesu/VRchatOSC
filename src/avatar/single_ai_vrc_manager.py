#!/usr/bin/env python3
"""
单AI角色VRC管理器 - 专为单个AI角色设计的VRChat连接管理
"""

import threading
import time
import os
import tempfile
import queue
from typing import Optional, Callable
from ..vrchat_controller import VRChatController
from .ai_character import AICharacter, AIPersonality
from .voice_queue_manager import VoiceQueueManager


class SingleAIVRCManager:
    """单AI角色VRC管理器"""
    
    def __init__(self, voicevox_client=None):
        """初始化单AI角色VRC管理器
        
        Args:
            voicevox_client: VOICEVOX客户端
        """
        self.voicevox_client = voicevox_client
        
        # VRChat控制器
        self.vrc_controller: Optional[VRChatController] = None
        self.is_vrc_connected = False
        
        # AI角色
        self.ai_character: Optional[AICharacter] = None
        self.ai_character_name = ""
        self.ai_personality = AIPersonality.FRIENDLY
        self.is_ai_active = False
        
        # 语音队列管理器
        self.voice_queue_manager = None
        
        # 回调函数
        self.status_callback: Optional[Callable] = None
        
        print("单AI角色VRC管理器已初始化")
    
    def create_ai_character(self, name: str, personality: AIPersonality = AIPersonality.FRIENDLY) -> bool:
        """创建AI角色
        
        Args:
            name: AI角色名称
            personality: AI人格类型
            
        Returns:
            bool: 是否成功创建
        """
        try:
            # 如果已存在AI角色，先停用
            if self.ai_character:
                self.deactivate_ai_character()
            
            self.ai_character_name = name
            self.ai_personality = personality
            
            # 创建AI角色实例（暂时不需要avatar_controller）
            self.ai_character = AICharacter(
                name=name,
                personality=personality,
                avatar_controller=None,  # 等VRC连接后再设置
                voicevox_client=self.voicevox_client
            )
            
            print(f"AI角色 '{name}' 创建成功 (人格: {personality.value})")
            
            if self.status_callback:
                self.status_callback("ai_character_created", {"name": name, "personality": personality.value})
            
            return True
            
        except Exception as e:
            print(f"创建AI角色失败: {e}")
            return False
    
    def connect_to_vrc(self, host: str = "127.0.0.1", send_port: int = 9000, receive_port: int = 9001) -> bool:
        """连接到VRChat
        
        Args:
            host: VRChat主机地址
            send_port: OSC发送端口
            receive_port: OSC接收端口
            
        Returns:
            bool: 是否连接成功
        """
        try:
            if self.vrc_controller:
                self.disconnect_from_vrc()
            
            # 创建VRChat控制器
            self.vrc_controller = VRChatController(
                host=host,
                send_port=send_port,
                receive_port=receive_port
            )
            
            # 启动OSC服务器
            success = self.vrc_controller.start_osc_server()
            if not success:
                print("启动OSC服务器失败")
                return False
            
            self.is_vrc_connected = True
            
            # 如果有AI角色，更新其avatar_controller
            if self.ai_character:
                from .avatar_controller import AvatarController
                avatar_controller = AvatarController(
                    osc_client=self.vrc_controller.osc_client,
                    voicevox_client=self.voicevox_client
                )
                self.ai_character.avatar_controller = avatar_controller
            
            # 初始化语音队列管理器
            self.init_voice_queue_manager()
            
            print(f"VRChat连接成功 (发送端口: {send_port}, 接收端口: {receive_port})")
            
            if self.status_callback:
                self.status_callback("vrc_connected", {"host": host, "send_port": send_port, "receive_port": receive_port})
            
            return True
            
        except Exception as e:
            print(f"连接VRChat失败: {e}")
            self.is_vrc_connected = False
            return False
    
    def disconnect_from_vrc(self):
        """断开VRChat连接"""
        try:
            if self.voice_queue_manager:
                self.voice_queue_manager.cleanup()
                self.voice_queue_manager = None
            
            if self.ai_character and self.is_ai_active:
                self.deactivate_ai_character()
            
            if self.vrc_controller:
                self.vrc_controller.stop_osc_server()
                self.vrc_controller = None
            
            self.is_vrc_connected = False
            print("已断开VRChat连接")
            
            if self.status_callback:
                self.status_callback("vrc_disconnected", {})
            
        except Exception as e:
            print(f"断开VRChat连接时出错: {e}")
    
    def init_voice_queue_manager(self):
        """初始化语音队列管理器"""
        if not self.is_vrc_connected:
            return
        
        try:
            from .voice_queue_manager import VoiceQueueManager
            self.voice_queue_manager = VoiceQueueManager(
                voicevox_client=self.voicevox_client,
                ai_manager=self  # 传递自身作为AI管理器
            )
            
            self.voice_queue_manager.start_processing()
            print("语音队列管理器初始化成功")
            
        except Exception as e:
            print(f"初始化语音队列管理器失败: {e}")
    
    def activate_ai_character(self) -> bool:
        """激活AI角色"""
        if not self.ai_character:
            print("请先创建AI角色")
            return False
        
        if not self.is_vrc_connected:
            print("请先连接VRChat")
            return False
        
        if self.is_ai_active:
            print("AI角色已激活")
            return True
        
        try:
            success = self.ai_character.start_ai_behavior()
            if success:
                self.is_ai_active = True
                print(f"AI角色 '{self.ai_character_name}' 已激活")
                
                if self.status_callback:
                    self.status_callback("ai_activated", {"name": self.ai_character_name})
            
            return success
            
        except Exception as e:
            print(f"激活AI角色失败: {e}")
            return False
    
    def deactivate_ai_character(self) -> bool:
        """停用AI角色"""
        if not self.ai_character:
            return False
        
        try:
            self.ai_character.stop_ai_behavior()
            self.is_ai_active = False
            print(f"AI角色 '{self.ai_character_name}' 已停用")
            
            if self.status_callback:
                self.status_callback("ai_deactivated", {"name": self.ai_character_name})
            
            return True
            
        except Exception as e:
            print(f"停用AI角色失败: {e}")
            return False
    
    def make_ai_speak(self, text: str, emotion: str = "neutral") -> bool:
        """让AI角色说话"""
        if not self.ai_character or not self.is_ai_active:
            print("AI角色未激活")
            return False
        
        try:
            self.ai_character.say(text, emotion)
            return True
        except Exception as e:
            print(f"AI角色说话失败: {e}")
            return False
    
    def make_ai_greet(self, target_name: str = "") -> bool:
        """让AI角色打招呼"""
        if not self.ai_character or not self.is_ai_active:
            print("AI角色未激活")
            return False
        
        try:
            self.ai_character.greet_someone(target_name)
            return True
        except Exception as e:
            print(f"AI角色打招呼失败: {e}")
            return False
    
    def send_text_message(self, message: str) -> bool:
        """发送文本消息到VRChat"""
        if not self.vrc_controller or not self.is_vrc_connected:
            print("VRChat未连接")
            return False
        
        try:
            success = self.vrc_controller.send_text_message(message)
            if success:
                print(f"文本消息已发送: {message}")
            return success
        except Exception as e:
            print(f"发送文本消息失败: {e}")
            return False
    
    def upload_voice_file(self, file_path: str) -> bool:
        """上传语音文件（添加到队列）"""
        if not self.voice_queue_manager:
            print("语音队列管理器未初始化")
            return False
        
        if not os.path.exists(file_path):
            print(f"语音文件不存在: {file_path}")
            return False
        
        try:
            item_id = self.voice_queue_manager.add_voice_file(
                file_path=file_path,
                character_name=self.ai_character_name,
                text=f"上传的语音文件: {os.path.basename(file_path)}"
            )
            print(f"语音文件已添加到队列: {file_path} (ID: {item_id})")
            return True
            
        except Exception as e:
            print(f"上传语音文件失败: {e}")
            return False
    
    def generate_and_send_voice(self, text: str, speaker_id: int = 0) -> bool:
        """生成VOICEVOX语音并发送"""
        if not self.voice_queue_manager:
            print("语音队列管理器未初始化")
            return False
        
        # 如果没有AI角色名，使用默认名称
        character_name = self.ai_character_name if self.ai_character_name else "DefaultAI"
        
        try:
            item_id = self.voice_queue_manager.add_voicevox_item(
                text=text,
                character_name=character_name,
                speaker_id=speaker_id,
                emotion="neutral"
            )
            print(f"VOICEVOX语音已添加到队列: {text[:30]}... (ID: {item_id})")
            return True
            
        except Exception as e:
            print(f"生成并发送语音失败: {e}")
            return False
    
    def get_status(self) -> dict:
        """获取系统状态"""
        status = {
            "vrc_connected": self.is_vrc_connected,
            "ai_character_exists": self.ai_character is not None,
            "ai_character_name": self.ai_character_name,
            "ai_active": self.is_ai_active,
            "ai_personality": self.ai_personality.value if self.ai_character else None
        }
        
        if self.voice_queue_manager:
            status["voice_queue"] = self.voice_queue_manager.get_queue_status()
        
        return status
    
    def get_voice_queue_items(self, count: int = 10):
        """获取语音队列项目"""
        if self.voice_queue_manager:
            return self.voice_queue_manager.get_recent_items(count)
        return []
    
    def set_status_callback(self, callback: Callable):
        """设置状态回调函数"""
        self.status_callback = callback
    
    def update_voicevox_client(self, voicevox_client):
        """更新VOICEVOX客户端"""
        self.voicevox_client = voicevox_client
        
        if self.ai_character:
            self.ai_character.voicevox_client = voicevox_client
        
        if self.voice_queue_manager:
            self.voice_queue_manager.voicevox_client = voicevox_client
    
    def cleanup(self):
        """清理所有资源"""
        if self.voice_queue_manager:
            self.voice_queue_manager.cleanup()
        
        if self.ai_character and self.is_ai_active:
            self.deactivate_ai_character()
        
        if self.vrc_controller:
            self.disconnect_from_vrc()
        
        print("单AI角色VRC管理器已清理")
    
    # 为了兼容VoiceQueueManager的接口
    @property
    def osc_clients(self):
        """返回OSC客户端字典（兼容接口）"""
        character_name = self.ai_character_name if self.ai_character_name else "DefaultAI"
        if self.vrc_controller:
            return {character_name: self.vrc_controller.osc_client}
        return {}
    
    @property 
    def avatar_controllers(self):
        """返回Avatar控制器字典（兼容接口）"""
        character_name = self.ai_character_name if self.ai_character_name else "DefaultAI"
        if self.ai_character and self.ai_character.avatar_controller:
            return {character_name: self.ai_character.avatar_controller}
        return {}