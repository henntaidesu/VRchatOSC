#!/usr/bin/env python3
"""
Avatar控制模块 - VRChat虚拟人物控制逻辑

包含功能：
- Avatar参数控制
- 角色位置管理  
- 表情映射
- 距离追踪
"""

from .avatar_controller import AvatarController
from .character_manager import CharacterManager
from .expression_mapper import ExpressionMapper
from .avatar_parameters import AvatarParameters

__all__ = [
    'AvatarController',
    'CharacterManager', 
    'ExpressionMapper',
    'AvatarParameters'
]