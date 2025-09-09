#!/usr/bin/env python3
"""
配置迁移脚本 - 将INI配置文件转换为JSON格式
"""

import configparser
import json
import os


def migrate_ini_to_json():
    """将INI配置迁移到JSON格式"""
    ini_file = "conf.ini"
    json_file = "config.json"
    
    if not os.path.exists(ini_file):
        print("没有找到conf.ini文件，无需迁移")
        return
    
    if os.path.exists(json_file):
        print("config.json已存在，跳过迁移")
        return
    
    # 读取INI配置
    config = configparser.ConfigParser()
    config.read(ini_file, encoding='utf-8')
    
    # 转换为JSON结构
    json_config = {
        "osc": {
            "host": config.get('OSC', 'host', fallback='127.0.0.1'),
            "send_port": config.getint('OSC', 'send_port', fallback=9000),
            "receive_port": config.getint('OSC', 'receive_port', fallback=9001),
            "debug_mode": config.getboolean('OSC', 'debug_mode', fallback=False),
            "enable_parameter_filtering": True,  # 默认启用
            "filtered_parameters": {}
        },
        "voice": {
            "language": config.get('Voice', 'language', fallback='ja-JP'),
            "device": config.get('Voice', 'device', fallback='auto'),
            "voice_threshold": config.getfloat('Voice', 'voice_threshold', fallback=0.015),
            "energy_threshold": config.getfloat('Voice', 'energy_threshold', fallback=0.01)
        },
        "recording": {
            "max_speech_duration": config.getfloat('Recording', 'max_speech_duration', fallback=8.0),
            "min_speech_duration": config.getfloat('Recording', 'min_speech_duration', fallback=0.3),
            "silence_duration": config.getfloat('Recording', 'silence_duration', fallback=0.8),
            "sentence_pause_threshold": config.getfloat('Recording', 'sentence_pause_threshold', fallback=0.5),
            "phrase_pause_threshold": config.getfloat('Recording', 'phrase_pause_threshold', fallback=0.3),
            "chunk_size_ms": config.getint('Recording', 'chunk_size_ms', fallback=100)
        },
        "modes": {
            "use_fallback_mode": config.getboolean('Modes', 'use_fallback_mode', fallback=False),
            "disable_fallback_mode": config.getboolean('Modes', 'disable_fallback_mode', fallback=True),
            "vrc_detection_timeout": config.getfloat('Modes', 'vrc_detection_timeout', fallback=30.0)
        },
        "interface": {
            "ui_language": config.get('Interface', 'ui_language', fallback='zh'),
            "window_width": config.getint('Interface', 'window_width', fallback=800),
            "window_height": config.getint('Interface', 'window_height', fallback=1000)
        },
        "advanced": {
            "energy_drop_ratio": config.getfloat('Advanced', 'energy_drop_ratio', fallback=0.3),
            "recent_energy_window": config.getint('Advanced', 'recent_energy_window', fallback=10),
            "zero_crossing_threshold": config.getfloat('Advanced', 'zero_crossing_threshold', fallback=0.3),
            "recognition_interval": config.getfloat('Advanced', 'recognition_interval', fallback=1.0),
            "max_failures": config.getint('Advanced', 'max_failures', fallback=5)
        },
        "llm": {
            "gemini_api_key": config.get('LLM', 'gemini_api_key', fallback=''),
            "gemini_model": config.get('LLM', 'gemini_model', fallback='gemini-2.5-flash'),
            "enable_llm": config.getboolean('LLM', 'enable_llm', fallback=False),
            "temperature": config.getfloat('LLM', 'temperature', fallback=0.7),
            "max_output_tokens": config.getint('LLM', 'max_output_tokens', fallback=2048),
            "conversation_history_length": config.getint('LLM', 'conversation_history_length', fallback=10),
            "system_prompt": config.get('LLM', 'system_prompt', fallback='')
        },
        "ai_character_vrc": {
            "ai_host": config.get('AI_CHARACTER_VRC', 'ai_host', fallback='127.0.0.1'),
            "ai_send_port": config.getint('AI_CHARACTER_VRC', 'ai_send_port', fallback=9000),
            "ai_receive_port": config.getint('AI_CHARACTER_VRC', 'ai_receive_port', fallback=9001),
            "auto_connect": config.getboolean('AI_CHARACTER_VRC', 'auto_connect', fallback=False),
            "connection_timeout": config.getint('AI_CHARACTER_VRC', 'connection_timeout', fallback=10),
            "last_character_name": config.get('AI_CHARACTER_VRC', 'last_character_name', fallback=''),
            "last_character_personality": config.get('AI_CHARACTER_VRC', 'last_character_personality', fallback='friendly')
        },
        "voicevox": {
            "host": config.get('VOICEVOX', 'host', fallback='localhost'),
            "port": config.getint('VOICEVOX', 'port', fallback=50021),
            "last_period": config.get('VOICEVOX', 'last_period', fallback='1期'),
            "last_character": config.get('VOICEVOX', 'last_character', fallback='春日部つむぎ'),
            "last_speaker_id": config.get('VOICEVOX', 'last_speaker_id', fallback='8'),
            "last_speaker_name": config.get('VOICEVOX', 'last_speaker_name', fallback='春日部つむぎ'),
            "last_speaker_style": config.get('VOICEVOX', 'last_speaker_style', fallback='ノーマル')
        },
        "runtime": {
            "mode": config.get('Runtime', 'mode', fallback='user'),
            "disable_speech_recognition": config.getboolean('Runtime', 'disable_speech_recognition', fallback=False)
        }
    }
    
    # 迁移OSC参数过滤配置
    filtered_params_str = config.get('Advanced', 'filtered_osc_parameters', fallback='')
    if filtered_params_str:
        filtered_param_names = [param.strip() for param in filtered_params_str.split(',') if param.strip()]
        
        # 预定义参数映射
        param_descriptions = {
            "AvatarVersion": "Avatar版本信息",
            "Grounded": "是否接地状态", 
            "InStation": "是否在Station中",
            "Seated": "是否坐着",
            "AFK": "是否挂机",
            "MuteSelf": "是否静音",
            "Earmuffs": "是否戴耳机",
            "AFKTimer": "挂机计时器",
            "Hips_SwimsuitGrab_Angle": "臀部泳装抓取角度",
            "Chest_SwimsuitGrab_Angle": "胸部泳装抓取角度",
            "GestureLeft": "左手手势",
            "GestureRight": "右手手势"
        }
        
        for param_name in filtered_param_names:
            json_config["osc"]["filtered_parameters"][param_name] = {
                "enabled": True,
                "description": param_descriptions.get(param_name, "自定义参数")
            }
    
    # 保存JSON配置
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_config, f, ensure_ascii=False, indent=2)
        print(f"配置迁移完成: {ini_file} -> {json_file}")
        
        # 备份原INI文件
        backup_file = f"{ini_file}.backup"
        os.rename(ini_file, backup_file)
        print(f"原配置文件已备份为: {backup_file}")
        
    except Exception as e:
        print(f"配置迁移失败: {e}")


if __name__ == "__main__":
    migrate_ini_to_json()