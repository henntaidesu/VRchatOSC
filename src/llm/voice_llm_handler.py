#!/usr/bin/env python3
"""
语音LLM处理器 - 将语音识别结果发送到LLM进行处理
"""

import threading
import queue
import time
import numpy as np
import sounddevice as sd
import json
import os
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from .GeminiLLM import GeminiClient, GeminiResponse
from ..voice.engine import SpeechEngine


@dataclass
class VoiceLLMRequest:
    """语音LLM请求数据"""
    text: str
    timestamp: float
    request_id: str
    system_prompt: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None


@dataclass
class VoiceLLMResponse:
    """语音LLM响应数据"""
    request_id: str
    original_text: str
    llm_response: str
    timestamp: float
    processing_time: float
    success: bool
    error: Optional[str] = None


class VoiceLLMHandler:
    """语音LLM处理器类"""
    
    def __init__(self, config=None):
        """
        初始化语音LLM处理器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        self.gemini_client: Optional[GeminiClient] = None
        
        # 请求队列和响应回调
        self.request_queue = queue.Queue()
        self.response_callback: Optional[Callable[[VoiceLLMResponse], None]] = None
        
        # 处理线程
        self.processing_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # 对话历史 (支持多轮对话)
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history_length = None  # 不设置对话上限，保留所有历史
        
        # 对话会话管理
        self.conversation_sessions_dir = "data/conversations"
        self.current_session_id = None
        self.current_session_file = None
        
        # 确保对话目录存在
        os.makedirs(self.conversation_sessions_dir, exist_ok=True)
        
        # 创建新的对话会话
        self._create_new_conversation_session()
        
        # 默认系统提示词
        self.default_system_prompt = """你是一个友善、有用的AI助手。请用简洁、自然的语言回复用户的问题。
如果用户说的是日语，请用日语回复；如果是中文，请用中文回复；如果是英语，请用英语回复。
保持回复简短但有用，适合语音对话的场景。"""
        
        # 初始化LLM客户端
        self._init_llm_client()
        
        print("[成功] 语音LLM处理器初始化完成")
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            if not self.config:
                print("[警告] 没有配置管理器，无法初始化LLM客户端")
                return
            
            # 从配置获取API Key
            api_key = self.config.get('LLM', 'gemini_api_key')
            if not api_key:
                print("[警告] 未配置Gemini API Key，LLM功能不可用")
                return
            
            # 获取模型配置
            model = self.config.get('LLM', 'gemini_model', 'gemini-1.5-flash')
            
            # 创建客户端
            self.gemini_client = GeminiClient(
                api_key=api_key,
                model=model,
                config=self.config
            )
            
            # 测试连接
            if self.gemini_client.test_connection():
                print("[成功] Gemini客户端连接测试成功")
            else:
                print("[错误] Gemini客户端连接测试失败")
                self.gemini_client = None
                
        except Exception as e:
            print(f"[错误] 初始化LLM客户端失败: {e}")
            import traceback
            traceback.print_exc()
            self.gemini_client = None
    
    def set_response_callback(self, callback: Callable[[VoiceLLMResponse], None]):
        """
        设置响应回调函数
        
        Args:
            callback: 响应回调函数，接收VoiceLLMResponse参数
        """
        self.response_callback = callback
        print("[成功] 已设置响应回调函数")
    
    def start_processing(self):
        """开始处理请求队列"""
        if self.is_running:
            print("[警告] 处理器已在运行中")
            return
        
        if not self.gemini_client:
            print("[错误] LLM客户端未初始化，无法开始处理")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        print("[成功] 语音LLM处理器已启动")
    
    def stop_processing(self):
        """停止处理请求队列"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        print("[停止] 语音LLM处理器已停止")
    
    def _processing_loop(self):
        """处理循环"""
        while self.is_running:
            try:
                # 从队列获取请求
                request = self.request_queue.get(timeout=1.0)
                
                # 处理请求
                response = self._process_request(request)
                
                # 调用回调函数
                if self.response_callback:
                    try:
                        self.response_callback(response)
                    except Exception as e:
                        print(f"[错误] 响应回调函数执行失败: {e}")
                
                # 标记队列任务完成
                self.request_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[错误] 处理循环异常: {e}")
                import traceback
                traceback.print_exc()
    
    def _process_request(self, request: VoiceLLMRequest) -> VoiceLLMResponse:
        """
        处理单个请求
        
        Args:
            request: 语音LLM请求
            
        Returns:
            处理响应
        """
        start_time = time.time()
        
        try:
            print(f"[AI] 处理语音LLM请求: {request.text[:50]}...")
            
            if not self.gemini_client:
                return VoiceLLMResponse(
                    request_id=request.request_id,
                    original_text=request.text,
                    llm_response="",
                    timestamp=time.time(),
                    processing_time=time.time() - start_time,
                    success=False,
                    error="LLM客户端未初始化"
                )
            
            # 强制使用流式处理（已移除传统模式）
            system_prompt = request.system_prompt or self.default_system_prompt
            
            # 创建流式回调函数
            current_response_text = ""
            processed_sentences = []  # 已处理的句子
            
            def stream_callback(chunk_text, is_final):
                nonlocal current_response_text, processed_sentences
                if chunk_text:  # 如果有内容
                    current_response_text += chunk_text
                    print(f"[流式回调] 累积文本长度: {len(current_response_text)}, 新增: {len(chunk_text)} 字符")
                    
                    # 检测完整句子
                    new_sentences = self._detect_complete_sentences_in_stream(current_response_text, processed_sentences)
                    
                    # 处理新检测到的句子
                    for sentence in new_sentences:
                        if sentence.strip():
                            print(f"[实时句子] 检测到完整句子: {sentence}")
                            processed_sentences.append(sentence)
                            
                            # 立即触发VOICEVOX音频合成
                            self._trigger_voice_synthesis(sentence, request.request_id)
                
                if is_final:
                    print(f"[流式完成] 最终文本长度: {len(current_response_text)}")
                    
                    # 处理最后可能剩余的不完整句子
                    remaining_text = self._get_remaining_text(current_response_text, processed_sentences)
                    if remaining_text and remaining_text.strip():
                        print(f"[最终句子] 处理剩余文本: {remaining_text}")
                        self._trigger_voice_synthesis(remaining_text, request.request_id)
                
                # 始终触发回调（包含空内容的结束信号）
                partial_response = VoiceLLMResponse(
                    request_id=request.request_id,
                    original_text=request.text,
                    llm_response=current_response_text,
                    timestamp=time.time(),
                    processing_time=time.time() - start_time,
                    success=True,
                    error=None
                )
                # 调用回调函数传递流式结果
                if self.response_callback:
                    self.response_callback(partial_response)
            
            # 只使用流式生成内容，传递对话历史
            print(f"[流式] 使用Gemini流式API，对话历史长度: {len(self.conversation_history)}")
            full_response_text = self.gemini_client.generate_content_stream(
                prompt=request.text,
                system_prompt=system_prompt,
                conversation_history=self.conversation_history,
                callback=stream_callback
            )
            
            # 创建模拟的GeminiResponse对象
            llm_response = type('GeminiResponse', (), {
                'text': full_response_text,
                'error': None if full_response_text else "流式响应为空"
            })()
            
            # 处理响应
            if llm_response.error:
                return VoiceLLMResponse(
                    request_id=request.request_id,
                    original_text=request.text,
                    llm_response="",
                    timestamp=time.time(),
                    processing_time=time.time() - start_time,
                    success=False,
                    error=llm_response.error
                )
            
            response_text = llm_response.text
            
            # 更新对话历史
            self._update_conversation_history(request.text, response_text)
            
            processing_time = time.time() - start_time
            print(f"[成功] LLM响应完成，耗时: {processing_time:.2f}秒")
            
            return VoiceLLMResponse(
                request_id=request.request_id,
                original_text=request.text,
                llm_response=response_text,
                timestamp=time.time(),
                processing_time=processing_time,
                success=True
            )
            
        except Exception as e:
            print(f"[错误] 处理请求失败: {e}")
            import traceback
            traceback.print_exc()
            
            return VoiceLLMResponse(
                request_id=request.request_id,
                original_text=request.text,
                llm_response="",
                timestamp=time.time(),
                processing_time=time.time() - start_time,
                success=False,
                error=f"处理异常: {str(e)}"
            )
    
    def _create_new_conversation_session(self):
        """创建新的对话会话"""
        try:
            # 生成新的会话ID (基于时间戳)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_session_id = f"conversation_{timestamp}"
            self.current_session_file = os.path.join(self.conversation_sessions_dir, f"{self.current_session_id}.json")
            
            # 创建新的会话文件
            session_data = {
                "session_id": self.current_session_id,
                "created_at": datetime.now().isoformat(),
                "conversation_history": []
            }
            
            with open(self.current_session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            print(f"[会话] 创建新对话会话: {self.current_session_id}")
            
        except Exception as e:
            print(f"[错误] 创建对话会话失败: {e}")
            self.current_session_id = None
            self.current_session_file = None

    def _save_conversation_to_file(self):
        """保存对话历史到文件"""
        try:
            if not self.current_session_file:
                return
            
            session_data = {
                "session_id": self.current_session_id,
                "created_at": datetime.now().isoformat(),
                "conversation_history": self.conversation_history,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.current_session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[错误] 保存对话历史失败: {e}")

    def _update_conversation_history(self, user_text: str, assistant_text: str):
        """
        更新对话历史
        
        Args:
            user_text: 用户输入
            assistant_text: 助手回复
        """
        current_time = datetime.now().isoformat()
        
        # 添加用户消息
        self.conversation_history.append({
            "role": "user",
            "text": user_text,
            "timestamp": current_time
        })
        
        # 添加助手回复
        self.conversation_history.append({
            "role": "assistant", 
            "text": assistant_text,
            "timestamp": current_time
        })
        
        # 不设置历史长度限制，保留所有对话历史
        
        # 保存到文件
        self._save_conversation_to_file()
    
    def submit_voice_text(self, text: str, system_prompt: Optional[str] = None, 
                         user_context: Optional[Dict[str, Any]] = None) -> str:
        """
        提交语音文本进行LLM处理
        
        Args:
            text: 识别出的语音文本
            system_prompt: 自定义系统提示词
            user_context: 用户上下文信息
            
        Returns:
            请求ID
        """
        if not text.strip():
            print("[警告] 空文本，跳过LLM处理")
            return ""
        
        if not self.is_running:
            print("[警告] 处理器未运行，无法提交请求")
            return ""
        
        # 生成请求ID
        request_id = f"req_{int(time.time() * 1000)}_{hash(text) % 10000}"
        
        # 创建请求
        request = VoiceLLMRequest(
            text=text,
            timestamp=time.time(),
            request_id=request_id,
            system_prompt=system_prompt,
            user_context=user_context
        )
        
        # 添加到队列
        try:
            self.request_queue.put(request, timeout=1.0)
            print(f"[日志] 已提交语音文本到LLM: {text[:50]}... (ID: {request_id})")
            return request_id
        except queue.Full:
            print("[错误] 请求队列已满，无法提交")
            return ""
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        # 创建新的会话
        self._create_new_conversation_session()
        print("[清空] 已清空对话历史并创建新会话")
    
    def get_queue_size(self) -> int:
        """获取当前队列大小"""
        return self.request_queue.qsize()
    
    def is_client_ready(self) -> bool:
        """检查LLM客户端是否就绪"""
        return self.gemini_client is not None
    
    def update_api_key(self, api_key: str):
        """
        更新API Key
        
        Args:
            api_key: 新的API Key
        """
        try:
            if not api_key.strip():
                print("[警告] 空的API Key")
                return False
            
            # 停止当前处理
            was_running = self.is_running
            if was_running:
                self.stop_processing()
            
            # 重新初始化客户端
            model = self.config.get('LLM', 'gemini_model', 'gemini-1.5-flash') if self.config else 'gemini-1.5-flash'
            self.gemini_client = GeminiClient(
                api_key=api_key,
                model=model,
                config=self.config
            )
            
            # 测试连接
            if self.gemini_client.test_connection():
                print("[成功] API Key更新成功，连接测试通过")
                
                # 恢复处理（如果之前在运行）
                if was_running:
                    self.start_processing()
                
                return True
            else:
                print("[错误] API Key更新失败，连接测试不通过")
                self.gemini_client = None
                return False
                
        except Exception as e:
            print(f"[错误] 更新API Key失败: {e}")
            self.gemini_client = None
            return False
    
    def _detect_complete_sentences_in_stream(self, full_text: str, processed_sentences: list) -> list:
        """
        在流式文本中检测完整句子
        
        Args:
            full_text: 累积的完整文本
            processed_sentences: 已处理的句子列表
            
        Returns:
            新检测到的完整句子列表
        """
        import re
        
        # 句子结束标点符号（中文、日文、英文）+ 逗号（用于语音停顿）
        sentence_endings = r'[。！？.!?，,、]'
        
        # 按句子标点分割文本
        parts = re.split(f'({sentence_endings})', full_text)
        
        new_sentences = []
        current_sentence = ""
        
        i = 0
        while i < len(parts):
            part = parts[i]
            
            if re.match(sentence_endings, part):
                # 这是一个标点符号
                current_sentence += part
                
                # 检查这个句子是否已经处理过
                if current_sentence.strip() and current_sentence not in processed_sentences:
                    new_sentences.append(current_sentence.strip())
                
                current_sentence = ""
            else:
                # 这是文本内容
                current_sentence += part
            
            i += 1
        
        return new_sentences
    
    def _get_remaining_text(self, full_text: str, processed_sentences: list) -> str:
        """
        获取剩余未处理的文本
        
        Args:
            full_text: 完整文本
            processed_sentences: 已处理的句子列表
            
        Returns:
            剩余的未处理文本
        """
        # 简单实现：移除所有已处理的句子后返回剩余部分
        remaining = full_text
        for sentence in processed_sentences:
            remaining = remaining.replace(sentence, "", 1)
        
        return remaining.strip()
    
    def _trigger_voice_synthesis(self, sentence: str, request_id: str):
        """
        触发VOICEVOX语音合成
        
        Args:
            sentence: 要合成的句子
            request_id: 请求ID
        """
        try:
            print(f"[语音合成] 开始合成句子: {sentence}")
            
            # 这里需要调用VOICEVOX API
            # 由于这个方法在voice_llm_handler中，需要通过某种方式访问主应用的VOICEVOX功能
            # 可以通过回调函数或者事件系统来实现
            
            # 创建合成请求事件
            synthesis_event = {
                'type': 'voice_synthesis_request',
                'text': sentence,
                'request_id': request_id,
                'timestamp': time.time(),
                'priority': 'realtime'  # 实时优先级
            }
            
            # 触发语音合成回调（如果有的话）
            if hasattr(self, 'voice_synthesis_callback') and self.voice_synthesis_callback:
                self.voice_synthesis_callback(synthesis_event)
            else:
                print(f"[警告] 未设置语音合成回调，无法合成: {sentence}")
                
        except Exception as e:
            print(f"[错误] 触发语音合成失败: {e}")
    
    def set_voice_synthesis_callback(self, callback):
        """设置语音合成回调函数"""
        self.voice_synthesis_callback = callback
        print("[设置] 已设置语音合成回调函数")