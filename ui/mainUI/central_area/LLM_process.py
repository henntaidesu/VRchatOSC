# -*- coding: utf-8 -*-

"""
LLM处理模块
负责管理语音转文本后的LLM处理功能
"""

from src.llm.voice_llm_handler import VoiceLLMHandler, VoiceLLMResponse


class LLMProcessor:
    def __init__(self, main_app):
        self.main_app = main_app
        self.llm_handler = None
        self.llm_enabled = True
    
    def init_llm_handler(self):
        """初始化LLM处理器"""
        try:
            if self.main_app.config:
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
            # 如果启用了LLM处理，发送到LLM
            if self.llm_enabled and self.llm_handler and self.llm_handler.is_client_ready():
                request_id = self.llm_handler.submit_voice_text(text)
                if request_id:
                    self.main_app.log(f"[LLM] 已提交音频文件到AI处理: {text[:50]}...")
                    return True
                else:
                    self.main_app.log("[LLM] 提交音频文件到AI失败")
                    return False
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
        return (self.llm_handler is not None and 
                self.llm_handler.is_client_ready())
    
    def shutdown(self):
        """关闭LLM处理器"""
        try:
            if self.llm_handler:
                self.llm_handler.shutdown()
                self.llm_handler = None
                self.main_app.log("LLM处理器已关闭")
        except Exception as e:
            self.main_app.log(f"关闭LLM处理器时出错: {e}")