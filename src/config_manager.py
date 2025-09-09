#!/usr/bin/env python3
"""
配置管理器 - JSON格式配置文件的读取、保存和验证
"""

import json
import os
from typing import Any, Dict, Optional, List


class ConfigManager:
    """配置管理器类 - 使用JSON格式"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = os.path.abspath(config_file)
        self.config = {}
        
        # 默认配置
        self.default_config = {
            "user_osc": {
                "host": "127.0.0.1",
                "send_port": 9000,
                "receive_port": 9001,
                "debug_mode": False,
                "enable_parameter_filtering": True,
                "filtered_parameters": {
                    "AvatarVersion": {
                        "enabled": True,
                        "description": "Avatar版本信息"
                    },
                    "Grounded": {
                        "enabled": True,
                        "description": "是否接地状态"
                    },
                    "InStation": {
                        "enabled": True,
                        "description": "是否在Station中"
                    },
                    "Seated": {
                        "enabled": True,
                        "description": "是否坐着"
                    },
                    "AFK": {
                        "enabled": True,
                        "description": "是否挂机"
                    },
                    "MuteSelf": {
                        "enabled": True,
                        "description": "是否静音"
                    },
                    "Earmuffs": {
                        "enabled": True,
                        "description": "是否戴耳机"
                    },
                    "AFKTimer": {
                        "enabled": True,
                        "description": "挂机计时器"
                    },
                    "Hips_SwimsuitGrab_Angle": {
                        "enabled": True,
                        "description": "臀部泳装抓取角度"
                    },
                    "GestureLeft": {
                        "enabled": False,
                        "description": "左手手势"
                    },
                    "GestureRight": {
                        "enabled": False,
                        "description": "右手手势"
                    }
                }
            },
            "voice": {
                "language": "ja-JP",
                "device": "auto",
                "voice_threshold": 0.015,
                "energy_threshold": 0.01
            },
            "recording": {
                "max_speech_duration": 8.0,
                "min_speech_duration": 0.3,
                "silence_duration": 0.8,
                "sentence_pause_threshold": 0.5,
                "phrase_pause_threshold": 0.3,
                "chunk_size_ms": 100
            },
            "modes": {
                "use_fallback_mode": False,
                "disable_fallback_mode": True,
                "vrc_detection_timeout": 30.0
            },
            "interface": {
                "ui_language": "zh",
                "window_width": 800,
                "window_height": 1000
            },
            "advanced": {
                "energy_drop_ratio": 0.3,
                "recent_energy_window": 10,
                "zero_crossing_threshold": 0.3,
                "recognition_interval": 1.0,
                "max_failures": 5
            },
            "llm": {
                "gemini_api_key": "",
                "gemini_model": "gemini-2.5-flash",
                "enable_llm": False,
                "temperature": 0.7,
                "max_output_tokens": 2048,
                "conversation_history_length": 10,
                "system_prompt": ""
            },
            "ai_osc": {
                "ai_host": "127.0.0.1",
                "ai_send_port": 9000,
                "ai_receive_port": 9001,
                "auto_connect": False,
                "connection_timeout": 10,
                "last_character_name": "",
                "last_character_personality": "friendly"
            },
            "voicevox": {
                "host": "localhost",
                "port": 50021,
                "last_period": "1期",
                "last_character": "春日部つむぎ",
                "last_speaker_id": "8",
                "last_speaker_name": "春日部つむぎ",
                "last_speaker_style": "ノーマル"
            },
            "runtime": {
                "mode": "user",
                "disable_speech_recognition": False
            }
        }
        
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print(f"[OK] 已加载配置文件: {self.config_file}")
                self._validate_config()
            except Exception as e:
                print(f"[警告] 加载配置文件失败: {e}")
                self._create_default_config()
        else:
            print(f"[信息] 配置文件不存在，创建默认配置: {self.config_file}")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置"""
        self.config = self.default_config.copy()
        self.save_config()
    
    def _validate_config(self):
        """验证配置完整性，添加缺失项"""
        modified = False
        
        def merge_dict(target, source, path=""):
            nonlocal modified
            for key, value in source.items():
                current_path = f"{path}.{key}" if path else key
                if key not in target:
                    target[key] = value
                    modified = True
                    print(f"[配置] 添加缺失配置项: {current_path}")
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    merge_dict(target[key], value, current_path)
        
        merge_dict(self.config, self.default_config)
        
        if modified:
            self.save_config()
            print("[更新] 配置文件已添加缺失项，用户配置保持不变")
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"[保存] 配置已保存: {self.config_file}")
        except Exception as e:
            print(f"[错误] 保存配置失败: {e}")
    
    def get(self, section: str, key: str = None, fallback: Any = None) -> Any:
        """获取配置值"""
        try:
            section_data = self.config.get(section.lower(), {})
            if key is None:
                return section_data
            return section_data.get(key, fallback)
        except Exception:
            return fallback
    
    def set(self, section: str, key: str, value: Any):
        """设置配置值"""
        section_lower = section.lower()
        if section_lower not in self.config:
            self.config[section_lower] = {}
        self.config[section_lower][key] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取整个配置节"""
        return self.get(section, fallback={})
    
    def update_section(self, section: str, values: Dict[str, Any]):
        """更新配置节"""
        for key, value in values.items():
            self.set(section, key, value)
    
    # OSC配置便捷方法
    @property
    def osc_host(self) -> str:
        return self.get('user_osc', 'host', '127.0.0.1')
    
    @property
    def osc_send_port(self) -> int:
        return self.get('user_osc', 'send_port', 9000)
    
    @property
    def osc_receive_port(self) -> int:
        return self.get('user_osc', 'receive_port', 9001)
    
    @property
    def osc_debug_mode(self) -> bool:
        return self.get('user_osc', 'debug_mode', False)
    
    @property
    def enable_parameter_filtering(self) -> bool:
        return self.get('user_osc', 'enable_parameter_filtering', True)
    
    @enable_parameter_filtering.setter
    def enable_parameter_filtering(self, value: bool):
        self.set('user_osc', 'enable_parameter_filtering', value)
    
    # OSC参数过滤配置
    @property
    def filtered_osc_parameters(self) -> List[str]:
        """获取需要过滤的OSC参数列表（启用状态的参数）"""
        filtered_params = self.get('user_osc', 'filtered_parameters', {})
        if not self.enable_parameter_filtering:
            return []
        return [param for param, config in filtered_params.items() 
                if config.get('enabled', False)]
    
    def get_osc_parameter_config(self) -> Dict[str, Dict]:
        """获取所有OSC参数配置"""
        return self.get('user_osc', 'filtered_parameters', {})
    
    def set_osc_parameter_enabled(self, param_name: str, enabled: bool):
        """设置OSC参数是否启用过滤"""
        filtered_params = self.get('user_osc', 'filtered_parameters', {})
        if param_name in filtered_params:
            filtered_params[param_name]['enabled'] = enabled
        else:
            filtered_params[param_name] = {
                'enabled': enabled,
                'description': '用户自定义参数'
            }
        self.set('user_osc', 'filtered_parameters', filtered_params)
    
    def add_custom_osc_parameter(self, param_name: str, description: str = "自定义参数"):
        """添加自定义OSC参数"""
        filtered_params = self.get('user_osc', 'filtered_parameters', {})
        if param_name not in filtered_params:
            filtered_params[param_name] = {
                'enabled': True,
                'description': description
            }
            self.set('user_osc', 'filtered_parameters', filtered_params)
            return True
        return False
    
    # 语音配置
    @property
    def voice_language(self) -> str:
        return self.get('voice', 'language', 'ja-JP')
    
    @property
    def voice_device(self) -> str:
        return self.get('voice', 'device', 'auto')
    
    @property
    def voice_threshold(self) -> float:
        return self.get('voice', 'voice_threshold', 0.015)
    
    @property
    def energy_threshold(self) -> float:
        return self.get('voice', 'energy_threshold', 0.01)
    
    # 界面配置
    @property
    def ui_language(self) -> str:
        return self.get('interface', 'ui_language', 'zh')
    
    @ui_language.setter
    def ui_language(self, value: str):
        self.set('interface', 'ui_language', value)
    
    @property
    def window_width(self) -> int:
        return self.get('interface', 'window_width', 800)
    
    @property
    def window_height(self) -> int:
        return self.get('interface', 'window_height', 1000)
    
    # LLM配置
    @property
    def gemini_api_key(self) -> str:
        return self.get('llm', 'gemini_api_key', '')
    
    @property
    def gemini_model(self) -> str:
        return self.get('llm', 'gemini_model', 'gemini-2.5-flash')
    
    @property
    def enable_llm(self) -> bool:
        return self.get('llm', 'enable_llm', False)
    
    @property
    def llm_temperature(self) -> float:
        return self.get('llm', 'temperature', 0.7)
    
    @property
    def llm_max_output_tokens(self) -> int:
        return self.get('llm', 'max_output_tokens', 2048)
    
    @property
    def llm_conversation_history_length(self) -> int:
        return self.get('llm', 'conversation_history_length', 10)
    
    @property
    def llm_system_prompt(self) -> str:
        return self.get('llm', 'system_prompt', '')
    
    # VOICEVOX配置
    @property
    def voicevox_host(self) -> str:
        return self.get('voicevox', 'host', 'localhost')
    
    @property
    def voicevox_port(self) -> int:
        return self.get('voicevox', 'port', 50021)
    
    @property
    def voicevox_last_speaker_name(self) -> str:
        return self.get('voicevox', 'last_speaker_name', '')
    
    @voicevox_last_speaker_name.setter
    def voicevox_last_speaker_name(self, value: str):
        self.set('voicevox', 'last_speaker_name', value)
    
    # 录制配置
    @property
    def max_speech_duration(self) -> float:
        return self.get('recording', 'max_speech_duration', 8.0)
    
    @property
    def min_speech_duration(self) -> float:
        return self.get('recording', 'min_speech_duration', 0.3)
    
    @property
    def silence_duration(self) -> float:
        return self.get('recording', 'silence_duration', 0.8)
    
    @property
    def sentence_pause_threshold(self) -> float:
        return self.get('recording', 'sentence_pause_threshold', 0.5)
    
    @property
    def phrase_pause_threshold(self) -> float:
        return self.get('recording', 'phrase_pause_threshold', 0.3)
    
    # 模式配置
    @property
    def use_fallback_mode(self) -> bool:
        return self.get('modes', 'use_fallback_mode', False)
    
    @property
    def disable_fallback_mode(self) -> bool:
        return self.get('modes', 'disable_fallback_mode', True)
    
    @property
    def vrc_detection_timeout(self) -> float:
        return self.get('modes', 'vrc_detection_timeout', 30.0)
    
    # 高级配置
    @property
    def energy_drop_ratio(self) -> float:
        return self.get('advanced', 'energy_drop_ratio', 0.3)
    
    @property
    def recent_energy_window(self) -> int:
        return self.get('advanced', 'recent_energy_window', 10)
    
    @property
    def recognition_interval(self) -> float:
        return self.get('advanced', 'recognition_interval', 1.0)
    
    # AI角色OSC配置  
    @property
    def ai_character_host(self) -> str:
        return self.get('ai_osc', 'ai_host', '127.0.0.1')
    
    @property
    def ai_character_send_port(self) -> int:
        return self.get('ai_osc', 'ai_send_port', 9000)
    
    @property
    def ai_character_receive_port(self) -> int:
        return self.get('ai_osc', 'ai_receive_port', 9001)
    
    @property
    def ai_character_auto_connect(self) -> bool:
        return self.get('ai_osc', 'auto_connect', False)
    
    @property
    def ai_character_connection_timeout(self) -> int:
        return self.get('ai_osc', 'connection_timeout', 10)
    
    @property
    def ai_character_last_name(self) -> str:
        return self.get('ai_osc', 'last_character_name', '')
    
    @property
    def ai_character_last_personality(self) -> str:
        return self.get('ai_osc', 'last_character_personality', 'friendly')
    
    # VOICEVOX扩展配置
    @property
    def voicevox_last_period(self) -> str:
        return self.get('voicevox', 'last_period', '1期')
    
    @property
    def voicevox_last_character(self) -> str:
        return self.get('voicevox', 'last_character', '春日部つむぎ')
    
    @property
    def voicevox_last_speaker_id(self) -> str:
        return self.get('voicevox', 'last_speaker_id', '8')
    
    @property
    def voicevox_last_speaker_style(self) -> str:
        return self.get('voicevox', 'last_speaker_style', 'ノーマル')
    
    # 运行时配置
    @property
    def runtime_mode(self) -> str:
        return self.get('runtime', 'mode', 'user')
    
    @property
    def disable_speech_recognition(self) -> bool:
        return self.get('runtime', 'disable_speech_recognition', False)
    
    # 添加缺失的setter方法
    def set_voicevox_last_selection(self, period: str, character: str, speaker_id: str = '', 
                                  speaker_name: str = '', speaker_style: str = ''):
        """保存VOICEVOX最后的选择"""
        self.set('voicevox', 'last_period', period)
        self.set('voicevox', 'last_character', character)
        self.set('voicevox', 'last_speaker_id', speaker_id)
        self.set('voicevox', 'last_speaker_name', speaker_name)
        self.set('voicevox', 'last_speaker_style', speaker_style)
    
    # AI角色OSC相关setter方法
    def set_ai_character_host(self, host: str):
        """设置AI角色主机地址"""
        self.set('ai_osc', 'ai_host', host)
    
    def set_ai_character_ports(self, send_port: int, receive_port: int):
        """设置AI角色OSC端口"""
        self.set('ai_osc', 'ai_send_port', send_port)
        self.set('ai_osc', 'ai_receive_port', receive_port)
    
    def set_ai_character_last_info(self, name: str, personality: str):
        """保存最后使用的AI角色信息"""
        self.set('ai_osc', 'last_character_name', name)
        self.set('ai_osc', 'last_character_personality', personality)
    
    def set_ai_character_auto_connect(self, auto_connect: bool):
        """设置是否自动连接"""
        self.set('ai_osc', 'auto_connect', auto_connect)
    
    # 运行时配置setter方法
    def set_runtime_mode(self, mode: str):
        """设置运行模式"""
        self.set('runtime', 'mode', mode)
    
    def set_disable_speech_recognition(self, disable: bool):
        """设置是否禁用语音识别"""
        self.set('runtime', 'disable_speech_recognition', disable)
    
    # VOICEVOX setter方法
    def set_voicevox_server(self, host: str, port: int):
        """设置VOICEVOX服务器地址和端口"""
        self.set('voicevox', 'host', host)
        self.set('voicevox', 'port', port)
    
    # 兼容原有的setter属性
    @voicevox_last_speaker_name.setter
    def voicevox_last_speaker_name(self, value: str):
        self.set('voicevox', 'last_speaker_name', value)
    
    @voicevox_last_speaker_id.setter  
    def voicevox_last_speaker_id(self, value: str):
        self.set('voicevox', 'last_speaker_id', value)
    
    @voicevox_last_speaker_style.setter
    def voicevox_last_speaker_style(self, value: str):
        self.set('voicevox', 'last_speaker_style', value)
    
    @voicevox_last_period.setter
    def voicevox_last_period(self, value: str):
        self.set('voicevox', 'last_period', value)


# 全局配置管理器实例
config_manager = ConfigManager()