#!/usr/bin/env python3
"""
VRC动态语音处理器 - 基于VRChat麦克风状态进行动态录音和语音识别
"""

import threading
import queue
import time
import numpy as np
import sounddevice as sd
import tempfile
import os
import soundfile as sf
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

from ..voice.engine import SpeechEngine
from .voice_llm_handler import VoiceLLMHandler


class RecordingState(Enum):
    """录音状态枚举"""
    IDLE = "idle"
    WAITING_FOR_VRC_MIC = "waiting_for_vrc_mic"
    RECORDING = "recording"
    PROCESSING = "processing"


@dataclass
class VRCVoiceEvent:
    """VRC语音事件数据"""
    event_type: str  # "mic_opened", "mic_closed", "speaking_started", "speaking_stopped"
    timestamp: float
    vrc_speaking_state: bool
    voice_level: float = 0.0
    

class VRCDynamicVoiceProcessor:
    """VRC动态语音处理器"""
    
    def __init__(self, config=None):
        """
        初始化VRC动态语音处理器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        
        # 语音引擎和LLM处理器
        self.speech_engine: Optional[SpeechEngine] = None
        self.llm_handler: Optional[VoiceLLMHandler] = None
        
        # VRC状态监听
        self.vrc_speaking_state = False
        self.vrc_voice_level = 0.0
        self.last_vrc_state_change = 0.0
        
        # 录音状态
        self.recording_state = RecordingState.IDLE
        self.is_recording = False
        self.audio_stream = None
        self.audio_chunks = []
        self.recording_start_time = 0.0
        
        # 音频参数
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = int(0.1 * self.sample_rate)  # 100ms chunks
        
        # 处理队列和线程
        self.event_queue = queue.Queue()
        self.processing_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # 回调函数
        self.speech_result_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        
        # 录音控制参数
        self.min_recording_duration = 0.5  # 最小录音时长（秒）
        self.max_recording_duration = 30.0  # 最大录音时长（秒）
        self.silence_timeout = 2.0  # 静音超时时间（秒）
        
        # 语音片段累积功能
        self.speech_segments = []  # 存储当前会话的所有语音片段
        self.session_start_time = None  # 会话开始时间
        self.last_speech_time = None  # 最后一次语音的时间
        self.session_timeout = 5.0  # 会话超时时间(秒)，超过此时间未说话则发送累积的语音
        self.enable_speech_accumulation = True  # 是否启用语音累积功能
        
        # 识别完成状态跟踪
        self.pending_recognition = False  # 是否有待处理的语音识别
        self.mic_closed_waiting_recognition = False  # 麦克风已关闭，等待最后识别完成
        
        print("[初始化] VRC动态语音处理器初始化完成")
    
    def set_speech_engine(self, speech_engine: SpeechEngine):
        """设置语音识别引擎"""
        self.speech_engine = speech_engine
        print("[配置] 语音识别引擎已设置")
    
    def set_llm_handler(self, llm_handler: VoiceLLMHandler):
        """设置LLM处理器"""
        self.llm_handler = llm_handler
        print("[配置] LLM处理器已设置")
    
    def set_speech_result_callback(self, callback: Callable):
        """设置语音识别结果回调"""
        self.speech_result_callback = callback
        print("[配置] 语音识别结果回调已设置")
    
    def set_status_callback(self, callback: Callable):
        """设置状态变化回调"""
        self.status_callback = callback
        print("[配置] 状态变化回调已设置")
    
    def start_processing(self):
        """启动处理器"""
        if self.is_running:
            print("[警告] 处理器已在运行")
            return
        
        if not self.speech_engine:
            print("[错误] 未设置语音识别引擎")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        print("[启动] VRC动态语音处理器已启动")
    
    def stop_processing(self):
        """停止处理器"""
        if not self.is_running:
            return
        
        # 发送剩余的累积语音片段
        if self.speech_segments:
            print("[停止] 发送剩余的累积语音片段")
            self._send_accumulated_speech()
        
        self.is_running = False
        self._stop_recording()
        
        if self.processing_thread:
            self.processing_thread.join(timeout=3.0)
        
        print("[停止] VRC动态语音处理器已停止")
    
    def on_vrc_speaking_state_changed(self, speaking_state: bool, voice_level: float = 0.0):
        """
        VRC麦克风状态变化回调
        
        Args:
            speaking_state: VRC麦克风状态（True=开启，False=关闭）
            voice_level: 语音强度级别
        """
        current_time = time.time()
        
        # 创建事件
        if speaking_state != self.vrc_speaking_state:
            event_type = "mic_opened" if speaking_state else "mic_closed"
            event = VRCVoiceEvent(
                event_type=event_type,
                timestamp=current_time,
                vrc_speaking_state=speaking_state,
                voice_level=voice_level
            )
            
            # 更新状态
            self.vrc_speaking_state = speaking_state
            self.vrc_voice_level = voice_level
            self.last_vrc_state_change = current_time
            
            # 添加事件到队列
            try:
                self.event_queue.put(event, timeout=0.1)
                print(f"[VRC状态] {event_type} - 语音状态: {speaking_state}, 强度: {voice_level:.3f}")
            except queue.Full:
                print("[错误] 事件队列已满，跳过事件")
        else:
            # 只是强度变化，更新数值
            self.vrc_voice_level = voice_level
    
    def _processing_loop(self):
        """处理循环"""
        while self.is_running:
            try:
                # 处理事件队列
                try:
                    event = self.event_queue.get(timeout=0.5)
                    self._handle_vrc_event(event)
                    self.event_queue.task_done()
                except queue.Empty:
                    # 检查录音超时
                    self._check_recording_timeout()
                    # 语音累积超时检查已禁用，只在麦克风关闭时发送
                    # self._check_speech_session_timeout()
                    continue
                
            except Exception as e:
                print(f"[错误] 处理循环异常: {e}")
                import traceback
                traceback.print_exc()
    
    def _handle_vrc_event(self, event: VRCVoiceEvent):
        """处理VRC事件"""
        try:
            if event.event_type == "mic_opened":
                self._handle_mic_opened(event)
            elif event.event_type == "mic_closed":
                self._handle_mic_closed(event)
            
            # 通知状态变化
            if self.status_callback:
                self.status_callback(event.event_type, {
                    'recording_state': self.recording_state.value,
                    'vrc_speaking_state': event.vrc_speaking_state,
                    'voice_level': event.voice_level,
                    'timestamp': event.timestamp
                })
                
        except Exception as e:
            print(f"[错误] 处理VRC事件失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_mic_opened(self, event: VRCVoiceEvent):
        """处理VRC麦克风开启"""
        print(f"[检测] VRC麦克风开启")
        
        # 清除麦克风关闭等待状态
        self.mic_closed_waiting_recognition = False
        
        if self.recording_state == RecordingState.IDLE:
            self._start_recording()
        elif self.recording_state == RecordingState.RECORDING:
            print("[状态] 已在录音中，继续录音")
    
    def _handle_mic_closed(self, event: VRCVoiceEvent):
        """处理VRC麦克风关闭"""
        print(f"[检测] VRC麦克风关闭")
        
        if self.recording_state == RecordingState.RECORDING:
            # 检查录音时长
            recording_duration = time.time() - self.recording_start_time
            if recording_duration >= self.min_recording_duration:
                print(f"[录音] 达到最小时长 ({recording_duration:.2f}s)，停止录音并处理")
                self._stop_recording_and_process()
            else:
                print(f"[录音] 录音时长过短 ({recording_duration:.2f}s < {self.min_recording_duration}s)，取消录音")
                self._cancel_recording()
        
        # 关键修改：麦克风关闭时标记等待最后识别完成
        if self.enable_speech_accumulation:
            if self.pending_recognition:
                # 如果还有识别任务在处理，标记等待
                self.mic_closed_waiting_recognition = True
                print(f"[麦克风关闭] 等待最后一次识别完成，然后发送累积的{len(self.speech_segments)}个语音片段")
            elif self.speech_segments:
                # 没有待处理识别，立即发送
                print(f"[麦克风关闭] 立即发送累积的{len(self.speech_segments)}个语音片段")
                self._send_accumulated_speech()
            else:
                print(f"[麦克风关闭] 没有累积的语音片段")
    
    def _start_recording(self):
        """开始录音"""
        try:
            if self.is_recording:
                print("[警告] 已在录音中")
                return
            
            print("[录音] 开始录音...")
            self.recording_state = RecordingState.RECORDING
            self.is_recording = True
            self.audio_chunks = []
            self.recording_start_time = time.time()
            
            # 创建音频流
            def audio_callback(indata, frames, time, status):
                if status:
                    print(f"[音频] 状态: {status}")
                if self.is_recording:
                    self.audio_chunks.append(indata.copy())
            
            self.audio_stream = sd.InputStream(
                callback=audio_callback,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                dtype=np.float32
            )
            
            self.audio_stream.start()
            print("[录音] 录音已启动")
            
        except Exception as e:
            print(f"[错误] 启动录音失败: {e}")
            self.recording_state = RecordingState.IDLE
            self.is_recording = False
            import traceback
            traceback.print_exc()
    
    def _stop_recording(self):
        """停止录音（不处理）"""
        if self.audio_stream and self.is_recording:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None
                self.is_recording = False
                print("[录音] 录音已停止")
            except Exception as e:
                print(f"[错误] 停止录音失败: {e}")
    
    def _stop_recording_and_process(self):
        """停止录音并处理语音识别"""
        try:
            # 停止录音
            self._stop_recording()
            
            if not self.audio_chunks:
                print("[警告] 没有录音数据")
                self.recording_state = RecordingState.IDLE
                return
            
            self.recording_state = RecordingState.PROCESSING
            
            # 合并音频数据
            audio_data = np.concatenate([chunk.flatten() for chunk in self.audio_chunks])
            recording_duration = len(audio_data) / self.sample_rate
            
            print(f"[处理] 开始处理录音，时长: {recording_duration:.2f}秒")
            
            # 标记开始识别处理
            self.pending_recognition = True
            
            # 异步处理语音识别
            processing_thread = threading.Thread(
                target=self._process_audio_async,
                args=(audio_data, recording_duration),
                daemon=True
            )
            processing_thread.start()
            
        except Exception as e:
            print(f"[错误] 处理录音失败: {e}")
            self.recording_state = RecordingState.IDLE
            import traceback
            traceback.print_exc()
    
    def _cancel_recording(self):
        """取消录音"""
        self._stop_recording()
        self.audio_chunks = []
        self.recording_state = RecordingState.IDLE
        print("[录音] 录音已取消")
    
    def _process_audio_async(self, audio_data: np.ndarray, duration: float):
        """异步处理音频识别"""
        try:
            print(f"[识别] 开始语音识别，音频时长: {duration:.2f}秒")
            
            # 语音识别
            if self.speech_engine and self.speech_engine.is_model_loaded():
                # 检测语音活动
                has_voice = self.speech_engine.detect_voice_activity(audio_data)
                
                if not has_voice:
                    print("[识别] 未检测到语音活动，跳过识别")
                    self.recording_state = RecordingState.IDLE
                    return
                
                # 进行语音识别，传递语言配置
                from ..config_manager import config_manager
                language = config_manager.voice_language
                recognized_text = self.speech_engine.recognize_audio(
                    audio_data, 
                    self.sample_rate,
                    language
                )
                
                if recognized_text and recognized_text.strip():
                    print(f"[识别] 识别结果: {recognized_text}")
                    
                    # 调用结果回调
                    if self.speech_result_callback:
                        self.speech_result_callback(recognized_text, {
                            'duration': duration,
                            'trigger': 'vrc_mic_closed',
                            'timestamp': time.time()
                        })
                    
                    # 处理语音片段累积
                    if self.enable_speech_accumulation:
                        self._add_speech_segment(recognized_text)
                        
                        # 检查是否需要发送累积语音（麦克风已关闭且这是最后一次识别）
                        if self.mic_closed_waiting_recognition:
                            print(f"[识别完成] 最后一次识别完成，发送累积的{len(self.speech_segments)}个语音片段")
                            self._send_accumulated_speech()
                            self.mic_closed_waiting_recognition = False
                    else:
                        # 直接提交到LLM处理（原始行为）
                        if self.llm_handler:
                            self.llm_handler.submit_voice_text(recognized_text)
                else:
                    print("[识别] 未识别出文本内容")
            else:
                print("[错误] 语音识别引擎未就绪")
            
        except Exception as e:
            print(f"[错误] 异步语音处理失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 清除识别处理标志
            self.pending_recognition = False
            
            # 如果麦克风已关闭且在等待识别完成，且没有识别出文本，仍需检查是否发送累积语音
            if self.mic_closed_waiting_recognition and self.enable_speech_accumulation and self.speech_segments:
                print(f"[识别完成] 识别未产生文本，但发送已有的累积语音片段")
                self._send_accumulated_speech()
                self.mic_closed_waiting_recognition = False
            
            self.recording_state = RecordingState.IDLE
            print("[状态] 处理完成，回到空闲状态")
    
    def _check_recording_timeout(self):
        """检查录音超时"""
        if (self.recording_state == RecordingState.RECORDING and 
            self.recording_start_time > 0):
            
            recording_duration = time.time() - self.recording_start_time
            
            if recording_duration >= self.max_recording_duration:
                print(f"[超时] 录音时长达到上限 ({recording_duration:.2f}s)，强制停止")
                self._stop_recording_and_process()
    
    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        return {
            'is_running': self.is_running,
            'recording_state': self.recording_state.value,
            'is_recording': self.is_recording,
            'vrc_speaking_state': self.vrc_speaking_state,
            'vrc_voice_level': self.vrc_voice_level,
            'audio_chunks_count': len(self.audio_chunks),
            'recording_duration': (time.time() - self.recording_start_time) if self.recording_start_time > 0 else 0.0,
            'engines_ready': {
                'speech_engine': self.speech_engine is not None and self.speech_engine.is_model_loaded(),
                'llm_handler': self.llm_handler is not None and self.llm_handler.is_client_ready()
            }
        }
    
    def force_stop_recording(self):
        """强制停止当前录音"""
        if self.recording_state == RecordingState.RECORDING:
            print("[强制] 用户强制停止录音")
            recording_duration = time.time() - self.recording_start_time
            if recording_duration >= self.min_recording_duration:
                self._stop_recording_and_process()
            else:
                self._cancel_recording()
        else:
            print("[状态] 当前未在录音")
    
    def set_recording_parameters(self, min_duration: float = None, max_duration: float = None, 
                               silence_timeout: float = None):
        """设置录音参数"""
        if min_duration is not None:
            self.min_recording_duration = min_duration
        if max_duration is not None:
            self.max_recording_duration = max_duration
        if silence_timeout is not None:
            self.silence_timeout = silence_timeout
        
        print(f"[配置] 录音参数已更新: min={self.min_recording_duration}s, "
              f"max={self.max_recording_duration}s, silence_timeout={self.silence_timeout}s")
    
    def _add_speech_segment(self, text: str):
        """添加语音片段到累积列表"""
        current_time = time.time()
        
        # 如果是新会话的开始（没有累积片段或麦克风已关闭很久）
        if not self.speech_segments:
            self.session_start_time = current_time
            print(f"[新会话] 开始新的语音累积会话")
        
        # 添加当前语音片段
        self.speech_segments.append({
            'text': text,
            'timestamp': current_time
        })
        # 不更新 last_speech_time，避免触发超时机制
        # self.last_speech_time = current_time
        
        print(f"[累积] 语音片段已添加: {text[:30]}... (共{len(self.speech_segments)}个片段)")
        print(f"[累积状态] 等待麦克风关闭信号以发送累积语音")
    
    def _check_speech_session_timeout(self):
        """检查语音累积会话是否超时（已禁用，只在麦克风关闭时发送）"""
        # 完全禁用基于时间的自动发送机制
        # 只在麦克风关闭时发送累积语音，确保完整性
        pass
    
    def _send_accumulated_speech(self):
        """发送累积的语音片段到LLM"""
        if not self.speech_segments:
            return
        
        # 合并所有语音片段
        combined_text = " ".join([segment['text'] for segment in self.speech_segments])
        
        print(f"[累积发送] 合并{len(self.speech_segments)}个语音片段: {combined_text[:100]}...")
        
        # 发送到LLM处理
        if self.llm_handler:
            self.llm_handler.submit_voice_text(combined_text)
        
        # 清空累积列表
        self.speech_segments = []
        self.session_start_time = None
        print(f"[累积发送] 语音片段已发送并清空缓存")
    
    def set_speech_accumulation_enabled(self, enabled: bool):
        """设置语音累积功能开关"""
        self.enable_speech_accumulation = enabled
        if not enabled and self.speech_segments:
            # 如果禁用累积功能时还有未发送的语音，立即发送
            self._send_accumulated_speech()
        print(f"[配置] 语音累积功能已{'启用' if enabled else '禁用'}")
    
    def set_session_timeout(self, timeout: float):
        """设置会话超时时间（现在主要用作安全机制）"""
        self.session_timeout = timeout
        print(f"[配置] 安全超时时间设为{timeout}秒（2倍值用作强制发送阈值）")
    
    def force_send_accumulated_speech(self):
        """强制发送当前累积的语音片段"""
        if self.speech_segments:
            print(f"[强制发送] 手动发送累积的语音片段")
            self._send_accumulated_speech()
        else:
            print(f"[强制发送] 没有累积的语音片段")