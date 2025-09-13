# -*- coding: utf-8 -*-
"""
LLM处理UI功能类
负责处理LLM相关的UI交互逻辑
"""

import tkinter as tk
from tkinter import messagebox

try:
    from src.llm.voice_llm_handler import VoiceLLMHandler, VoiceLLMResponse
    LLM_HANDLER_AVAILABLE = True
except ImportError:
    LLM_HANDLER_AVAILABLE = False
    
try:
    from src.llm.streaming_llm_processor import StreamingLLMProcessor
    STREAMING_PROCESSOR_AVAILABLE = True
except ImportError:
    STREAMING_PROCESSOR_AVAILABLE = False
    
try:
    from src.llm.emotion_aware_streaming_processor import EmotionAwareStreamingProcessor
    EMOTION_PROCESSOR_AVAILABLE = True
except ImportError:
    EMOTION_PROCESSOR_AVAILABLE = False


class LLMHandler:
    """LLM处理UI功能类"""
    
    def __init__(self, main_app):
        """
        初始化LLM处理器
        
        Args:
            main_app: 主应用程序实例
        """
        self.main_app = main_app
        self.llm_handler = None
        self.streaming_processor = None
        self.emotion_aware_processor = None
        self.llm_enabled = True
        self.streaming_mode = True  # 强制使用流式模式
        self.emotion_awareness_enabled = True  # 是否启用情感感知
        
        # 对话记录相关
        self.conversation_file_path = None
        self.current_user_input = None
        self._processed_responses = set()
        
        self._init_conversation_recording()
    
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
                        
                        # 设置额外的回调
                        if hasattr(self.emotion_aware_processor, 'set_additional_callback'):
                            self.emotion_aware_processor.set_additional_callback(self.on_llm_response)
                        
                        # 启动情感感知流式处理
                        self.emotion_aware_processor.start_processing()
                        
                        if self.emotion_aware_processor.is_client_ready():
                            self.main_app.log("情感感知流式LLM处理器初始化成功")
                        else:
                            self.main_app.log("情感感知流式LLM处理器初始化失败")
                    else:
                        # 初始化普通流式处理器
                        self.streaming_processor = StreamingLLMProcessor(
                            main_app=self.main_app,
                            config=self.main_app.config
                        )
                        
                        # 设置额外的回调
                        if hasattr(self.streaming_processor, 'set_additional_callback'):
                            self.streaming_processor.set_additional_callback(self.on_llm_response)
                        
                        # 启动流式处理
                        self.streaming_processor.start_processing()
                        
                        if self.streaming_processor.is_client_ready():
                            self.main_app.log("流式LLM处理器初始化成功")
                        else:
                            self.main_app.log("流式LLM处理器初始化失败")
                    
        except Exception as e:
            self.main_app.log(f"LLM处理器初始化失败: {e}")
            self.llm_handler = None
            self.streaming_processor = None
            self.emotion_aware_processor = None
    
    def on_llm_response(self, response: VoiceLLMResponse):
        """处理LLM响应 - UI更新和对话记录"""
        # 添加重复调用检测
        if hasattr(response, 'request_id'):
            response_key = f"{response.request_id}_{response.llm_response[:50]}"
            if response_key in self._processed_responses:
                self.main_app.log(f"[警告] 检测到重复的LLM响应处理: {response.request_id}")
                return
            self._processed_responses.add(response_key)
            
            # 清理过期的响应记录
            if len(self._processed_responses) > 100:
                self._processed_responses.clear()
        
        try:
            if response.success:
                # 记录对话
                if hasattr(self, 'current_user_input') and self.current_user_input:
                    self._record_conversation(self.current_user_input, response.llm_response)
                    self.current_user_input = None
                
                # 显示LLM回复在语音识别框中
                self.main_app.add_speech_output(response.llm_response, "AI回复")
                
                # 发送AI回复到AI端VRChat
                self._send_ai_reply_to_vrchat(response.llm_response)
                
            else:
                self.main_app.log(f"[LLM错误] 处理失败: {response.error}")
            
        except Exception as e:
            self.main_app.log(f"[错误] LLM响应处理出错: {e}")
    
    def _send_ai_reply_to_vrchat(self, reply_text: str):
        """发送AI回复到AI端VRChat"""
        try:
            if (hasattr(self.main_app, 'ai_vrchat_manager') and 
                self.main_app.ai_vrchat_manager and 
                hasattr(self.main_app.ai_vrchat_manager, 'ai_osc_client') and
                self.main_app.ai_vrchat_manager.ai_osc_client):
                
                success = self.main_app.ai_vrchat_manager.ai_osc_client.send_chatbox_message(
                    f"[AI] {reply_text}", 
                    send_immediately=True
                )
                if success:
                    self.main_app.log(f"[AI→AI] 文本已发送: {reply_text[:50]}...")
                else:
                    self.main_app.log(f"[AI→AI] 文本发送失败: {reply_text[:50]}...")
            else:
                self.main_app.log("[AI回复] AI VRChat未连接")
                
        except Exception as e:
            self.main_app.log(f"[AI→AI] 发送异常: {e}")
    
    def process_voice_text(self, text: str) -> bool:
        """
        处理语音转文本结果
        
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
            
            # 存储用户输入以便后续记录对话
            self.current_user_input = text.strip()
            
            # 使用流式处理器
            if self.emotion_awareness_enabled and self.emotion_aware_processor:
                # 使用情感感知流式处理器
                if self.emotion_aware_processor.is_client_ready():
                    self.main_app.log(f"[情感感知LLM] 提交文本: {text}")
                    request_id = self.emotion_aware_processor.submit_voice_text(text)
                    if request_id:
                        self.main_app.log(f"[情感感知LLM] 已提交: {request_id}")
                        return True
                    else:
                        self.main_app.log("[情感感知LLM] 提交失败")
                        return False
                else:
                    self.main_app.log("[情感感知LLM] 处理器未就绪")
                    return False
            elif self.streaming_processor:
                # 使用普通流式处理器
                if self.streaming_processor.is_client_ready():
                    self.main_app.log(f"[流式LLM] 提交文本: {text}")
                    request_id = self.streaming_processor.submit_voice_text(text)
                    if request_id:
                        self.main_app.log(f"[流式LLM] 已提交: {request_id}")
                        return True
                    else:
                        self.main_app.log("[流式LLM] 提交失败")
                        return False
                else:
                    self.main_app.log("[流式LLM] 处理器未就绪")
                    return False
            else:
                self.main_app.log("[LLM] 无可用处理器")
                return False
                
        except Exception as e:
            self.main_app.log(f"LLM语音文本处理错误: {e}")
            return False
    
    def toggle_llm_enabled(self, enabled: bool):
        """切换LLM启用状态"""
        self.llm_enabled = enabled
        status = "已启用" if self.llm_enabled else "已禁用"
        self.main_app.log(f"LLM处理状态: {status}")
    
    def set_emotion_awareness_enabled(self, enabled: bool):
        """设置情感感知开关"""
        if self.emotion_awareness_enabled != enabled:
            # 关闭当前处理器
            self.shutdown()
            
            self.emotion_awareness_enabled = enabled
            
            # 重新初始化
            self.init_llm_handler()
            
            mode = "情感感知模式" if enabled else "流式模式"
            self.main_app.log(f"LLM模式已切换为: {mode}")
    
    def update_emotion_state(self, emotions: dict):
        """更新用户情感状态"""
        if self.emotion_aware_processor:
            self.emotion_aware_processor.update_emotion_state(emotions)
        else:
            # 如果没有情感感知处理器，缓存情感数据
            if not hasattr(self, '_cached_emotions'):
                self._cached_emotions = {}
            self._cached_emotions.update(emotions)
    
    def get_emotion_summary(self) -> dict:
        """获取情感状态摘要"""
        if self.emotion_aware_processor:
            return self.emotion_aware_processor.get_emotion_summary()
        else:
            return {"message": "情感感知未启用"}
    
    def clear_emotion_history(self):
        """清除情感历史记录"""
        if self.emotion_aware_processor:
            self.emotion_aware_processor.clear_emotion_history()
    
    def reset_conversation(self):
        """重置LLM对话历史"""
        try:
            # 确认重置操作
            result = messagebox.askyesno(
                "确认重置", 
                "确定要重置LLM对话历史吗？\n这将清空当前对话并创建新的对话文件。",
                icon="question"
            )
            
            if not result:
                return
            
            # 重置对话历史
            if self.emotion_awareness_enabled and self.emotion_aware_processor:
                if hasattr(self.emotion_aware_processor, 'llm_handler'):
                    self.emotion_aware_processor.llm_handler.clear_conversation_history()
                    self.main_app.log("[LLM重置] 情感感知处理器对话历史已清空")
            elif self.streaming_processor:
                if hasattr(self.streaming_processor, 'llm_handler'):
                    self.streaming_processor.llm_handler.clear_conversation_history()
                    self.main_app.log("[LLM重置] 流式处理器对话历史已清空")
            elif self.llm_handler:
                if hasattr(self.llm_handler, 'clear_conversation_history'):
                    self.llm_handler.clear_conversation_history()
                    self.main_app.log("[LLM重置] 传统处理器对话历史已清空")
            else:
                self.main_app.log("[LLM重置] 未找到有效的LLM处理器")
                return
            
            self.main_app.log("[LLM重置] 对话历史已重置，新的对话文件已创建")
            messagebox.showinfo("重置完成", "LLM对话历史已成功重置！")
            
        except Exception as e:
            self.main_app.log(f"[LLM重置] 重置失败: {e}")
            messagebox.showerror("重置失败", f"重置LLM对话历史时发生错误: {e}")
    
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
                self.main_app.log("情感感知LLM处理器已关闭")
            
            if self.streaming_processor:
                self.streaming_processor.shutdown()
                self.streaming_processor = None
                self.main_app.log("流式LLM处理器已关闭")
                
            if self.llm_handler:
                self.llm_handler.stop_processing()
                self.llm_handler = None
                self.main_app.log("传统LLM处理器已关闭")
        except Exception as e:
            self.main_app.log(f"LLM处理器关闭错误: {e}")
    
    def _init_conversation_recording(self):
        """初始化对话记录功能"""
        try:
            import os
            from datetime import datetime
            
            # 设置记录目录路径
            self.record_dir = os.path.join(os.getcwd(), "Record", "text")
            
            # 确保目录存在
            self._ensure_record_directory()
            
            # 生成文件名：启动时间 + 处理器标识
            start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_ui_{start_time}.vsc"
            self.conversation_file_path = os.path.join(self.record_dir, filename)
            
            # 创建文件并写入头部信息
            with open(self.conversation_file_path, 'w', encoding='utf-8') as f:
                f.write("# VRChat OSC 对话记录\n")
                f.write(f"# 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# 文件格式: VSCode对话记录格式\n")
                f.write("# ==========================================\n\n")
            
            self.main_app.log(f"[对话记录] 文件已创建: {filename}")
            
        except Exception as e:
            self.main_app.log(f"[对话记录] 初始化失败: {e}")
            self.conversation_file_path = None
    
    def _ensure_record_directory(self):
        """确保记录目录存在"""
        try:
            import os
            
            if not os.path.exists(self.record_dir):
                os.makedirs(self.record_dir, exist_ok=True)
                self.main_app.log(f"[对话记录] 目录已创建: {self.record_dir}")
            
        except Exception as e:
            self.main_app.log(f"[对话记录] 目录创建失败: {e}")
    
    def _record_conversation(self, user_input: str, ai_response: str):
        """记录对话到文件"""
        try:
            if not self.conversation_file_path:
                return
            
            # 确保目录存在
            if hasattr(self, 'record_dir'):
                self._ensure_record_directory()
            
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(self.conversation_file_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 用户: {user_input}\n")
                f.write(f"[{timestamp}] AI: {ai_response}\n")
                f.write("---\n\n")
            
            self.main_app.log("[对话记录] 对话已记录")
            
        except Exception as e:
            self.main_app.log(f"[对话记录] 记录失败: {e}")
            # 如果记录失败，尝试重新初始化
            try:
                self._init_conversation_recording()
                self.main_app.log("[对话记录] 重新初始化完成")
            except Exception as retry_e:
                self.main_app.log(f"[对话记录] 重新初始化失败: {retry_e}")
    
    def cleanup(self):
        """清理资源"""
        self.shutdown()
