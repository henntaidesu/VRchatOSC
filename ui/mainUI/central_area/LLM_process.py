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
        self.streaming_mode = True  # 强制使用流式模式（已移除传统模式）
        self.emotion_awareness_enabled = True  # 是否启用情感感知
        
        # 对话记录相关
        self.conversation_file_path = None
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
                        
                        # 设置额外的回调到LLM_process
                        if hasattr(self.emotion_aware_processor, 'set_additional_callback'):
                            self.emotion_aware_processor.set_additional_callback(self.on_llm_response)
                        
                        # 启动情感感知流式处理
                        self.emotion_aware_processor.start_processing()
                        
                        if self.emotion_aware_processor.is_client_ready():
                            self.main_app.log(self.main_app.get_text("llm_emotion_streaming_init_success"))
                        else:
                            self.main_app.log(self.main_app.get_text("llm_emotion_streaming_init_failed"))
                    else:
                        # 初始化普通流式处理器
                        self.streaming_processor = StreamingLLMProcessor(
                            main_app=self.main_app,
                            config=self.main_app.config
                        )
                        
                        # 设置额外的回调到LLM_process
                        if hasattr(self.streaming_processor, 'set_additional_callback'):
                            self.streaming_processor.set_additional_callback(self.on_llm_response)
                        
                        # 启动流式处理
                        self.streaming_processor.start_processing()
                        
                        if self.streaming_processor.is_client_ready():
                            self.main_app.log(self.main_app.get_text("llm_streaming_init_success"))
                        else:
                            self.main_app.log(self.main_app.get_text("llm_streaming_init_failed"))
                # 已移除传统模式处理器初始化
                    
        except Exception as e:
            self.main_app.log(f"{self.main_app.get_text('llm_init_failed')}: {e}")
            self.llm_handler = None
            self.streaming_processor = None
            self.emotion_aware_processor = None
    
    def on_llm_response(self, response: VoiceLLMResponse):
        """处理LLM响应"""
        try:
            if response.success:
                # 详细显示LLM返回内容
                self.main_app.log(f"[{self.main_app.get_text('llm_response_return')}] {self.main_app.get_text('llm_response_complete')}: {response.llm_response}")
                
                # 记录对话
                if hasattr(self, 'current_user_input') and self.current_user_input:
                    self._record_conversation(self.current_user_input, response.llm_response)
                    # 清空当前用户输入
                    self.current_user_input = None
                
                # 显示LLM回复在语音识别框中
                self.main_app.add_speech_output(response.llm_response, self.main_app.get_text("llm_response_ai_reply"))
                
                # 发送AI回复到AI端VRChat (而不是用户VRChat端)
                if (hasattr(self.main_app, 'ai_vrchat_area') and 
                    self.main_app.ai_vrchat_area and 
                    hasattr(self.main_app.ai_vrchat_area, 'ai_osc_client') and
                    self.main_app.ai_vrchat_area.ai_osc_client):
                    try:
                        success = self.main_app.ai_vrchat_area.ai_osc_client.send_chatbox_message(
                            f"[AI] {response.llm_response}", 
                            send_immediately=True
                        )
                        if success:
                            self.main_app.log(f"[{self.main_app.get_text('llm_response_ai_to_ai')}] {self.main_app.get_text('llm_response_text_sent')}: {response.llm_response[:50]}...")
                        else:
                            self.main_app.log(f"[{self.main_app.get_text('llm_response_ai_to_ai')}] {self.main_app.get_text('llm_response_text_failed')}: {response.llm_response[:50]}...")
                    except Exception as e:
                        self.main_app.log(f"[{self.main_app.get_text('llm_response_ai_to_ai')}] {self.main_app.get_text('llm_response_send_exception')}: {e}")
                else:
                    self.main_app.log(f"[{self.main_app.get_text('llm_response_ai_reply')}] {self.main_app.get_text('llm_response_ai_not_connected')}")
                
                # 按句子结束标点分割文本并逐句处理
                self.main_app.log(f"[{self.main_app.get_text('llm_voice_synthesis')}] {self.main_app.get_text('llm_sentence_split')}: {response.llm_response}")
                sentences = self._split_by_punctuation(response.llm_response)
                
                # 使用顺序播放处理
                self._process_sentences_sequentially(sentences)
                
            else:
                self.main_app.log(f"[{self.main_app.get_text('llm_error')}] {self.main_app.get_text('llm_error_processing_failed')}: {response.error}")
            
        except Exception as e:
            self.main_app.log(f"[{self.main_app.get_text('error')}] {self.main_app.get_text('llm_error_response_processing')}: {e}")
        
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
            
            # 存储用户输入以便后续记录对话
            self.current_user_input = text.strip()
            
            # 只使用流式处理器（已移除传统模式）
            if self.emotion_awareness_enabled and self.emotion_aware_processor:
                # 使用情感感知流式处理器
                if self.emotion_aware_processor.is_client_ready():
                    self.main_app.log(f"[{self.main_app.get_text('llm_voice_submit_emotion')}: {text}")
                    request_id = self.emotion_aware_processor.submit_voice_text(text)
                    if request_id:
                        self.main_app.log(f"[{self.main_app.get_text('llm_emotion_submitted')}: {request_id})")
                        return True
                    else:
                        self.main_app.log(f"[{self.main_app.get_text('llm_emotion_submit_failed')}")
                        return False
                else:
                    self.main_app.log(f"[{self.main_app.get_text('llm_emotion_not_ready')}")
                    return False
            elif self.streaming_processor:
                # 使用普通流式处理器
                if self.streaming_processor.is_client_ready():
                    self.main_app.log(f"[{self.main_app.get_text('llm_voice_submit_streaming')}: {text}")
                    request_id = self.streaming_processor.submit_voice_text(text)
                    if request_id:
                        self.main_app.log(f"[{self.main_app.get_text('llm_streaming_submitted')}: {request_id})")
                        return True
                    else:
                        self.main_app.log(f"[{self.main_app.get_text('llm_streaming_submit_failed')}")
                        return False
                else:
                    self.main_app.log(f"[{self.main_app.get_text('llm_streaming_not_ready')}")
                    return False
            else:
                self.main_app.log(f"[{self.main_app.get_text('llm_no_processor')}")
                return False
        except Exception as e:
            self.main_app.log(f"{self.main_app.get_text('llm_voice_text_error')}: {e}")
            return False
    
    def toggle_llm_enabled(self, enabled: bool):
        """切换LLM启用状态"""
        self.llm_enabled = enabled
        status = self.main_app.get_text("llm_enabled") if self.llm_enabled else self.main_app.get_text("llm_disabled")
        self.main_app.log(f"{self.main_app.get_text('llm_processing_status')}{status}")
    
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
                self.main_app.log(self.main_app.get_text("llm_emotion_processor_shutdown"))
            
            if self.streaming_processor:
                self.streaming_processor.shutdown()
                self.streaming_processor = None
                self.main_app.log(self.main_app.get_text("llm_streaming_processor_shutdown"))
                
            if self.llm_handler:
                self.llm_handler.stop_processing()
                self.llm_handler = None
                self.main_app.log(self.main_app.get_text("llm_processor_shutdown"))
        except Exception as e:
            self.main_app.log(f"{self.main_app.get_text('llm_shutdown_error')}: {e}")
            
    # 已移除 set_streaming_mode 方法，因为强制使用流式模式
    
    def set_emotion_awareness_enabled(self, enabled: bool):
        """设置情感感知开关"""
        if self.emotion_awareness_enabled != enabled:
            # 关闭当前处理器
            self.shutdown()
            
            self.emotion_awareness_enabled = enabled
            
            # 重新初始化
            self.init_llm_handler()
            
            mode = self.main_app.get_text("llm_emotion_mode") if enabled else self.main_app.get_text("llm_streaming_mode")
            self.main_app.log(self.main_app.get_text("llm_mode_switched").format(mode=mode))
    
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
            return {"message": self.main_app.get_text("llm_emotion_not_enabled")}
    
    def clear_emotion_history(self):
        """清除情感历史记录"""
        if self.emotion_aware_processor:
            self.emotion_aware_processor.clear_emotion_history()
    
    def _split_by_punctuation(self, text: str) -> list:
        """按句子结束标点符号分割文本（支持中日英三种语言）"""
        import re
        # 句子结束标点符号（中文、日文、英文）
        # 中文：。！？
        # 日文：。！？（日文句号与中文相同，但也包括日文特有的）
        # 英文：.!?
        # 只在句子结束标点处分割，保留逗号、顿号、分号等暂停标点在句子内
        end_punctuation = r'[。！？.!?]'
        sentences = re.split(end_punctuation, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _process_sentences_sequentially(self, sentences):
        """按顺序处理句子，确保音频按顺序播放"""
        import threading
        import time
        
        def sequential_processor():
            try:
                for i, sentence in enumerate(sentences):
                    if sentence.strip():
                        self.main_app.log(f"[{self.main_app.get_text('llm_sequential_processing')} {i+1}/{len(sentences)}: {sentence}")
                        
                        # 同步合成音频，指定返回bytes格式（用于传统处理）
                        audio_result = self.main_app.voicevox_area.synthesize_with_voicevox(sentence.strip(), return_format="bytes")
                        
                        if audio_result is not None:
                            self.main_app.log(f"[{self.main_app.get_text('llm_voicevox_success')}: {sentence.strip()} ({self.main_app.get_text('llm_audio_size')}: {len(audio_result)} bytes)")
                            
                            # 同步发送音频到9003端口
                            self._send_audio_to_port9003_sync(audio_result, i+1, len(sentences))
                            
                            # 等待一小段时间确保音频开始播放再处理下一句
                            # 根据音频长度估算播放时间（简单估算：每1000字节约0.1秒）
                            estimated_duration = max(0.5, len(audio_result) / 10000)  # 最少0.5秒间隔
                            self.main_app.log(f"[{self.main_app.get_text('llm_sequential_wait')} {estimated_duration:.1f}s {self.main_app.get_text('llm_processing_next_sentence')}")
                            time.sleep(estimated_duration)
                            
                        else:
                            self.main_app.log(f"[{self.main_app.get_text('llm_voicevox_failed')}: {sentence.strip()}")
                            
                self.main_app.log(f"[{self.main_app.get_text('llm_sequential_complete')}")
                
            except Exception as e:
                self.main_app.log(f"[{self.main_app.get_text('llm_sequential_processing')}] {self.main_app.get_text('llm_sequential_error_prefix')}: {e}")
        
        # 在后台线程中顺序处理，避免阻塞UI
        thread = threading.Thread(target=sequential_processor, daemon=True)
        thread.start()
    
    def _send_audio_to_port9003(self, audio_data):
        """发送音频数据到9003端口"""
        try:
            import threading
            import tempfile
            import os
            from remote_audio import RemoteAudioClient
            
            # 检查音频数据格式
            if not isinstance(audio_data, bytes):
                self.main_app.log(f"[{self.main_app.get_text('warning')}] VOICEVOX{self.main_app.get_text('llm_audio_format_unsupported')}: {type(audio_data)}")
                return
                
            audio_size = len(audio_data)
            
            # 获取AI主机地址
            ai_host = self.main_app.config.ai_character_host if self.main_app.config else "127.0.0.1"
            self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_prepare_send')} {ai_host}:9003，{self.main_app.get_text('llm_audio_size')}: {audio_size} bytes")
            
            def send_audio_thread():
                try:
                    # 使用RemoteAudioClient发送音频
                    client = RemoteAudioClient(host=ai_host, port=9003)
                    
                    # 保存临时音频文件
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                        temp_file.write(audio_data)
                        temp_audio_path = temp_file.name
                    
                    # 发送音频文件
                    success = client.play_audio_file(temp_audio_path, use_queue=True, priority=0)
                    
                    # 清理临时文件
                    try:
                        os.unlink(temp_audio_path)
                    except:
                        pass
                    
                    if success:
                        self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_send_success')} {ai_host}:9003 ({audio_size} bytes)")
                    else:
                        self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_send_failed')} {ai_host}:9003")
                    
                except Exception as e:
                    self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_send_failed')} {ai_host}:9003: {e}")
            
            # 在后台线程中发送，避免阻塞UI
            thread = threading.Thread(target=send_audio_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_thread_failed')}: {e}")
    
    def _send_audio_to_port9003_sync(self, audio_data, sentence_index, total_sentences):
        """同步发送音频数据到9003端口（用于顺序播放）"""
        try:
            import tempfile
            import os
            from remote_audio import RemoteAudioClient
            
            # 检查音频数据格式
            if not isinstance(audio_data, bytes):
                self.main_app.log(f"[{self.main_app.get_text('warning')}] {self.main_app.get_text('llm_audio_format_unsupported')}: {type(audio_data)}")
                return
                
            audio_size = len(audio_data)
            
            # 获取AI主机地址
            ai_host = self.main_app.config.ai_character_host if self.main_app.config else "127.0.0.1"
            self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_sentence_send')} {sentence_index}/{total_sentences} {self.main_app.get_text('to')} {ai_host}:9003，{self.main_app.get_text('llm_audio_size')}: {audio_size} bytes")
            
            try:
                # 使用RemoteAudioClient发送音频
                client = RemoteAudioClient(host=ai_host, port=9003)
                
                # 保存临时音频文件
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_audio_path = temp_file.name
                
                # 发送音频文件（使用队列确保顺序播放）
                success = client.play_audio_file(
                    temp_audio_path, 
                    use_queue=True, 
                    priority=sentence_index  # 使用句子索引作为优先级确保顺序
                )
                
                # 清理临时文件
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass
                
                if success:
                    self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_sentence_success').format(index=sentence_index)} {ai_host}:9003 ({audio_size} bytes)")
                else:
                    self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_sentence_failed').format(index=sentence_index)} {ai_host}:9003")
                
            except Exception as e:
                self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_sentence_failed').format(index=sentence_index)} {ai_host}:9003: {e}")
                
        except Exception as e:
            self.main_app.log(f"[{self.main_app.get_text('llm_audio_port9003')}] {self.main_app.get_text('llm_audio_sentence_exception').format(index=sentence_index)}: {e}")
    
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
            filename = f"conversation_traditional_{start_time}.vsc"
            self.conversation_file_path = os.path.join(self.record_dir, filename)
            
            # 创建文件并写入头部信息
            with open(self.conversation_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# VRChat OSC 对话记录\n")
                f.write(f"# 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 文件格式: VSCode对话记录格式\n")
                f.write(f"# ==========================================\n\n")
            
            self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_file_created')}: {filename}")
            
        except Exception as e:
            self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_init_failed')}: {e}")
            self.conversation_file_path = None
    
    def _ensure_record_directory(self):
        """确保记录目录存在，不存在则创建"""
        try:
            import os
            
            if not os.path.exists(self.record_dir):
                os.makedirs(self.record_dir, exist_ok=True)
                self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_dir_created')}: {self.record_dir}")
            else:
                self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_dir_exists')}: {self.record_dir}")
            
        except Exception as e:
            self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_dir_create_failed')}: {e}")
    
    def _record_conversation(self, user_input: str, ai_response: str):
        """记录对话到文件"""
        try:
            if not self.conversation_file_path:
                return
            
            # 确保目录存在（防止目录被删除）
            if hasattr(self, 'record_dir'):
                self._ensure_record_directory()
            
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(self.conversation_file_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {self.main_app.get_text('user')}: {user_input}\n")
                f.write(f"[{timestamp}] AI: {ai_response}\n")
                f.write(f"---\n\n")
            
            self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_recorded')}")
            
        except Exception as e:
            self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_record_failed')}: {e}")
            # 如果记录失败，尝试重新初始化
            try:
                self._init_conversation_recording()
                self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_reinit_complete')}")
                # 重新尝试记录
                with open(self.conversation_file_path, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] {self.main_app.get_text('user')}: {user_input}\n")
                    f.write(f"[{timestamp}] AI: {ai_response}\n")
                    f.write(f"---\n\n")
                self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_retry_success')}")
            except Exception as retry_e:
                self.main_app.log(f"[{self.main_app.get_text('llm_conversation_recording')}] {self.main_app.get_text('llm_conversation_retry_failed')}: {retry_e}")