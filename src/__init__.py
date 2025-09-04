"""
VRChat OSC 通信包 - 核心模块导出
"""

from .vrchat_controller import VRChatController
from .osc_client import OSCClient
from .speech_engine import SpeechEngine

__all__ = [
    'VRChatController',
    'OSCClient', 
    'SpeechEngine'
]

__version__ = '2.0.0'