#!/usr/bin/env python3
"""
虚拟麦克风模块 - 将音频输出到指定的音频设备
"""

import os
import time
import numpy as np
import soundfile as sf
from typing import Optional, List, Dict


class VirtualMicrophone:
    """虚拟麦克风管理器"""
    
    def __init__(self):
        """初始化虚拟麦克风"""
        self.current_device = None
        self.available_devices = []
        self.update_device_list()
        
    def update_device_list(self):
        """更新可用音频设备列表"""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            self.available_devices = []
            
            for i, device in enumerate(devices):
                if device['max_output_channels'] > 0:  # 输出设备
                    self.available_devices.append({
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_output_channels'],
                        'sample_rate': device['default_samplerate']
                    })
            
            print(f"找到 {len(self.available_devices)} 个音频输出设备")
            
        except ImportError:
            print("警告: sounddevice未安装，将使用备选方案")
            self.available_devices = []
        except Exception as e:
            print(f"获取音频设备列表失败: {e}")
            self.available_devices = []
    
    def list_devices(self) -> List[Dict]:
        """获取可用设备列表"""
        return self.available_devices
    
    def find_virtual_cable_device(self) -> Optional[int]:
        """寻找VB-Audio Virtual Cable设备"""
        virtual_keywords = [
            'CABLE Input', 'VB-Audio', 'Virtual Audio Cable',
            'VoiceMeeter Input', 'Microphone (VB-Audio'
        ]
        
        for device in self.available_devices:
            device_name = device['name'].lower()
            for keyword in virtual_keywords:
                if keyword.lower() in device_name:
                    print(f"找到虚拟音频设备: {device['name']} (ID: {device['id']})")
                    return device['id']
        
        print("未找到虚拟音频设备")
        return None
    
    def play_audio_to_device(self, file_path: str, device_id: Optional[int] = None, volume: float = 1.0) -> bool:
        """播放音频到指定设备"""
        try:
            import sounddevice as sd
            
            # 读取音频文件
            if not os.path.exists(file_path):
                print(f"音频文件不存在: {file_path}")
                return False
            
            data, sample_rate = sf.read(file_path)
            
            # 调整音量
            if volume != 1.0:
                data = data * volume
            
            # 自动寻找虚拟设备
            if device_id is None:
                device_id = self.find_virtual_cable_device()
            
            # 播放音频
            if device_id is not None:
                print(f"播放音频到设备 {device_id}: {file_path}")
                sd.play(data, sample_rate, device=device_id)
                sd.wait()  # 等待播放完成
                print("音频播放完成")
            else:
                print("播放音频到默认设备")
                sd.play(data, sample_rate)
                sd.wait()
            
            return True
            
        except ImportError:
            print("sounddevice未安装，尝试使用pygame备选方案")
            return self._play_with_pygame(file_path)
        except Exception as e:
            print(f"播放音频失败: {e}")
            return self._play_with_pygame(file_path)
    
    def _play_with_pygame(self, file_path: str) -> bool:
        """使用pygame作为备选播放方案"""
        try:
            import pygame
            
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            # 等待前一个音频完成
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # 估算播放时长并等待
            try:
                data, sample_rate = sf.read(file_path)
                duration = len(data) / sample_rate
                time.sleep(duration)
            except:
                time.sleep(3)  # 默认等待3秒
            
            print("pygame音频播放完成")
            return True
            
        except Exception as e:
            print(f"pygame播放也失败: {e}")
            return False
    
    def play_audio_with_mic_simulation(self, file_path: str) -> bool:
        """模拟麦克风输入播放音频"""
        print("🎤 模拟麦克风输入模式")
        print("📝 请按以下步骤设置:")
        print("   1. 安装 VB-Audio Virtual Cable")
        print("   2. 在VRChat中设置麦克风为 'CABLE Output'")
        print("   3. 本程序将音频输出到 'CABLE Input'")
        print("   4. VRChat将从 'CABLE Output' 接收音频")
        
        # 尝试找到CABLE Input设备
        cable_device = self.find_virtual_cable_device()
        
        return self.play_audio_to_device(file_path, cable_device, volume=0.8)
    


# 创建全局实例
virtual_microphone = VirtualMicrophone()