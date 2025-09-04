#!/usr/bin/env python3
"""
语音LLM处理器 - 将语音识别结果发送到LLM进行处理
"""

import threading
import queue
import time
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from .GeminiLLM import GeminiClient, GeminiResponse


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
        self.max_history_length = 10  # 保留最近10轮对话
        
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
            
            # 决定使用哪种处理方式
            if len(self.conversation_history) == 0:
                # 首次对话，使用generate_content
                system_prompt = request.system_prompt or self.default_system_prompt
                llm_response = self.gemini_client.generate_content(
                    prompt=request.text,
                    system_prompt=system_prompt
                )
            else:
                # 多轮对话，使用chat
                llm_response = self.gemini_client.chat(
                    message=request.text,
                    conversation_history=self.conversation_history
                )
            
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
    
    def _update_conversation_history(self, user_text: str, assistant_text: str):
        """
        更新对话历史
        
        Args:
            user_text: 用户输入
            assistant_text: 助手回复
        """
        # 添加用户消息
        self.conversation_history.append({
            "role": "user",
            "text": user_text
        })
        
        # 添加助手回复
        self.conversation_history.append({
            "role": "assistant",
            "text": assistant_text
        })
        
        # 保持历史长度限制
        while len(self.conversation_history) > self.max_history_length * 2:  # *2 因为每轮有用户和助手两条消息
            self.conversation_history.pop(0)
    
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
        print("[清空] 已清空对话历史")
    
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