#!/usr/bin/env python3
"""
Avatar参数定义和常量
定义VRChat Avatar的所有可控制参数
"""

from typing import Dict, Any
from enum import Enum


class ParameterType(Enum):
    """参数类型枚举"""
    BOOL = "bool"
    FLOAT = "float" 
    INT = "int"


class AvatarParameters:
    """Avatar参数定义类"""
    
    # 表情参数映射
    FACE_EXPRESSIONS = {
        'angry': '/avatar/parameters/FaceAngry',
        'disgust': '/avatar/parameters/FaceDisgust', 
        'fear': '/avatar/parameters/FaceFear',
        'happy': '/avatar/parameters/FaceHappy',
        'sad': '/avatar/parameters/FaceSad',
        'surprise': '/avatar/parameters/FaceSurprise',
        'neutral': '/avatar/parameters/FaceNeutral'
    }
    
    # 语音相关参数
    VOICE_PARAMETERS = {
        'voice_level': '/avatar/parameters/Voice',
        'voice_gain': '/avatar/parameters/VoiceGain',
        'is_speaking': '/avatar/parameters/IsSpeaking',
        'mic_level': '/avatar/parameters/MicLevel',
        'voice_threshold': '/avatar/parameters/VoiceThreshold'
    }
    
    # 嘴部动作参数
    MOUTH_PARAMETERS = {
        'mouth_open': '/avatar/parameters/MouthOpen',
        'viseme': '/avatar/parameters/Viseme',
        'mouth_move': '/avatar/parameters/MouthMove'
    }
    
    # 眼部表情参数
    EYE_PARAMETERS = {
        'left_eye_blink': '/avatar/parameters/LeftEyeBlink',
        'right_eye_blink': '/avatar/parameters/RightEyeBlink',
        'eye_blink': '/avatar/parameters/EyeBlink',
        'eye_look_up': '/avatar/parameters/EyeLookUp',
        'eye_look_down': '/avatar/parameters/EyeLookDown'
    }
    
    # 手势参数
    GESTURE_PARAMETERS = {
        'gesture_left': '/avatar/parameters/GestureLeft',
        'gesture_right': '/avatar/parameters/GestureRight',
        'gesture_left_weight': '/avatar/parameters/GestureLeftWeight',
        'gesture_right_weight': '/avatar/parameters/GestureRightWeight'
    }
    
    # 运动参数
    LOCOMOTION_PARAMETERS = {
        'velocity_x': '/avatar/parameters/VelocityX',
        'velocity_y': '/avatar/parameters/VelocityY', 
        'velocity_z': '/avatar/parameters/VelocityZ',
        'angular_y': '/avatar/parameters/AngularY',
        'upright': '/avatar/parameters/Upright',
        'grounded': '/avatar/parameters/Grounded'
    }
    
    # 自定义参数类型定义
    PARAMETER_TYPES = {
        # 表情参数都是浮点型 (0.0-1.0)
        **{param: ParameterType.FLOAT for param in FACE_EXPRESSIONS.values()},
        
        # 语音参数
        '/avatar/parameters/Voice': ParameterType.FLOAT,
        '/avatar/parameters/VoiceGain': ParameterType.FLOAT,
        '/avatar/parameters/IsSpeaking': ParameterType.BOOL,
        '/avatar/parameters/MicLevel': ParameterType.FLOAT,
        
        # 嘴部参数
        '/avatar/parameters/MouthOpen': ParameterType.FLOAT,
        '/avatar/parameters/Viseme': ParameterType.INT,  # 0-14
        '/avatar/parameters/MouthMove': ParameterType.FLOAT,
        
        # 眼部参数
        '/avatar/parameters/LeftEyeBlink': ParameterType.FLOAT,
        '/avatar/parameters/RightEyeBlink': ParameterType.FLOAT,
        '/avatar/parameters/EyeBlink': ParameterType.FLOAT,
        
        # 手势参数
        '/avatar/parameters/GestureLeft': ParameterType.INT,  # 0-7
        '/avatar/parameters/GestureRight': ParameterType.INT,  # 0-7
        '/avatar/parameters/GestureLeftWeight': ParameterType.FLOAT,
        '/avatar/parameters/GestureRightWeight': ParameterType.FLOAT,
        
        # 运动参数
        '/avatar/parameters/VelocityX': ParameterType.FLOAT,
        '/avatar/parameters/VelocityY': ParameterType.FLOAT,
        '/avatar/parameters/VelocityZ': ParameterType.FLOAT,
        '/avatar/parameters/AngularY': ParameterType.FLOAT,
        '/avatar/parameters/Upright': ParameterType.FLOAT,
        '/avatar/parameters/Grounded': ParameterType.BOOL,
    }
    
    @classmethod
    def get_parameter_type(cls, parameter_path: str) -> ParameterType:
        """获取参数类型"""
        return cls.PARAMETER_TYPES.get(parameter_path, ParameterType.FLOAT)
    
    @classmethod
    def get_all_parameters(cls) -> Dict[str, str]:
        """获取所有参数"""
        all_params = {}
        all_params.update(cls.FACE_EXPRESSIONS)
        all_params.update(cls.VOICE_PARAMETERS) 
        all_params.update(cls.MOUTH_PARAMETERS)
        all_params.update(cls.EYE_PARAMETERS)
        all_params.update(cls.GESTURE_PARAMETERS)
        all_params.update(cls.LOCOMOTION_PARAMETERS)
        return all_params
    
    @classmethod
    def validate_parameter_value(cls, parameter_path: str, value: Any) -> Any:
        """验证并转换参数值"""
        param_type = cls.get_parameter_type(parameter_path)
        
        if param_type == ParameterType.BOOL:
            return bool(value)
        elif param_type == ParameterType.FLOAT:
            float_val = float(value)
            # 大多数浮点参数限制在0-1范围内
            if 'Weight' in parameter_path or 'Blink' in parameter_path or 'Face' in parameter_path:
                return max(0.0, min(1.0, float_val))
            return float_val
        elif param_type == ParameterType.INT:
            int_val = int(value)
            # Gesture参数范围0-7，Viseme参数范围0-14
            if 'Gesture' in parameter_path and 'Weight' not in parameter_path:
                return max(0, min(7, int_val))
            elif 'Viseme' in parameter_path:
                return max(0, min(14, int_val))
            return int_val
        
        return value