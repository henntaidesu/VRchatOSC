#!/usr/bin/env python3
"""
VRChat实例管理模块
支持多VRChat实例管理，每个AI角色对应一个独立的VRChat客户端
"""

from .vrc_instance_manager import VRCInstanceManager, VRCInstance

__all__ = ['VRCInstanceManager', 'VRCInstance']