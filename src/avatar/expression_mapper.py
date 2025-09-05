#!/usr/bin/env python3
"""
表情映射器 - 处理表情输入到Avatar参数的映射
专注于VOICEVOX语音输出驱动的表情控制
"""

from typing import Dict, Optional
from .avatar_parameters import AvatarParameters


class ExpressionMapper:
    """表情映射器类 - 用于控制VRChat Avatar表情"""
    
    def __init__(self, osc_client=None):
        """初始化表情映射器
        
        Args:
            osc_client: OSC客户端实例，用于发送参数到VRChat
        """
        self.osc_client = osc_client
        self.current_expression = "neutral"
        self.is_speaking = False
        self.voice_level = 0.0
    
    def set_expression(self, emotion: str, intensity: float = 1.0) -> bool:
        """设置面部表情
        
        Args:
            emotion: 表情名称 ('happy', 'sad', 'angry', 'surprise', 'fear', 'disgust', 'neutral')
            intensity: 表情强度 (0.0-1.0)
            
        Returns:
            bool: 是否成功发送到VRChat
        """
        if not self.osc_client:
            return False
            
        # 验证表情名称
        if emotion not in AvatarParameters.FACE_EXPRESSIONS:
            return False
        
        # 清除之前的表情
        self.clear_all_expressions()
        
        # 设置新表情
        parameter_name = AvatarParameters.FACE_EXPRESSIONS[emotion].replace('/avatar/parameters/', '')
        validated_intensity = AvatarParameters.validate_parameter_value(
            AvatarParameters.FACE_EXPRESSIONS[emotion], intensity
        )
        
        success = self.osc_client.send_parameter(parameter_name, validated_intensity)
        
        if success:
            self.current_expression = emotion
            
        return success
    
    def set_voice_activity(self, speaking: bool, level: float = 0.0) -> bool:
        """设置语音活动状态（用于VOICEVOX语音输出时）
        
        Args:
            speaking: 是否在说话
            level: 语音强度 (0.0-1.0)
            
        Returns:
            bool: 是否成功
        """
        if not self.osc_client:
            return False
            
        self.is_speaking = speaking
        self.voice_level = level
        
        # 发送语音参数到VRChat
        success1 = self.osc_client.send_parameter('IsSpeaking', speaking)
        success2 = self.osc_client.send_parameter('Voice', level)
        
        # 语音激活时设置嘴部动作
        if speaking and level > 0.1:
            mouth_intensity = min(level * 1.2, 1.0)  # 稍微放大嘴部动作
            success3 = self.osc_client.send_parameter('MouthMove', mouth_intensity)
            success4 = self.osc_client.send_parameter('MouthOpen', mouth_intensity * 0.5)
            return all([success1, success2, success3, success4])
        else:
            # 停止说话时重置嘴部
            success3 = self.osc_client.send_parameter('MouthMove', 0.0)
            success4 = self.osc_client.send_parameter('MouthOpen', 0.0)
            return all([success1, success2, success3, success4])
    
    def set_mouth_movement(self, mouth_open: float, viseme: int = 0) -> bool:
        """直接控制嘴部动作
        
        Args:
            mouth_open: 嘴部开合程度 (0.0-1.0)
            viseme: Viseme ID (0-14，用于口型同步)
            
        Returns:
            bool: 是否成功
        """
        if not self.osc_client:
            return False
            
        success1 = self.osc_client.send_parameter('MouthOpen', mouth_open)
        success2 = self.osc_client.send_parameter('Viseme', viseme)
        
        return success1 and success2
    
    def set_eye_blink(self, blink_intensity: float = 1.0) -> bool:
        """设置眨眼动作
        
        Args:
            blink_intensity: 眨眼强度 (0.0-1.0)
            
        Returns:
            bool: 是否成功
        """
        if not self.osc_client:
            return False
            
        success1 = self.osc_client.send_parameter('LeftEyeBlink', blink_intensity)
        success2 = self.osc_client.send_parameter('RightEyeBlink', blink_intensity)
        success3 = self.osc_client.send_parameter('EyeBlink', blink_intensity)
        
        return all([success1, success2, success3])
    
    def clear_all_expressions(self) -> bool:
        """清除所有表情参数，回到中性状态"""
        if not self.osc_client:
            return False
            
        success_list = []
        for emotion, parameter_path in AvatarParameters.FACE_EXPRESSIONS.items():
            param_name = parameter_path.replace('/avatar/parameters/', '')
            success = self.osc_client.send_parameter(param_name, 0.0)
            success_list.append(success)
        
        if all(success_list):
            self.current_expression = "neutral"
            
        return all(success_list)
    
    def get_current_expression(self) -> str:
        """获取当前表情"""
        return self.current_expression
    
    def get_voice_status(self) -> Dict[str, any]:
        """获取语音状态"""
        return {
            'is_speaking': self.is_speaking,
            'voice_level': self.voice_level
        }
    
    # VOICEVOX集成相关方法
    def on_voicevox_start_speaking(self, text: str = "", voice_level: float = 0.8):
        """VOICEVOX开始说话时调用"""
        self.set_voice_activity(True, voice_level)
    
    def on_voicevox_stop_speaking(self):
        """VOICEVOX停止说话时调用"""
        self.set_voice_activity(False, 0.0)
    
    def on_voicevox_text_emotion(self, text: str, emotion: str = "neutral", intensity: float = 0.7):
        """根据VOICEVOX文本内容设置表情
        
        Args:
            text: 要说的文本
            emotion: 情感类型
            intensity: 情感强度
        """
        # 可以根据文本内容分析情感，这里先直接使用传入的情感
        self.set_expression(emotion, intensity)