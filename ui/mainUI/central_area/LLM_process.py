# -*- coding: utf-8 -*-

"""
LLM处理模块
负责管理语音转文本后的LLM处理功能
"""

from src.llm.voice_llm_handler import VoiceLLMHandler, VoiceLLMResponse
from src.llm.streaming_llm_processor import StreamingLLMProcessor
from src.llm.emotion_aware_streaming_processor import EmotionAwareStreamingProcessor


class LLMProcessor:
    def __init__(self, main_app):
        self.main_app = main_app
        self.llm_handler = None
        self.streaming_processor = None  # 流式处理器
        self.emotion_aware_processor = None  # 情感感知处理器
        self.llm_enabled = True
        self.streaming_mode = True  # 是否使用流式模式
        self.emotion_awareness_enabled = True  # 是否启用情感感知
    
    def init_llm_handler(self):
        """初始化LLM处理器"""
        try:
            if self.main_app.config:
                if self.streaming_mode:
                    if self.emotion_awareness_enabled:
                        # 初始化情感感知流式处理器
                        self.emotion_aware_processor = EmotionAwareStreamingProcessor(
                            main_app=self.main_app,
                            config=self.main_app.config
                        )
                        
                        # 启动情感感知流式处理
                        self.emotion_aware_processor.start_processing()
                        
                        if self.emotion_aware_processor.is_client_ready():
                            self.main_app.log("情感感知流式LLM处理器初始化成功")
                        else:
                            self.main_app.log("情感感知流式LLM处理器初始化失败：客户端未就绪")
                    else:
                        # 初始化普通流式处理器
                        self.streaming_processor = StreamingLLMProcessor(
                            main_app=self.main_app,
                            config=self.main_app.config
                        )
                        
                        # 启动流式处理
                        self.streaming_processor.start_processing()
                        
                        if self.streaming_processor.is_client_ready():
                            self.main_app.log("流式LLM处理器初始化成功")
                        else:
                            self.main_app.log("流式LLM处理器初始化失败：客户端未就绪")
                else:
                    # 初始化传统处理器
                    self.llm_handler = VoiceLLMHandler(config=self.main_app.config)
                    
                    # 设置LLM响应回调
                    self.llm_handler.set_response_callback(self.on_llm_response)
                    
                    if self.llm_handler.is_client_ready():
                        # 启动处理器
                        self.llm_handler.start_processing()
                        self.main_app.log("LLM处理器初始化成功")
                    else:
                        self.main_app.log("LLM处理器初始化失败：客户端未就绪")
                    
        except Exception as e:
            self.main_app.log(f"初始化LLM处理器失败: {e}")
            self.llm_handler = None
            self.streaming_processor = None
            self.emotion_aware_processor = None
    
    def on_llm_response(self, response: VoiceLLMResponse):
        """处理LLM响应"""
        try:
            if response.success:
                # 显示LLM回复在语音识别框中
                self.main_app.add_speech_output(response.llm_response, "AI回复")
                
                # 如果VRChat已连接，发送消息到VRChat
                if self.main_app.client:
                    self.main_app.client.send_text_message(f"[AI] {response.llm_response}")
                
                # 使用VOICEVOX合成语音
                self.main_app.voicevox_area.synthesize_with_voicevox(response.llm_response)
                
                self.main_app.log(f"LLM响应: {response.llm_response[:100]}...")
            else:
                self.main_app.log(f"LLM处理失败: {response.error}")
            
        except Exception as e:
            self.main_app.log(f"处理LLM响应时出错: {e}")
        
        # 在主线程中更新UI
        self.main_app.root.after(0, lambda: None)
    
    def process_voice_text(self, text: str) -> bool:
        """处理语音转文本结果
        
        Args:
            text: 识别到的语音文本
            
        Returns:
            bool: 是否成功提交到LLM处理
        """
        try:
            if not self.llm_enabled:
                return False
            
            if not text.strip():
                return False
            
            # 根据模式选择处理器
            if self.streaming_mode:
                if self.emotion_awareness_enabled and self.emotion_aware_processor:
                    # 使用情感感知流式处理器
                    if self.emotion_aware_processor.is_client_ready():
                        request_id = self.emotion_aware_processor.submit_voice_text(text)
                        if request_id:
                            self.main_app.log(f"[情感感知LLM] 已提交语音到AI处理: {text[:50]}...")
                            return True
                        else:
                            self.main_app.log("[情感感知LLM] 提交语音到AI失败")
                            return False
                    else:
                        self.main_app.log("[情感感知LLM] 情感感知处理器未就绪")
                        return False
                elif self.streaming_processor:
                    # 使用普通流式处理器
                    if self.streaming_processor.is_client_ready():
                        request_id = self.streaming_processor.submit_voice_text(text)
                        if request_id:
                            self.main_app.log(f"[流式LLM] 已提交语音到AI处理: {text[:50]}...")
                            return True
                        else:
                            self.main_app.log("[流式LLM] 提交语音到AI失败")
                            return False
                    else:
                        self.main_app.log("[流式LLM] 流式处理器未就绪")
                        return False
            else:
                # 使用传统处理器
                if self.llm_handler and self.llm_handler.is_client_ready():
                    request_id = self.llm_handler.submit_voice_text(text)
                    if request_id:
                        self.main_app.log(f"[LLM] 已提交语音到AI处理: {text[:50]}...")
                        return True
                    else:
                        self.main_app.log("[LLM] 提交语音到AI失败")
                        return False
                else:
                    self.main_app.log("[LLM] LLM处理器未就绪")
                    return False
        except Exception as e:
            self.main_app.log(f"处理语音文本时出错: {e}")
            return False
    
    def toggle_llm_enabled(self, enabled: bool):
        """切换LLM启用状态"""
        self.llm_enabled = enabled
        status = "启用" if self.llm_enabled else "禁用"
        self.main_app.log(f"LLM处理已{status}")
    
    def is_enabled(self) -> bool:
        """检查LLM是否启用"""
        return self.llm_enabled
    
    def is_ready(self) -> bool:
        """检查LLM处理器是否就绪"""
        if self.streaming_mode:
            if self.emotion_awareness_enabled and self.emotion_aware_processor:
                return (self.emotion_aware_processor is not None and 
                        self.emotion_aware_processor.is_client_ready())
            elif self.streaming_processor:
                return (self.streaming_processor is not None and 
                        self.streaming_processor.is_client_ready())
            else:
                return False
        else:
            return (self.llm_handler is not None and 
                    self.llm_handler.is_client_ready())
    
    def shutdown(self):
        """关闭LLM处理器"""
        try:
            if self.emotion_aware_processor:
                self.emotion_aware_processor.shutdown()
                self.emotion_aware_processor = None
                self.main_app.log("情感感知流式LLM处理器已关闭")
            
            if self.streaming_processor:
                self.streaming_processor.shutdown()
                self.streaming_processor = None
                self.main_app.log("流式LLM处理器已关闭")
                
            if self.llm_handler:
                self.llm_handler.stop_processing()
                self.llm_handler = None
                self.main_app.log("LLM处理器已关闭")
        except Exception as e:
            self.main_app.log(f"关闭LLM处理器时出错: {e}")
            
    def set_streaming_mode(self, enabled: bool):
        """设置流式模式开关"""
        if self.streaming_mode != enabled:
            # 关闭当前处理器
            self.shutdown()
            
            self.streaming_mode = enabled
            
            # 重新初始化
            self.init_llm_handler()
            
            mode = "流式" if enabled else "传统"
            self.main_app.log(f"已切换到{mode}LLM处理模式")
    
    def set_emotion_awareness_enabled(self, enabled: bool):
        """设置情感感知开关"""
        if self.emotion_awareness_enabled != enabled:
            # 关闭当前处理器
            self.shutdown()
            
            self.emotion_awareness_enabled = enabled
            
            # 重新初始化
            self.init_llm_handler()
            
            mode = "情感感知" if enabled else "普通流式"
            self.main_app.log(f"已切换到{mode}LLM处理模式")
    
    def update_emotion_state(self, emotions: dict):
        """更新用户情感状态"""
        if self.emotion_aware_processor:
            self.emotion_aware_processor.update_emotion_state(emotions)
        else:
            # 如果没有情感感知处理器，记录情感数据用于后续切换
            if not hasattr(self, '_cached_emotions'):
                self._cached_emotions = {}
            self._cached_emotions.update(emotions)
    
    def get_emotion_summary(self) -> dict:
        """获取情感状态摘要"""
        if self.emotion_aware_processor:
            return self.emotion_aware_processor.get_emotion_summary()
        else:
            return {"message": "情感感知功能未启用"}
    
    def clear_emotion_history(self):
        """清除情感历史记录"""
        if self.emotion_aware_processor:
            self.emotion_aware_processor.clear_emotion_history()
            self.main_app.log("已清除情感历史记录")