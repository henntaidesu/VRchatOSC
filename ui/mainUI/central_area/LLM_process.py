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
                # 详细显示LLM返回内容
                self.main_app.log(f"[LLM返回] 完整回复: {response.llm_response}")
                
                # 显示LLM回复在语音识别框中
                self.main_app.add_speech_output(response.llm_response, "AI回复")
                
                # 如果VRChat已连接，发送消息到VRChat
                if self.main_app.client:
                    self.main_app.client.send_text_message(f"[AI] {response.llm_response}")
                    self.main_app.log(f"[VRChat] 已发送消息: {response.llm_response[:50]}...")
                
                # 按句子结束标点分割文本并逐句处理
                self.main_app.log(f"[语音合成] 按句子分割（支持中日英标点）: {response.llm_response}")
                sentences = self._split_by_punctuation(response.llm_response)
                
                # 使用顺序播放处理
                self._process_sentences_sequentially(sentences)
                
            else:
                self.main_app.log(f"[LLM错误] 处理失败: {response.error}")
            
        except Exception as e:
            self.main_app.log(f"[错误] 处理LLM响应时出错: {e}")
        
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
                        self.main_app.log(f"[语音识别] 提交到情感感知LLM: {text}")
                        request_id = self.emotion_aware_processor.submit_voice_text(text)
                        if request_id:
                            self.main_app.log(f"[情感感知LLM] ✅ 已提交语音到AI处理 (ID: {request_id})")
                            return True
                        else:
                            self.main_app.log("[情感感知LLM] ❌ 提交语音到AI失败")
                            return False
                    else:
                        self.main_app.log("[情感感知LLM] ⚠️ 情感感知处理器未就绪")
                        return False
                elif self.streaming_processor:
                    # 使用普通流式处理器
                    if self.streaming_processor.is_client_ready():
                        self.main_app.log(f"[语音识别] 提交到流式LLM: {text}")
                        request_id = self.streaming_processor.submit_voice_text(text)
                        if request_id:
                            self.main_app.log(f"[流式LLM] ✅ 已提交语音到AI处理 (ID: {request_id})")
                            return True
                        else:
                            self.main_app.log("[流式LLM] ❌ 提交语音到AI失败")
                            return False
                    else:
                        self.main_app.log("[流式LLM] ⚠️ 流式处理器未就绪")
                        return False
            else:
                # 使用传统处理器
                if self.llm_handler and self.llm_handler.is_client_ready():
                    self.main_app.log(f"[语音识别] 提交到传统LLM: {text}")
                    request_id = self.llm_handler.submit_voice_text(text)
                    if request_id:
                        self.main_app.log(f"[传统LLM] ✅ 已提交语音到AI处理 (ID: {request_id})")
                        return True
                    else:
                        self.main_app.log("[传统LLM] ❌ 提交语音到AI失败")
                        return False
                else:
                    self.main_app.log("[传统LLM] ⚠️ LLM处理器未就绪")
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
                        self.main_app.log(f"[顺序播放] 处理句子 {i+1}/{len(sentences)}: {sentence}")
                        
                        # 同步合成音频
                        audio_result = self.main_app.voicevox_area.synthesize_with_voicevox(sentence.strip())
                        
                        if audio_result is not None:
                            self.main_app.log(f"[VOICEVOX] 句子合成成功: {sentence.strip()} (大小: {len(audio_result)} bytes)")
                            
                            # 同步发送音频到9003端口
                            self._send_audio_to_port9003_sync(audio_result, i+1, len(sentences))
                            
                            # 等待一小段时间确保音频开始播放再处理下一句
                            # 根据音频长度估算播放时间（简单估算：每1000字节约0.1秒）
                            estimated_duration = max(0.5, len(audio_result) / 10000)  # 最少0.5秒间隔
                            self.main_app.log(f"[顺序播放] 等待 {estimated_duration:.1f}s 后处理下一句")
                            time.sleep(estimated_duration)
                            
                        else:
                            self.main_app.log(f"[VOICEVOX] 句子合成失败: {sentence.strip()}")
                            
                self.main_app.log("[顺序播放] 所有句子处理完成")
                
            except Exception as e:
                self.main_app.log(f"[顺序播放] 处理出错: {e}")
        
        # 在后台线程中顺序处理，避免阻塞UI
        thread = threading.Thread(target=sequential_processor, daemon=True)
        thread.start()
    
    def _send_audio_to_port9003(self, audio_data):
        """发送音频数据到9003端口"""
        try:
            import socket
            import threading
            
            # 检查音频数据格式和大小
            if not isinstance(audio_data, bytes):
                self.main_app.log(f"[警告] VOICEVOX返回的音频数据格式不支持: {type(audio_data)}")
                return
                
            audio_size = len(audio_data)
            self.main_app.log(f"[端口9003] 准备发送音频数据，大小: {audio_size} bytes")
            
            # UDP最大包大小通常是65507字节，但实际建议小于64KB
            MAX_UDP_SIZE = 64000
            
            def send_audio_thread():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    
                    if audio_size <= MAX_UDP_SIZE:
                        # 直接发送
                        sock.sendto(audio_data, ('127.0.0.1', 9003))
                        self.main_app.log(f"[端口9003] 音频数据发送成功 ({audio_size} bytes)")
                    else:
                        # 分块发送
                        chunks = [audio_data[i:i+MAX_UDP_SIZE] for i in range(0, audio_size, MAX_UDP_SIZE)]
                        self.main_app.log(f"[端口9003] 音频过大，分为 {len(chunks)} 块发送")
                        
                        for i, chunk in enumerate(chunks):
                            sock.sendto(chunk, ('127.0.0.1', 9003))
                            self.main_app.log(f"[端口9003] 发送块 {i+1}/{len(chunks)} ({len(chunk)} bytes)")
                        
                        self.main_app.log(f"[端口9003] 所有音频块发送完成")
                    
                    sock.close()
                    
                except Exception as e:
                    self.main_app.log(f"[端口9003] 音频发送失败: {e}")
            
            # 在后台线程中发送，避免阻塞UI
            thread = threading.Thread(target=send_audio_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self.main_app.log(f"[端口9003] 创建发送线程失败: {e}")
    
    def _send_audio_to_port9003_sync(self, audio_data, sentence_index, total_sentences):
        """同步发送音频数据到9003端口（用于顺序播放）"""
        try:
            import socket
            
            # 检查音频数据格式
            if not isinstance(audio_data, bytes):
                self.main_app.log(f"[警告] 音频数据格式不支持: {type(audio_data)}")
                return
                
            audio_size = len(audio_data)
            self.main_app.log(f"[端口9003] 发送句子 {sentence_index}/{total_sentences}，大小: {audio_size} bytes")
            
            # 直接发送整个音频，不分块
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            try:
                sock.sendto(audio_data, ('127.0.0.1', 9003))
                self.main_app.log(f"[端口9003] 句子 {sentence_index} 发送成功 ({audio_size} bytes)")
                
            finally:
                sock.close()
                
        except Exception as e:
            self.main_app.log(f"[端口9003] 句子 {sentence_index} 发送失败: {e}")