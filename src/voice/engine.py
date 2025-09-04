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
    
    def __init__(self, model_size: str = "medium", device: str = "auto", config=None):
        """
        初始化语音识别引擎
        
        Args:
            model_size: Whisper模型大小 ("tiny", "base", "small", "medium", "large")
            device: 计算设备 ("auto", "cuda", "cpu")
            config: 配置管理器实例
        """
        self.config = config
        self.whisper_model = None
        self.model_size = model_size
        
        # GPU支持检查和设备选择
        self.device = self._detect_device(device)
        print(f"使用计算设备: {self.device}")
        
        # 从配置文件加载参数（如果有配置）
        if self.config:
            self.voice_threshold = self.config.voice_threshold
            self.energy_threshold = self.config.energy_threshold
            self.max_speech_duration = self.config.max_speech_duration
            self.min_speech_duration = self.config.min_speech_duration
            self.silence_duration = self.config.silence_duration
            self.sentence_pause_threshold = self.config.sentence_pause_threshold
            self.phrase_pause_threshold = self.config.phrase_pause_threshold
            self.energy_drop_ratio = self.config.get('Advanced', 'energy_drop_ratio')
            self.recent_energy_window = self.config.get('Advanced', 'recent_energy_window')
            self.zero_crossing_threshold = self.config.get('Advanced', 'zero_crossing_threshold')
        else:
            # 默认参数（向后兼容）
            self.voice_threshold = 0.015
            self.energy_threshold = 0.01
            self.max_speech_duration = 8.0
            self.min_speech_duration = 0.3
            self.silence_duration = 0.8
            self.sentence_pause_threshold = 0.5
            self.phrase_pause_threshold = 0.3
            self.energy_drop_ratio = 0.3
            self.recent_energy_window = 10
            self.zero_crossing_threshold = 0.3
        
        # 固定参数
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = int(0.1 * self.sample_rate)  # 100ms chunks
        
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
        self.energy_threshold = threshold * 0.7  # 能量阈值相应调整
    
    def set_sentence_pause_threshold(self, threshold: float):
        """设置句子间停顿阈值"""
        self.sentence_pause_threshold = threshold
        self.phrase_pause_threshold = threshold * 0.6  # 短语停顿阈值相应调整
        self.silence_duration = threshold + 0.3  # 静音检测时间调整
    
    def stop_recording(self):
        """强制停止当前录制"""
        self.force_stop_recording = True
        print("用户手动停止录制")
    
    def detect_sentence_boundary(self, recent_energy_levels: list, silence_chunks: int, speech_chunks: int) -> tuple:
        """
        检测句子边界和断句
        
        Args:
            recent_energy_levels: 最近的能量级别列表
            silence_chunks: 连续静音块数
            speech_chunks: 总语音块数
            
        Returns:
            (is_sentence_end, is_phrase_end, confidence)
        """
        try:
            if len(recent_energy_levels) < 5:
                return False, False, 0.0
            
            # 计算当前静音时长
            silence_duration = silence_chunks * 0.1  # 每块0.1秒
            speech_duration = speech_chunks * 0.1
            
            # 判断是否是句子结束
            is_sentence_end = (
                silence_duration >= self.sentence_pause_threshold and 
                speech_duration >= 1.0  # 至少说话1秒
            )
            
            # 判断是否是短语结束
            is_phrase_end = (
                silence_duration >= self.phrase_pause_threshold and 
                speech_duration >= 0.5  # 至少说话0.5秒
            )
            
            # 计算能量下降程度
            if len(recent_energy_levels) >= self.recent_energy_window:
                recent_avg = np.mean(recent_energy_levels[-5:])  # 最近5个块的平均
                earlier_avg = np.mean(recent_energy_levels[-self.recent_energy_window:-5])  # 更早的平均
                
                energy_drop = (earlier_avg - recent_avg) / earlier_avg if earlier_avg > 0 else 0
                energy_confidence = min(energy_drop / self.energy_drop_ratio, 1.0)
            else:
                energy_confidence = 0.5
            
            # 基于时长的置信度
            time_confidence = min(silence_duration / self.sentence_pause_threshold, 1.0)
            
            # 综合置信度
            confidence = (energy_confidence * 0.3 + time_confidence * 0.7)
            
            return is_sentence_end, is_phrase_end, confidence
            
        except Exception as e:
            print(f"断句检测错误: {e}")
            return False, False, 0.0
    
    def detect_voice_activity(self, audio_data: np.ndarray) -> bool:
        """
        检测语音活动 - 使用多种指标进行判断
        
        Args:
            audio_data: 音频数据
            
        Returns:
            是否检测到语音
        """
        try:
            if len(audio_data) == 0:
                return False
            
            # 1. 计算RMS能量
            rms_energy = np.sqrt(np.mean(audio_data ** 2))
            
            # 2. 计算过零率 (Zero Crossing Rate)
            zero_crossings = np.sum(np.diff(np.sign(audio_data)) != 0)
            zero_crossing_rate = zero_crossings / len(audio_data)
            
            # 3. 计算最大幅值
            max_amplitude = np.max(np.abs(audio_data))
            
            # 4. 计算频谱能量集中度
            fft = np.fft.fft(audio_data)
            magnitude_spectrum = np.abs(fft[:len(fft)//2])
            spectral_energy = np.sum(magnitude_spectrum)
            
            # 多重判断条件
            energy_check = rms_energy > self.energy_threshold
            amplitude_check = max_amplitude > self.voice_threshold
            zcr_check = zero_crossing_rate > 0.01  # 防止纯噪音
            spectral_check = spectral_energy > 1.0  # 频谱能量检查
            
            # 至少满足两个条件才认为是语音
            checks_passed = sum([energy_check, amplitude_check, zcr_check, spectral_check])
            has_voice = checks_passed >= 2
            
            # 调试输出
            if not has_voice:
                print(f"语音检测: RMS={rms_energy:.4f}, Max={max_amplitude:.4f}, ZCR={zero_crossing_rate:.4f}, "
                      f"通过检查: {checks_passed}/4")
            
            return has_voice
            
        except Exception as e:
            print(f"语音活动检测失败: {e}")
            return True  # 出错时默认认为有语音
    
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
                
                # 断句检测相关变量
                recent_energy_levels = []
                last_sentence_end_time = 0
                sentence_boundary_detected = False
                
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
                        
                        # 计算并记录能量级别用于断句检测
                        rms_energy = np.sqrt(np.mean(chunk_flat ** 2))
                        recent_energy_levels.append(rms_energy)
                        if len(recent_energy_levels) > self.recent_energy_window * 2:
                            recent_energy_levels.pop(0)  # 保持窗口大小
                        
                        if has_voice:
                            if not speech_started:
                                print("检测到语音活动，开始录制...")
                                speech_started = True
                            silence_chunks = 0
                            speech_chunks += 1
                            # 显示录制进度 (减少频率避免刷屏)
                            if speech_chunks % 20 == 0:  # 每2秒显示一次
                                print(f"录制中... ({speech_chunks * 0.1:.1f}秒)")
                        else:
                            if speech_started:
                                silence_chunks += 1
                                # 只在刚开始静音时提示一次
                                if silence_chunks == 1:
                                    print("检测到静音，分析是否为断句...")
                        
                        # 如果已经开始说话，保存音频块并检测断句
                        if speech_started:
                            audio_chunks.append(chunk_flat)
                            
                            # 进行断句检测
                            is_sentence_end, is_phrase_end, confidence = self.detect_sentence_boundary(
                                recent_energy_levels, silence_chunks, speech_chunks
                            )
                            
                            # 断句反馈
                            if is_sentence_end and confidence > 0.7:
                                print(f"检测到句子结束 (置信度: {confidence:.2f})")
                                sentence_boundary_detected = True
                            elif is_phrase_end and confidence > 0.6:
                                print(f"检测到短语停顿 (置信度: {confidence:.2f})")
                            
                            # 决定是否停止录制
                            should_stop = False
                            stop_reason = ""
                            
                            # 1. 检测到明确的句子边界
                            if sentence_boundary_detected and speech_chunks >= min_speech_chunks:
                                should_stop = True
                                stop_reason = "句子边界"
                            
                            # 2. 基于静音时长的停止条件
                            elif silence_chunks >= silence_threshold and speech_chunks >= min_speech_chunks:
                                should_stop = True
                                stop_reason = "静音超时"
                            
                            # 3. 达到最大录制时长
                            elif speech_chunks >= max_chunks * 0.8:  # 80%最大时长
                                should_stop = True
                                stop_reason = "达到最大时长"
                            
                            if should_stop:
                                speech_duration = speech_chunks * 0.1
                                silence_duration = silence_chunks * 0.1
                                print(f"录制结束 - {stop_reason} (语音:{speech_duration:.1f}s, 静音:{silence_duration:.1f}s)")
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