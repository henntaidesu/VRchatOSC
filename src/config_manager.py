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
                'window_height': '900'
            },
            'Advanced': {
                'energy_drop_ratio': '0.3',
                'recent_energy_window': '10',
                'zero_crossing_threshold': '0.3',
                'recognition_interval': '1.0',
                'max_failures': '5'
            }
        }
        
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
                print(f"✅ 已加载配置文件: {self.config_file}")
                self._validate_config()
            except Exception as e:
                print(f"⚠️ 加载配置文件失败: {e}")
                self._create_default_config()
        else:
            print(f"📁 配置文件不存在，创建默认配置: {self.config_file}")
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
            print("🔧 配置文件已更新至最新版本")
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"💾 配置已保存: {self.config_file}")
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
    
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


# 全局配置管理器实例
config_manager = ConfigManager()