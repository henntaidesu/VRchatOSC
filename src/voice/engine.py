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
import threading
import queue
import time
import torch
from typing import Optional, Callable


class SpeechEngine:
    """语音识别引擎类 - 负责所有语音相关的处理"""
    
    def __init__(self, model_size: str = "medium", device: str = "auto"):
        """
        初始化语音识别引擎
        
        Args:
            model_size: Whisper模型大小 ("tiny", "base", "small", "medium", "large")
            device: 计算设备 ("auto", "cuda", "cpu")
        """
        self.whisper_model = None
        self.voice_threshold = 0.02  # 声音激活阈值
        self.model_size = model_size
        
        # GPU支持检查和设备选择
        self.device = self._detect_device(device)
        print(f"使用计算设备: {self.device}")
        
        # 动态录制相关参数
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = int(0.1 * self.sample_rate)  # 100ms chunks
        self.min_speech_duration = 0.5  # 最小语音持续时间(秒)
        self.max_speech_duration = 10.0  # 最大语音持续时间(秒)
        self.silence_duration = 1.0  # 静音持续时间后停止录制(秒)
        
        # 录制控制标志
        self.force_stop_recording = False
        
        self._load_whisper_model()
    
    def _detect_device(self, device: str) -> str:
        """检测和选择计算设备"""
        if device == "cpu":
            return "cpu"
        elif device == "cuda":
            if torch.cuda.is_available():
                return "cuda"
            else:
                print("警告: 请求使用CUDA但未检测到GPU支持，回退到CPU")
                return "cpu"
        elif device == "auto":
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                print(f"检测到GPU: {gpu_name} ({gpu_memory:.1f}GB)")
                return "cuda"
            else:
                print("未检测到CUDA支持，使用CPU进行推理")
                return "cpu"
        else:
            print(f"未知设备类型: {device}，使用自动检测")
            return self._detect_device("auto")
    
    def _load_whisper_model(self):
        """加载Whisper模型"""
        try:
            print(f"[1/3] 初始化Whisper模型 ({self.model_size})...")
            print(f"[2/3] 加载到设备: {self.device}")
            
            # 加载模型到指定设备
            if self.device == "cuda":
                print("[3/3] 配置GPU加速...")
                self.whisper_model = whisper.load_model(self.model_size, device="cuda")
                print("✓ Whisper GPU模型加载成功！")
            else:
                print("[3/3] 配置CPU模式...")
                self.whisper_model = whisper.load_model(self.model_size, device="cpu")
                print("✓ Whisper CPU模型加载成功！")
                
            return True
        except Exception as e:
            print(f"✗ Whisper模型加载失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_model_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self.whisper_model is not None
    
    def set_voice_threshold(self, threshold: float):
        """设置语音激活阈值"""
        self.voice_threshold = threshold
    
    def stop_recording(self):
        """强制停止当前录制"""
        self.force_stop_recording = True
        print("用户手动停止录制")
    
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
                print("Whisper模型未加载")
                return None
            
            print(f"开始识别音频，采样率: {sample_rate}, 语言: {language}")
            
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
                    print(f"使用语言代码: {whisper_lang}")
                
                # 配置推理选项
                transcribe_options = {
                    "fp16": self.device == "cuda",  # GPU时使用FP16加速
                    "verbose": False  # 减少输出
                }
                
                # 使用Whisper识别
                print(f"调用Whisper进行识别 (设备: {self.device}, FP16: {transcribe_options['fp16']})...")
                if whisper_lang:
                    result = self.whisper_model.transcribe(
                        temp_path, 
                        language=whisper_lang,
                        **transcribe_options
                    )
                else:
                    result = self.whisper_model.transcribe(
                        temp_path,
                        **transcribe_options
                    )
                
                text = result["text"].strip()
                print(f"Whisper识别结果: '{text}'")
                
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
            import traceback
            traceback.print_exc()
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
            print(f"开始录制音频，时长: {duration}秒, 采样率: {sample_rate}")
            audio_data = sd.rec(int(duration * sample_rate), 
                              samplerate=sample_rate, 
                              channels=1, 
                              dtype=np.float32)
            sd.wait()
            result = audio_data.flatten()
            print(f"录制完成，数据长度: {len(result)}, 最大值: {np.max(np.abs(result)):.4f}")
            return result
        except Exception as e:
            print(f"录制音频失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def record_audio_dynamic(self) -> Optional[np.ndarray]:
        """
        动态录制音频 - 自动检测语音开始和结束
        
        Returns:
            音频数据数组，失败返回None
        """
        try:
            print("开始动态语音录制...")
            
            # 重置强制停止标志
            self.force_stop_recording = False
            
            # 创建音频数据队列
            audio_queue = queue.Queue()
            recording = True
            
            def audio_callback(indata, frames, time, status):
                """音频输入回调函数"""
                if status:
                    print(f"音频输入状态: {status}")
                if recording:
                    audio_queue.put(indata.copy())
            
            # 开始音频流
            with sd.InputStream(callback=audio_callback,
                              channels=self.channels,
                              samplerate=self.sample_rate,
                              blocksize=self.chunk_size,
                              dtype=np.float32):
                
                audio_chunks = []
                speech_started = False
                silence_chunks = 0
                speech_chunks = 0
                max_chunks = int(self.max_speech_duration * self.sample_rate / self.chunk_size)
                silence_threshold = int(self.silence_duration * self.sample_rate / self.chunk_size)
                min_speech_chunks = int(self.min_speech_duration * self.sample_rate / self.chunk_size)
                
                print("等待语音输入...")
                
                while recording and len(audio_chunks) < max_chunks:
                    try:
                        # 检查强制停止信号
                        if self.force_stop_recording:
                            print("收到停止录制信号，结束录制")
                            break
                        
                        # 获取音频块
                        chunk = audio_queue.get(timeout=0.1)
                        chunk_flat = chunk.flatten()
                        
                        # 检测语音活动
                        has_voice = self.detect_voice_activity(chunk_flat)
                        
                        if has_voice:
                            if not speech_started:
                                print("检测到语音活动，开始录制...")
                                speech_started = True
                            silence_chunks = 0
                            speech_chunks += 1
                            # 显示录制进度
                            if speech_chunks % 10 == 0:  # 每1秒显示一次
                                print(f"录制中... ({speech_chunks * 0.1:.1f}秒)")
                        else:
                            if speech_started:
                                silence_chunks += 1
                                # 显示静音检测
                                if silence_chunks == 1:
                                    print("检测到静音，等待语音结束确认...")
                        
                        # 如果已经开始说话，保存音频块
                        if speech_started:
                            audio_chunks.append(chunk_flat)
                            
                            # 如果静音超过阈值且已有足够的语音，停止录制
                            if silence_chunks >= silence_threshold and speech_chunks >= min_speech_chunks:
                                print("检测到语音结束，停止录制")
                                break
                                
                    except queue.Empty:
                        # 如果没有新的音频数据，继续等待
                        if not speech_started:
                            continue
                        else:
                            # 如果已经开始录制但长时间没有音频数据，停止
                            silence_chunks += 1
                            if silence_chunks >= silence_threshold:
                                break
                
                recording = False
                
                if not audio_chunks:
                    print("未录制到音频数据")
                    return None
                
                # 合并所有音频块
                audio_data = np.concatenate(audio_chunks)
                print(f"录制完成，总时长: {len(audio_data)/self.sample_rate:.2f}秒")
                
                return audio_data
                
        except Exception as e:
            print(f"动态录制音频失败: {e}")
            import traceback
            traceback.print_exc()
            return None