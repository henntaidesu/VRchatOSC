#!/usr/bin/env python3
"""
语音识别引擎 - 纯后端逻辑，不包含UI代码
"""

import numpy as np
import sounddevice as sd
import whisper
import tempfile
import os
import soundfile as sf
from typing import Optional, Callable


class SpeechEngine:
    """语音识别引擎类 - 负责所有语音相关的处理"""
    
    def __init__(self, model_size: str = "base"):
        """
        初始化语音识别引擎
        
        Args:
            model_size: Whisper模型大小 ("tiny", "base", "small", "medium", "large")
        """
        self.whisper_model = None
        self.voice_threshold = 0.02  # 声音激活阈值
        self.model_size = model_size
        
        self._load_whisper_model()
    
    def _load_whisper_model(self):
        """加载Whisper模型"""
        try:
            print(f"正在加载Whisper模型 ({self.model_size})...")
            self.whisper_model = whisper.load_model(self.model_size)
            print("Whisper本地模型加载成功！")
            return True
        except Exception as e:
            print(f"Whisper模型加载失败: {e}")
            return False
    
    def is_model_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self.whisper_model is not None
    
    def set_voice_threshold(self, threshold: float):
        """设置语音激活阈值"""
        self.voice_threshold = threshold
    
    def detect_voice_activity(self, audio_data: np.ndarray) -> bool:
        """
        检测语音活动
        
        Args:
            audio_data: 音频数据
            
        Returns:
            是否检测到语音
        """
        try:
            # 计算音频的RMS能量
            rms_energy = np.sqrt(np.mean(audio_data ** 2))
            return rms_energy > self.voice_threshold
        except Exception as e:
            print(f"语音活动检测失败: {e}")
            return True
    
    def recognize_audio(self, audio_data: np.ndarray, sample_rate: int, language: str = None) -> Optional[str]:
        """
        识别音频数据
        
        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            language: 指定语言（可选）
            
        Returns:
            识别出的文本，失败返回None
        """
        try:
            if not self.whisper_model:
                return None
            
            # 创建临时音频文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                sf.write(temp_file.name, audio_data, sample_rate)
                temp_path = temp_file.name
            
            try:
                # 语言代码映射
                language_map = {
                    "zh-CN": "zh",
                    "ja-JP": "ja", 
                    "ja": "ja",
                    "en-US": "en",
                    "en": "en"
                }
                
                whisper_lang = None
                if language:
                    whisper_lang = language_map.get(language, language[:2])
                
                # 使用Whisper识别
                if whisper_lang:
                    result = self.whisper_model.transcribe(temp_path, language=whisper_lang)
                else:
                    result = self.whisper_model.transcribe(temp_path)
                
                text = result["text"].strip()
                
                if text:
                    return text
                else:
                    return None
                    
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"音频识别失败: {e}")
            return None
    
    def record_audio(self, duration: int = 5, sample_rate: int = 16000) -> Optional[np.ndarray]:
        """
        录制音频
        
        Args:
            duration: 录制时长（秒）
            sample_rate: 采样率
            
        Returns:
            音频数据数组，失败返回None
        """
        try:
            audio_data = sd.rec(int(duration * sample_rate), 
                              samplerate=sample_rate, 
                              channels=1, 
                              dtype=np.float32)
            sd.wait()
            return audio_data.flatten()
        except Exception as e:
            print(f"录制音频失败: {e}")
            return None