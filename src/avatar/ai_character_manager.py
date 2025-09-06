#!/usr/bin/env python3
"""
AI角色管理器 - 管理多个AI角色实例
"""

import json
import os
from typing import Dict, List, Optional
from .ai_character import AICharacter, AIPersonality


class AICharacterManager:
    """AI角色管理器"""
    
    def __init__(self, avatar_controller=None, voicevox_client=None, 
                 config_file: str = "data/ai_characters.json"):
        """初始化AI角色管理器
        
        Args:
            avatar_controller: Avatar控制器
            voicevox_client: VOICEVOX客户端
            config_file: 配置文件路径
        """
        self.avatar_controller = avatar_controller
        self.voicevox_client = voicevox_client
        self.config_file = config_file
        
        # AI角色实例
        self.ai_characters: Dict[str, AICharacter] = {}
        self.active_character: Optional[str] = None  # 当前激活的AI角色
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # 加载保存的AI角色配置
        self.load_character_configs()
    
    def create_ai_character(self, name: str, personality: AIPersonality = AIPersonality.FRIENDLY) -> bool:
        """创建新的AI角色
        
        Args:
            name: 角色名称
            personality: 角色人格
            
        Returns:
            bool: 是否成功创建
        """
        if name in self.ai_characters:
            print(f"AI角色 '{name}' 已存在")
            return False
        
        # 创建AI角色实例
        ai_char = AICharacter(
            name=name,
            personality=personality,
            avatar_controller=self.avatar_controller,
            voicevox_client=self.voicevox_client
        )
        
        self.ai_characters[name] = ai_char
        self.save_character_configs()
        
        print(f"AI角色 '{name}' 创建成功 (人格: {personality.value})")
        return True
    
    def remove_ai_character(self, name: str) -> bool:
        """删除AI角色
        
        Args:
            name: 角色名称
            
        Returns:
            bool: 是否成功删除
        """
        if name not in self.ai_characters:
            return False
        
        # 先停止AI角色
        self.ai_characters[name].stop_ai_behavior()
        
        # 如果是当前激活的角色，取消激活
        if self.active_character == name:
            self.active_character = None
        
        del self.ai_characters[name]
        self.save_character_configs()
        
        print(f"AI角色 '{name}' 已删除")
        return True
    
    def activate_character(self, name: str) -> bool:
        """激活指定的AI角色
        
        Args:
            name: 角色名称
            
        Returns:
            bool: 是否成功激活
        """
        if name not in self.ai_characters:
            print(f"AI角色 '{name}' 不存在")
            return False
        
        # 先停用当前激活的角色
        if self.active_character:
            self.deactivate_current_character()
        
        # 激活新角色
        success = self.ai_characters[name].start_ai_behavior()
        if success:
            self.active_character = name
            print(f"AI角色 '{name}' 已激活")
        
        return success
    
    def deactivate_current_character(self) -> bool:
        """停用当前激活的AI角色"""
        if not self.active_character:
            return False
        
        self.ai_characters[self.active_character].stop_ai_behavior()
        print(f"AI角色 '{self.active_character}' 已停用")
        self.active_character = None
        return True
    
    def get_active_character(self) -> Optional[AICharacter]:
        """获取当前激活的AI角色"""
        if self.active_character and self.active_character in self.ai_characters:
            return self.ai_characters[self.active_character]
        return None
    
    def get_character(self, name: str) -> Optional[AICharacter]:
        """获取指定名称的AI角色"""
        return self.ai_characters.get(name)
    
    def get_all_characters(self) -> Dict[str, AICharacter]:
        """获取所有AI角色"""
        return self.ai_characters.copy()
    
    def list_character_names(self) -> List[str]:
        """获取所有AI角色名称列表"""
        return list(self.ai_characters.keys())
    
    def get_character_status(self, name: str) -> Optional[Dict]:
        """获取AI角色状态"""
        if name in self.ai_characters:
            return self.ai_characters[name].get_status()
        return None
    
    def get_all_character_status(self) -> Dict[str, Dict]:
        """获取所有AI角色状态"""
        status = {}
        for name, char in self.ai_characters.items():
            status[name] = char.get_status()
        return status
    
    def update_controllers(self, avatar_controller=None, voicevox_client=None):
        """更新所有AI角色的控制器引用
        
        Args:
            avatar_controller: 新的Avatar控制器
            voicevox_client: 新的VOICEVOX客户端
        """
        if avatar_controller:
            self.avatar_controller = avatar_controller
        if voicevox_client:
            self.voicevox_client = voicevox_client
        
        # 更新所有AI角色的控制器引用
        for ai_char in self.ai_characters.values():
            if avatar_controller:
                ai_char.avatar_controller = avatar_controller
            if voicevox_client:
                ai_char.voicevox_client = voicevox_client
    
    # 快捷控制方法
    
    def make_active_character_speak(self, text: str, emotion: str = "neutral") -> bool:
        """让当前激活的AI角色说话"""
        active_char = self.get_active_character()
        if active_char:
            active_char.say(text, emotion)
            return True
        return False
    
    def make_active_character_greet(self, target_name: str = "") -> bool:
        """让当前激活的AI角色打招呼"""
        active_char = self.get_active_character()
        if active_char:
            active_char.greet_someone(target_name)
            return True
        return False
    
    def make_active_character_react(self, speech_text: str, speaker: str = "") -> bool:
        """让当前激活的AI角色对语音做出反应"""
        active_char = self.get_active_character()
        if active_char:
            active_char.react_to_speech(speech_text, speaker)
            return True
        return False
    
    def set_active_character_personality(self, personality: AIPersonality) -> bool:
        """设置当前激活AI角色的人格"""
        active_char = self.get_active_character()
        if active_char:
            active_char.set_personality(personality)
            self.save_character_configs()
            return True
        return False
    
    def save_character_configs(self):
        """保存AI角色配置到文件"""
        try:
            config_data = {
                "active_character": self.active_character,
                "characters": {}
            }
            
            for name, char in self.ai_characters.items():
                config_data["characters"][name] = {
                    "personality": char.personality.value,
                    "auto_behavior_enabled": char.auto_behavior_enabled,
                    "speech_cooldown": char.speech_cooldown
                }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"保存AI角色配置失败: {e}")
    
    def load_character_configs(self):
        """从文件加载AI角色配置"""
        try:
            if not os.path.exists(self.config_file):
                # 创建默认AI角色
                self.create_default_characters()
                return
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 重建AI角色实例
            for name, config in config_data.get("characters", {}).items():
                personality = AIPersonality(config.get("personality", "friendly"))
                
                ai_char = AICharacter(
                    name=name,
                    personality=personality,
                    avatar_controller=self.avatar_controller,
                    voicevox_client=self.voicevox_client
                )
                
                ai_char.auto_behavior_enabled = config.get("auto_behavior_enabled", True)
                ai_char.speech_cooldown = config.get("speech_cooldown", 5)
                
                self.ai_characters[name] = ai_char
            
            # 恢复激活状态
            active_name = config_data.get("active_character")
            if active_name and active_name in self.ai_characters:
                self.active_character = active_name
            
            print(f"已加载 {len(self.ai_characters)} 个AI角色配置")
            
        except Exception as e:
            print(f"加载AI角色配置失败: {e}")
            self.create_default_characters()
    
    def create_default_characters(self):
        """创建默认的AI角色"""
        default_characters = [
            ("小助手", AIPersonality.FRIENDLY),
            ("元气少女", AIPersonality.ENERGETIC),
            ("安静同学", AIPersonality.SHY),
            ("冷静分析师", AIPersonality.CALM)
        ]
        
        for name, personality in default_characters:
            self.create_ai_character(name, personality)
        
        print("已创建默认AI角色")
    
    def get_character_count(self) -> int:
        """获取AI角色数量"""
        return len(self.ai_characters)
    
    def has_active_character(self) -> bool:
        """检查是否有激活的AI角色"""
        return self.active_character is not None and self.active_character in self.ai_characters