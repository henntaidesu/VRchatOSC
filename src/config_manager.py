#!/usr/bin/env python3
"""
配置管理器 - 处理配置文件的读取、保存和验证
"""

import configparser
import os
from typing import Any, Dict, Optional


class ConfigManager:
    """配置管理器类"""
    
    def __init__(self, config_file: str = "conf.ini"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = os.path.abspath(config_file)
        self.config = configparser.ConfigParser()
        
        # 默认配置
        self.default_config = {
            'OSC': {
                'host': '127.0.0.1',
                'send_port': '9000',
                'receive_port': '9001',
                'debug_mode': 'false'
            },
            'Voice': {
                'language': 'ja-JP',
                'device': 'auto',
                'voice_threshold': '0.015',
                'energy_threshold': '0.01'
            },
            'Recording': {
                'max_speech_duration': '8.0',
                'min_speech_duration': '0.3',
                'silence_duration': '0.8',
                'sentence_pause_threshold': '0.5',
                'phrase_pause_threshold': '0.3',
                'chunk_size_ms': '100'
            },
            'Modes': {
                'use_fallback_mode': 'false',
                'disable_fallback_mode': 'true',
                'vrc_detection_timeout': '30.0'
            },
            'Interface': {
                'ui_language': 'zh',
                'window_width': '800',
                'window_height': '1000'
            },
            'Advanced': {
                'energy_drop_ratio': '0.3',
                'recent_energy_window': '10',
                'zero_crossing_threshold': '0.3',
                'recognition_interval': '1.0',
                'max_failures': '5'
            },
            'LLM': {
                'gemini_api_key': '',
                'gemini_model': 'gemini-1.5-flash',
                'enable_llm': 'false',
                'temperature': '0.7',
                'max_output_tokens': '2048',
                'conversation_history_length': '10',
                'system_prompt': '你是一个友善、有用的AI助手。请用简洁、自然的语言回复用户的问题。'
            },
            'AI_CHARACTER_VRC': {
                'ai_host': '127.0.0.1',
                'ai_send_port': '9002',
                'ai_receive_port': '9003',
                'auto_connect': 'false',
                'connection_timeout': '10',
                'last_character_name': '',
                'last_character_personality': 'friendly'
            },
            'VOICEVOX': {
                'last_period': '1期',
                'last_character': 'ずんだもん - ノーマル',
                'last_speaker_id': '',
                'last_speaker_name': '',
                'last_speaker_style': ''
            },
            'Runtime': {
                'mode': 'user',  # user: 用户端(支持语音识别), ai_remote: AI远端(仅支持语音输出)
                'disable_speech_recognition': 'false'  # 是否禁用语音识别
            }
        }
        
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
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
        self.config.clear()
        for section, options in self.default_config.items():
            self.config.add_section(section)
            for key, value in options.items():
                self.config.set(section, key, value)
        self.save_config()
    
    def _validate_config(self):
        """验证配置完整性"""
        modified = False
        
        for section, options in self.default_config.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                modified = True
            
            for key, default_value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, default_value)
                    modified = True
        
        if modified:
            self.save_config()
            print("[更新] 配置文件已更新至最新版本")
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"[保存] 配置已保存: {self.config_file}")
        except Exception as e:
            print(f"[错误] 保存配置失败: {e}")
    
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """获取配置值"""
        try:
            value = self.config.get(section, key)
            return self._convert_value(value)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            # 从默认配置获取
            if section in self.default_config and key in self.default_config[section]:
                return self._convert_value(self.default_config[section][key])
            return None
    
    def set(self, section: str, key: str, value: Any):
        """设置配置值"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        
        # 将值转换为字符串
        str_value = str(value).lower() if isinstance(value, bool) else str(value)
        self.config.set(section, key, str_value)
    
    def _convert_value(self, value: str) -> Any:
        """转换配置值类型"""
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        try:
            # 尝试转换为整数
            if '.' not in value:
                return int(value)
        except ValueError:
            pass
        
        try:
            # 尝试转换为浮点数
            return float(value)
        except ValueError:
            pass
        
        # 返回字符串
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取整个配置节"""
        if not self.config.has_section(section):
            return {}
        
        return {key: self.get(section, key) for key in self.config.options(section)}
    
    def update_section(self, section: str, values: Dict[str, Any]):
        """更新配置节"""
        for key, value in values.items():
            self.set(section, key, value)
    
    # 便捷方法：OSC配置
    @property
    def osc_host(self) -> str:
        return self.get('OSC', 'host')
    
    @property
    def osc_send_port(self) -> int:
        return self.get('OSC', 'send_port')
    
    @property
    def osc_receive_port(self) -> int:
        return self.get('OSC', 'receive_port')
    
    @property
    def osc_debug_mode(self) -> bool:
        return self.get('OSC', 'debug_mode')
    
    # 便捷方法：语音配置
    @property
    def voice_language(self) -> str:
        return self.get('Voice', 'language')
    
    @property
    def voice_device(self) -> str:
        return self.get('Voice', 'device')
    
    @property
    def voice_threshold(self) -> float:
        return self.get('Voice', 'voice_threshold')
    
    @property
    def energy_threshold(self) -> float:
        return self.get('Voice', 'energy_threshold')
    
    # 便捷方法：录制配置
    @property
    def max_speech_duration(self) -> float:
        return self.get('Recording', 'max_speech_duration')
    
    @property
    def min_speech_duration(self) -> float:
        return self.get('Recording', 'min_speech_duration')
    
    @property
    def silence_duration(self) -> float:
        return self.get('Recording', 'silence_duration')
    
    @property
    def sentence_pause_threshold(self) -> float:
        return self.get('Recording', 'sentence_pause_threshold')
    
    @property
    def phrase_pause_threshold(self) -> float:
        return self.get('Recording', 'phrase_pause_threshold')
    
    # 便捷方法：模式配置
    @property
    def use_fallback_mode(self) -> bool:
        return self.get('Modes', 'use_fallback_mode')
    
    @property
    def disable_fallback_mode(self) -> bool:
        return self.get('Modes', 'disable_fallback_mode')
    
    @property
    def vrc_detection_timeout(self) -> float:
        return self.get('Modes', 'vrc_detection_timeout')
    
    # 便捷方法：界面配置
    @property
    def ui_language(self) -> str:
        return self.get('Interface', 'ui_language')
    
    @property
    def window_width(self) -> int:
        return self.get('Interface', 'window_width')
    
    @property
    def window_height(self) -> int:
        return self.get('Interface', 'window_height')
    
    # 便捷方法：LLM配置
    @property
    def gemini_api_key(self) -> str:
        return self.get('LLM', 'gemini_api_key', '')
    
    @property
    def gemini_model(self) -> str:
        return self.get('LLM', 'gemini_model', 'gemini-1.5-flash')
    
    @property
    def enable_llm(self) -> bool:
        return self.get('LLM', 'enable_llm', False)
    
    @property
    def llm_temperature(self) -> float:
        return self.get('LLM', 'temperature', 0.7)
    
    @property
    def llm_max_output_tokens(self) -> int:
        return self.get('LLM', 'max_output_tokens', 2048)
    
    @property
    def llm_conversation_history_length(self) -> int:
        return self.get('LLM', 'conversation_history_length', 10)
    
    @property
    def llm_system_prompt(self) -> str:
        return self.get('LLM', 'system_prompt', '你是一个友善、有用的AI助手。请用简洁、自然的语言回复用户的问题。')
    
    # 便捷方法：AI角色VRC配置
    @property
    def ai_character_host(self) -> str:
        return self.get('AI_CHARACTER_VRC', 'ai_host')
    
    @property
    def ai_character_send_port(self) -> int:
        return self.get('AI_CHARACTER_VRC', 'ai_send_port')
    
    @property
    def ai_character_receive_port(self) -> int:
        return self.get('AI_CHARACTER_VRC', 'ai_receive_port')
    
    @property
    def ai_character_auto_connect(self) -> bool:
        return self.get('AI_CHARACTER_VRC', 'auto_connect')
    
    @property
    def ai_character_connection_timeout(self) -> int:
        return self.get('AI_CHARACTER_VRC', 'connection_timeout')
    
    @property
    def ai_character_last_name(self) -> str:
        return self.get('AI_CHARACTER_VRC', 'last_character_name')
    
    @property
    def ai_character_last_personality(self) -> str:
        return self.get('AI_CHARACTER_VRC', 'last_character_personality')
    
    def set_ai_character_host(self, host: str):
        """设置AI角色主机地址"""
        self.set('AI_CHARACTER_VRC', 'ai_host', host)
    
    def set_ai_character_ports(self, send_port: int, receive_port: int):
        """设置AI角色OSC端口"""
        self.set('AI_CHARACTER_VRC', 'ai_send_port', send_port)
        self.set('AI_CHARACTER_VRC', 'ai_receive_port', receive_port)
    
    def set_ai_character_last_info(self, name: str, personality: str):
        """保存最后使用的AI角色信息"""
        self.set('AI_CHARACTER_VRC', 'last_character_name', name)
        self.set('AI_CHARACTER_VRC', 'last_character_personality', personality)
    
    def set_ai_character_auto_connect(self, auto_connect: bool):
        """设置是否自动连接"""
        self.set('AI_CHARACTER_VRC', 'auto_connect', auto_connect)
    
    # 便捷方法：运行时配置
    @property
    def runtime_mode(self) -> str:
        """运行模式: user=用户端, ai_remote=AI远端"""
        return self.get('Runtime', 'mode', 'user')
    
    @property 
    def disable_speech_recognition(self) -> bool:
        """是否禁用语音识别"""
        return self.get('Runtime', 'disable_speech_recognition', False)
    
    def set_runtime_mode(self, mode: str):
        """设置运行模式"""
        self.set('Runtime', 'mode', mode)
    
    def set_disable_speech_recognition(self, disable: bool):
        """设置是否禁用语音识别"""
        self.set('Runtime', 'disable_speech_recognition', disable)
    
    # 便捷方法：VOICEVOX配置
    @property
    def voicevox_last_period(self) -> str:
        """获取上次选择的期数"""
        return self.get('VOICEVOX', 'last_period', '1期')
    
    @property
    def voicevox_last_character(self) -> str:
        """获取上次选择的角色"""
        return self.get('VOICEVOX', 'last_character', 'ずんだもん - ノーマル')
    
    @property
    def voicevox_last_speaker_id(self) -> str:
        """获取上次选择的说话人ID"""
        return self.get('VOICEVOX', 'last_speaker_id', '')
    
    @property
    def voicevox_last_speaker_name(self) -> str:
        """获取上次选择的说话人名称"""
        return self.get('VOICEVOX', 'last_speaker_name', '')
    
    @property
    def voicevox_last_speaker_style(self) -> str:
        """获取上次选择的说话人风格"""
        return self.get('VOICEVOX', 'last_speaker_style', '')
    
    def set_voicevox_last_selection(self, period: str, character: str, speaker_id: str = '', 
                                  speaker_name: str = '', speaker_style: str = ''):
        """保存VOICEVOX最后的选择"""
        self.set('VOICEVOX', 'last_period', period)
        self.set('VOICEVOX', 'last_character', character)
        self.set('VOICEVOX', 'last_speaker_id', speaker_id)
        self.set('VOICEVOX', 'last_speaker_name', speaker_name)
        self.set('VOICEVOX', 'last_speaker_style', speaker_style)


# 全局配置管理器实例
config_manager = ConfigManager()