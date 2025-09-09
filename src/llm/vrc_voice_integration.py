#!/usr/bin/env python3
"""
VRC语音集成模块 - 将VRC动态语音处理器集成到现有系统
"""

from typing import Optional, Callable, Dict, Any
from .vrc_dynamic_voice_processor import VRCDynamicVoiceProcessor
from .voice_llm_handler import VoiceLLMHandler
from ..voice.engine import SpeechEngine


class VRCVoiceIntegration:
    """VRC语音集成管理器"""
    
    def __init__(self, config=None):
        """
        初始化VRC语音集成管理器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        self.vrc_processor: Optional[VRCDynamicVoiceProcessor] = None
        self.speech_engine: Optional[SpeechEngine] = None
        self.llm_handler: Optional[VoiceLLMHandler] = None
        
        # 外部回调
        self.voice_result_callback: Optional[Callable] = None
        self.status_change_callback: Optional[Callable] = None
        self.log_callback: Optional[Callable] = None
        
        print("[集成] VRC语音集成管理器初始化完成")
    
    def initialize(self, speech_engine: SpeechEngine, llm_handler: VoiceLLMHandler = None):
        """
        初始化集成组件
        
        Args:
            speech_engine: 语音识别引擎
            llm_handler: LLM处理器（可选）
        """
        try:
            self.speech_engine = speech_engine
            self.llm_handler = llm_handler
            
            # 创建VRC动态语音处理器
            self.vrc_processor = VRCDynamicVoiceProcessor(config=self.config)
            
            # 设置引擎和处理器
            self.vrc_processor.set_speech_engine(speech_engine)
            if llm_handler:
                self.vrc_processor.set_llm_handler(llm_handler)
            
            # 设置回调
            self.vrc_processor.set_speech_result_callback(self._on_speech_result)
            self.vrc_processor.set_status_callback(self._on_status_change)
            
            self._log("[集成] VRC语音集成组件初始化完成")
            return True
            
        except Exception as e:
            self._log(f"[集成错误] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start_processing(self):
        """启动VRC语音处理"""
        if not self.vrc_processor:
            self._log("[集成错误] VRC处理器未初始化")
            return False
        
        try:
            self.vrc_processor.start_processing()
            self._log("[集成] VRC动态语音处理已启动")
            return True
        except Exception as e:
            self._log(f"[集成错误] 启动处理失败: {e}")
            return False
    
    def stop_processing(self):
        """停止VRC语音处理"""
        if self.vrc_processor:
            try:
                self.vrc_processor.stop_processing()
                self._log("[集成] VRC动态语音处理已停止")
            except Exception as e:
                self._log(f"[集成错误] 停止处理失败: {e}")
    
    def on_vrc_speaking_state_changed(self, speaking_state: bool, voice_level: float = 0.0):
        """
        处理VRChat麦克风状态变化
        
        Args:
            speaking_state: VRC麦克风状态（True=开启，False=关闭）
            voice_level: 语音强度级别
        """
        if self.vrc_processor:
            self.vrc_processor.on_vrc_speaking_state_changed(speaking_state, voice_level)
            self._log(f"[VRC状态] 麦克风状态: {'开启' if speaking_state else '关闭'}, 强度: {voice_level:.3f}")
    
    def force_stop_recording(self):
        """强制停止当前录音"""
        if self.vrc_processor:
            self.vrc_processor.force_stop_recording()
    
    def set_voice_result_callback(self, callback: Callable):
        """设置语音识别结果回调"""
        self.voice_result_callback = callback
        self._log("[集成] 语音识别结果回调已设置")
    
    def set_status_change_callback(self, callback: Callable):
        """设置状态变化回调"""
        self.status_change_callback = callback
        self._log("[集成] 状态变化回调已设置")
    
    def set_log_callback(self, callback: Callable):
        """设置日志回调"""
        self.log_callback = callback
    
    def _on_speech_result(self, recognized_text: str, metadata: Dict[str, Any]):
        """处理语音识别结果"""
        try:
            self._log(f"[动态识别] {recognized_text}")
            
            # 调用外部回调
            if self.voice_result_callback:
                self.voice_result_callback(
                    text=recognized_text,
                    is_realtime=False,
                    trigger_reason="vrc_mic_closed",
                    audio_duration=metadata.get('duration', 0.0)
                )
            
        except Exception as e:
            self._log(f"[集成错误] 处理语音结果失败: {e}")
    
    def _on_status_change(self, event_type: str, status_data: Dict[str, Any]):
        """处理状态变化"""
        try:
            # 记录状态变化
            if event_type == "mic_opened":
                self._log("[VRC检测] 麦克风开启，开始录音")
            elif event_type == "mic_closed":
                self._log("[VRC检测] 麦克风关闭，停止录音并处理")
            
            # 调用外部回调
            if self.status_change_callback:
                self.status_change_callback("vrc_voice_dynamic", {
                    'event_type': event_type,
                    'status_data': status_data
                })
                
        except Exception as e:
            self._log(f"[集成错误] 处理状态变化失败: {e}")
    
    def _log(self, message: str):
        """内部日志方法"""
        print(message)
        if self.log_callback:
            try:
                self.log_callback(message)
            except:
                pass
    
    def get_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        base_status = {
            'integration_ready': self.vrc_processor is not None,
            'speech_engine_ready': self.speech_engine is not None and self.speech_engine.is_model_loaded(),
            'llm_handler_ready': self.llm_handler is not None and self.llm_handler.is_client_ready()
        }
        
        if self.vrc_processor:
            processor_status = self.vrc_processor.get_status()
            base_status.update(processor_status)
        
        return base_status
    
    def set_recording_parameters(self, min_duration: float = None, max_duration: float = None, 
                               silence_timeout: float = None):
        """设置录音参数"""
        if self.vrc_processor:
            self.vrc_processor.set_recording_parameters(min_duration, max_duration, silence_timeout)
            self._log("[集成] 录音参数已更新")
    
    def is_ready(self) -> bool:
        """检查集成是否就绪"""
        return (self.vrc_processor is not None and 
                self.speech_engine is not None and 
                self.speech_engine.is_model_loaded())
    
    def cleanup(self):
        """清理资源"""
        try:
            self.stop_processing()
            self.vrc_processor = None
            self.speech_engine = None
            self.llm_handler = None
            self._log("[集成] 资源清理完成")
        except Exception as e:
            self._log(f"[集成错误] 资源清理失败: {e}")


# 便捷函数：用于现有代码的快速集成
def create_vrc_voice_integration(config=None, speech_engine=None, llm_handler=None):
    """
    创建VRC语音集成实例的便捷函数
    
    Args:
        config: 配置管理器
        speech_engine: 语音识别引擎
        llm_handler: LLM处理器
        
    Returns:
        VRCVoiceIntegration实例
    """
    integration = VRCVoiceIntegration(config)
    
    if speech_engine:
        integration.initialize(speech_engine, llm_handler)
    
    return integration