#!/usr/bin/env python3
"""
Avatar控制器 - 统一管理VRChat虚拟人物控制
专注于VOICEVOX语音输出驱动的Avatar控制
"""

from typing import Optional, Callable
from .expression_mapper import ExpressionMapper
from .character_manager import CharacterManager
from .avatar_parameters import AvatarParameters
from .ai_character_manager import AICharacterManager


class AvatarController:
    """Avatar控制器主类"""
    
    def __init__(self, osc_client=None, character_data_file: str = "data/vrc_characters.json", 
                 voicevox_client=None):
        """初始化Avatar控制器
        
        Args:
            osc_client: OSC客户端实例
            character_data_file: 角色数据文件路径
            voicevox_client: VOICEVOX客户端实例
        """
        self.osc_client = osc_client
        self.voicevox_client = voicevox_client
        
        # 初始化子模块
        self.expression_mapper = ExpressionMapper(osc_client)
        self.character_manager = CharacterManager(character_data_file)
        self.ai_character_manager = AICharacterManager(self, voicevox_client)
        
        # 状态跟踪
        self.is_connected = False
        self.current_voice_text = ""
        self.auto_expression_enabled = True  # 是否启用自动表情
        
    def set_osc_client(self, osc_client):
        """设置OSC客户端"""
        self.osc_client = osc_client
        self.expression_mapper.osc_client = osc_client
        self.is_connected = osc_client is not None
        
        # 更新AI角色管理器的控制器引用
        self.ai_character_manager.update_controllers(avatar_controller=self)
    
    def set_voicevox_client(self, voicevox_client):
        """设置VOICEVOX客户端"""
        self.voicevox_client = voicevox_client
        
        # 更新AI角色管理器的VOICEVOX客户端引用
        self.ai_character_manager.update_controllers(voicevox_client=voicevox_client)
    
    # === 表情控制接口 ===
    
    def set_expression(self, emotion: str, intensity: float = 1.0) -> bool:
        """设置面部表情
        
        Args:
            emotion: 表情类型 ('happy', 'sad', 'angry', 'surprise', 'fear', 'disgust', 'neutral')
            intensity: 表情强度 (0.0-1.0)
            
        Returns:
            bool: 是否成功
        """
        return self.expression_mapper.set_expression(emotion, intensity)
    
    def clear_expressions(self) -> bool:
        """清除所有表情，回到中性状态"""
        return self.expression_mapper.clear_all_expressions()
    
    def blink(self, intensity: float = 1.0) -> bool:
        """执行眨眼动作"""
        return self.expression_mapper.set_eye_blink(intensity)
    
    # === VOICEVOX集成接口 ===
    
    def start_speaking(self, text: str = "", emotion: str = "neutral", 
                      voice_level: float = 0.8, emotion_intensity: float = 0.7) -> bool:
        """开始说话（VOICEVOX输出时调用）
        
        Args:
            text: 要说的文本
            emotion: 对应的表情
            voice_level: 语音强度
            emotion_intensity: 表情强度
            
        Returns:
            bool: 是否成功
        """
        self.current_voice_text = text
        
        # 设置语音活动状态
        success1 = self.expression_mapper.set_voice_activity(True, voice_level)
        
        # 如果启用了自动表情，设置对应表情
        success2 = True
        if self.auto_expression_enabled and emotion != "neutral":
            success2 = self.expression_mapper.set_expression(emotion, emotion_intensity)
        
        return success1 and success2
    
    def stop_speaking(self) -> bool:
        """停止说话"""
        self.current_voice_text = ""
        success1 = self.expression_mapper.set_voice_activity(False, 0.0)
        
        # 可选：返回中性表情
        success2 = True
        if self.auto_expression_enabled:
            success2 = self.expression_mapper.set_expression("neutral", 0.3)
        
        return success1 and success2
    
    def update_voice_level(self, level: float) -> bool:
        """更新语音强度（实时调用）"""
        is_speaking = self.expression_mapper.is_speaking
        return self.expression_mapper.set_voice_activity(is_speaking, level)
    
    # === 直接参数控制接口 ===
    
    def send_avatar_parameter(self, parameter_name: str, value) -> bool:
        """发送Avatar参数
        
        Args:
            parameter_name: 参数名称（不含/avatar/parameters/前缀）
            value: 参数值
            
        Returns:
            bool: 是否成功
        """
        if not self.osc_client:
            return False
            
        # 验证参数值
        full_path = f"/avatar/parameters/{parameter_name}"
        if full_path in AvatarParameters.PARAMETER_TYPES:
            validated_value = AvatarParameters.validate_parameter_value(full_path, value)
            return self.osc_client.send_parameter(parameter_name, validated_value)
        else:
            # 未知参数，直接发送
            return self.osc_client.send_parameter(parameter_name, value)
    
    # === 角色管理接口 ===
    
    def add_character(self, name: str, x: float, y: float, z: float) -> bool:
        """添加角色"""
        return self.character_manager.add_character(name, x, y, z)
    
    def remove_character(self, name: str) -> bool:
        """删除角色"""
        return self.character_manager.remove_character(name)
    
    def update_player_position(self, x: float, y: float, z: float):
        """更新玩家位置（从OSC数据调用）"""
        self.character_manager.update_player_position(x, y, z)
    
    def get_character_distances(self):
        """获取角色距离信息"""
        return self.character_manager.get_character_distances()
    
    def get_distance_text(self, max_count: int = 5) -> str:
        """获取距离信息文本"""
        return self.character_manager.get_distance_info_text(max_count)
    
    def add_position_callback(self, callback: Callable):
        """添加位置更新回调"""
        self.character_manager.add_position_callback(callback)
    
    # === 状态查询接口 ===
    
    def get_current_expression(self) -> str:
        """获取当前表情"""
        return self.expression_mapper.get_current_expression()
    
    def get_voice_status(self):
        """获取语音状态"""
        return self.expression_mapper.get_voice_status()
    
    def is_avatar_connected(self) -> bool:
        """检查Avatar是否连接"""
        return self.is_connected and self.osc_client is not None
    
    def get_all_characters(self):
        """获取所有角色信息"""
        return self.character_manager.get_all_characters()
    
    def get_player_position(self):
        """获取玩家位置"""
        return self.character_manager.get_player_position()
    
    # === 配置接口 ===
    
    def set_auto_expression_enabled(self, enabled: bool):
        """设置是否启用自动表情"""
        self.auto_expression_enabled = enabled
    
    def is_auto_expression_enabled(self) -> bool:
        """检查是否启用了自动表情"""
        return self.auto_expression_enabled
    
    # === 文本情感分析接口（为未来扩展准备）===
    
    def analyze_text_emotion(self, text: str) -> str:
        """分析文本情感（简单实现，可扩展）
        
        Args:
            text: 要分析的文本
            
        Returns:
            str: 推测的情感类型
        """
        # 简单的关键词匹配，可以扩展为更复杂的情感分析
        text_lower = text.lower()
        
        # 开心相关词汇
        if any(word in text_lower for word in ['高兴', '开心', '快乐', '哈哈', '呵呵', '笑', '太好了']):
            return 'happy'
        
        # 生气相关词汇
        elif any(word in text_lower for word in ['生气', '愤怒', '气死', '讨厌', '烦']):
            return 'angry'
        
        # 悲伤相关词汇
        elif any(word in text_lower for word in ['伤心', '难过', '哭', '悲伤', '失望']):
            return 'sad'
        
        # 惊讶相关词汇
        elif any(word in text_lower for word in ['惊讶', '震惊', '哇', '天啊', '不会吧']):
            return 'surprise'
        
        # 默认中性
        else:
            return 'neutral'
    
    def speak_with_emotion(self, text: str, voice_level: float = 0.8) -> bool:
        """带情感的语音输出
        
        Args:
            text: 要说的文本
            voice_level: 语音强度
            
        Returns:
            bool: 是否成功
        """
        emotion = self.analyze_text_emotion(text)
        return self.start_speaking(text, emotion, voice_level)
    
    # === AI角色控制接口 ===
    
    def create_ai_character(self, name: str, personality_type: str = "friendly") -> bool:
        """创建AI角色
        
        Args:
            name: AI角色名称
            personality_type: 人格类型 ('friendly', 'shy', 'energetic', 'calm', 'playful')
            
        Returns:
            bool: 是否成功创建
        """
        from .ai_character import AIPersonality
        try:
            personality = AIPersonality(personality_type)
            return self.ai_character_manager.create_ai_character(name, personality)
        except ValueError:
            print(f"无效的人格类型: {personality_type}")
            return False
    
    def activate_ai_character(self, name: str) -> bool:
        """激活AI角色"""
        return self.ai_character_manager.activate_character(name)
    
    def deactivate_ai_character(self) -> bool:
        """停用当前AI角色"""
        return self.ai_character_manager.deactivate_current_character()
    
    def remove_ai_character(self, name: str) -> bool:
        """删除AI角色"""
        return self.ai_character_manager.remove_ai_character(name)
    
    def get_ai_characters(self) -> list:
        """获取所有AI角色名称"""
        return self.ai_character_manager.list_character_names()
    
    def get_active_ai_character(self) -> str:
        """获取当前激活的AI角色名称"""
        return self.ai_character_manager.active_character or ""
    
    def make_ai_character_speak(self, text: str, emotion: str = "neutral") -> bool:
        """让AI角色说话"""
        return self.ai_character_manager.make_active_character_speak(text, emotion)
    
    def make_ai_character_greet(self, target_name: str = "") -> bool:
        """让AI角色打招呼"""
        return self.ai_character_manager.make_active_character_greet(target_name)
    
    def set_ai_character_personality(self, personality_type: str) -> bool:
        """设置AI角色人格"""
        from .ai_character import AIPersonality
        try:
            personality = AIPersonality(personality_type)
            return self.ai_character_manager.set_active_character_personality(personality)
        except ValueError:
            return False
    
    def get_ai_character_status(self) -> dict:
        """获取所有AI角色状态"""
        return self.ai_character_manager.get_all_character_status()
    
    def has_active_ai_character(self) -> bool:
        """检查是否有激活的AI角色"""
        return self.ai_character_manager.has_active_character()