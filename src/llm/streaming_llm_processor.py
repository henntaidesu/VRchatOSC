#!/usr/bin/env python3
"""
流式LLM处理器 - 支持实时句子检测和语音合成
实现功能：
1. 接收语音识别文本，发送给LLM
2. 实时监测LLM回复，检测完整句子
3. 一旦检测到完整句子，立即转换为语音
4. 将语音发送到9003端口
"""

import threading
import queue
import time
import re
import os
import tempfile
import soundfile as sf
import numpy as np
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from .voice_llm_handler import VoiceLLMHandler, VoiceLLMResponse
from remote_audio import RemoteAudioClient


@dataclass
class StreamingSentence:
    """流式句子数据"""
    text: str
    timestamp: float
    is_complete: bool
    request_id: str


class StreamingLLMProcessor:
    """流式LLM处理器"""
    
    def __init__(self, main_app, config=None):
        """
        初始化流式LLM处理器
        
        Args:
            main_app: 主应用程序实例
            config: 配置管理器实例
        """
        self.main_app = main_app
        self.config = config
        
        # LLM处理器
        self.llm_handler = VoiceLLMHandler(config=config)
        
        # 句子检测相关
        self.current_response = ""  # 当前累积的回复文本
        self.processed_sentences = []  # 已处理的句子
        self.sentence_queue = queue.Queue()  # 待处理的句子队列
        
        # 句子分割正则表达式 - 支持中文、日文、英文
        self.sentence_patterns = [
            r'[。！？]+',  # 中文句号、感叹号、问号
            r'[.!?]+\s*',  # 英文句号、感叹号、问号
            r'[。！？.!?]+',  # 混合标点
        ]
        
        # 音频相关
        self.remote_audio_client = None
        self.voice_synthesis_enabled = True
        
        # 处理线程
        self.sentence_processing_thread = None
        self.is_running = False
        
        # 回调函数
        self.sentence_callback: Optional[Callable[[str], None]] = None
        self.additional_callback: Optional[Callable[[VoiceLLMResponse], None]] = None  # 额外的回调
        
        # 对话记录相关
        self.conversation_file_path = None
        self.current_user_input = None
        self._init_conversation_recording()
        
        # 初始化
        self._init_audio_client()
        self._setup_llm_handler()
        
        print("[成功] 流式LLM处理器初始化完成")
    
    def set_additional_callback(self, callback: Callable[[VoiceLLMResponse], None]):
        """设置额外的回调函数"""
        self.additional_callback = callback
        print("[设置] 已设置额外回调函数")
    
    def _on_voice_synthesis_request(self, synthesis_event):
        """
        处理语音合成请求
        
        Args:
            synthesis_event: 语音合成事件
        """
        try:
            sentence = synthesis_event.get('text', '')
            request_id = synthesis_event.get('request_id', '')
            priority = synthesis_event.get('priority', 'normal')
            
            print(f"[实时语音合成] 处理句子: {sentence} (优先级: {priority})")
            
            if not sentence.strip():
                return
            
            # 使用VOICEVOX合成音频
            if hasattr(self.main_app, 'voicevox_area') and self.main_app.voicevox_area:
                # 同步合成音频，返回bytes格式
                audio_result = self.main_app.voicevox_area.synthesize_with_voicevox(
                    sentence.strip(), 
                    return_format="bytes"
                )
                
                if audio_result is not None:
                    print(f"[VOICEVOX] 实时合成成功: {sentence.strip()} (大小: {len(audio_result)} bytes)")
                    
                    # 立即发送音频到9003端口
                    self._send_realtime_audio_to_port9003(audio_result, sentence)
                else:
                    print(f"[VOICEVOX] 实时合成失败: {sentence.strip()}")
            else:
                print(f"[警告] VOICEVOX未初始化，无法合成: {sentence}")
                
        except Exception as e:
            print(f"[错误] 处理语音合成请求失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _send_realtime_audio_to_port9003(self, audio_data: bytes, sentence: str):
        """
        实时发送音频到9003端口
        
        Args:
            audio_data: 音频数据
            sentence: 对应的句子文本
        """
        try:
            import tempfile
            import os
            from remote_audio import RemoteAudioClient
            
            audio_size = len(audio_data)
            ai_host = self.main_app.config.ai_character_host if self.main_app.config else "127.0.0.1"
            
            print(f"[实时音频] 发送到 {ai_host}:9003，句子: {sentence[:20]}..., 大小: {audio_size} bytes")
            
            # 使用RemoteAudioClient发送音频
            client = RemoteAudioClient(host=ai_host, port=9003)
            
            # 保存临时音频文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_audio_path = temp_file.name
            
            # 发送音频文件（实时优先级）
            success = client.play_audio_file(
                temp_audio_path,
                use_queue=True,
                priority=0  # 最高优先级，确保实时播放
            )
            
            # 清理临时文件
            try:
                os.unlink(temp_audio_path)
            except:
                pass
            
            if success:
                print(f"[实时音频] 句子音频发送成功: {sentence[:20]}...")
            else:
                print(f"[实时音频] 句子音频发送失败: {sentence[:20]}...")
                
        except Exception as e:
            print(f"[错误] 实时音频发送失败: {e}")
    
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
            filename = f"conversation_streaming_{start_time}.vsc"
            self.conversation_file_path = os.path.join(self.record_dir, filename)
            
            # 创建文件并写入头部信息
            with open(self.conversation_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# VRChat OSC 对话记录\n")
                f.write(f"# 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 文件格式: VSCode对话记录格式\n")
                f.write(f"# 处理器: 流式LLM处理器\n")
                f.write(f"# ==========================================\n\n")
            
            print(f"[对话记录] 已创建记录文件: {filename}")
            
        except Exception as e:
            print(f"[对话记录] 初始化失败: {e}")
            self.conversation_file_path = None
    
    def _ensure_record_directory(self):
        """确保记录目录存在，不存在则创建"""
        try:
            import os
            
            if not os.path.exists(self.record_dir):
                os.makedirs(self.record_dir, exist_ok=True)
                print(f"[对话记录] 已创建目录: {self.record_dir}")
            else:
                print(f"[对话记录] 目录已存在: {self.record_dir}")
        except Exception as e:
            print(f"[对话记录] 创建目录失败: {e}")
    
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
                f.write(f"[{timestamp}] 用户: {user_input}\n")
                f.write(f"[{timestamp}] AI: {ai_response}\n")
                f.write(f"---\n\n")
            
            print(f"[对话记录] 已记录对话")
            
        except Exception as e:
            print(f"[对话记录] 记录失败: {e}")
            # 如果记录失败，尝试重新初始化
            try:
                self._init_conversation_recording()
                print(f"[对话记录] 重新初始化完成，尝试再次记录")
                # 重新尝试记录
                with open(self.conversation_file_path, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] 用户: {user_input}\n")
                    f.write(f"[{timestamp}] AI: {ai_response}\n")
                    f.write(f"---\n\n")
                print(f"[对话记录] 重新记录成功")
            except Exception as retry_e:
                print(f"[对话记录] 重新记录也失败: {retry_e}")
    
    def _init_audio_client(self):
        """初始化音频客户端"""
        try:
            # 从配置文件获取AI主机地址
            ai_host = "127.0.0.1"  # 默认值
            if self.config:
                try:
                    ai_host = self.config.ai_character_host
                    if ai_host and ai_host != "127.0.0.1":
                        print(f"[配置] 使用配置的AI主机地址: {ai_host}")
                    else:
                        print(f"[配置] 使用默认AI主机地址: {ai_host}")
                except Exception as e:
                    print(f"[警告] 读取配置主机地址失败，使用默认值: {e}")
            
            # 创建远程音频客户端实例
            self.remote_audio_client = RemoteAudioClient(host=ai_host, port=9003)
            print(f"[成功] 远程音频客户端已创建 ({ai_host}:9003)")
        except Exception as e:
            print(f"[错误] 初始化音频客户端失败: {e}")
            self.remote_audio_client = None
    
    def _setup_llm_handler(self):
        """设置LLM处理器"""
        # 设置LLM响应回调为流式处理
        self.llm_handler.set_response_callback(self._on_llm_streaming_response)
        
        # 设置语音合成回调
        self.llm_handler.set_voice_synthesis_callback(self._on_voice_synthesis_request)
        
        # 启动LLM处理器
        if self.llm_handler.is_client_ready():
            self.llm_handler.start_processing()
        else:
            print("[警告] LLM客户端未就绪")
    
    def start_processing(self):
        """启动流式处理"""
        if self.is_running:
            print("[警告] 流式处理器已在运行")
            return
        
        self.is_running = True
        
        # 启动句子处理线程
        self.sentence_processing_thread = threading.Thread(
            target=self._sentence_processing_loop, 
            daemon=True
        )
        self.sentence_processing_thread.start()
        
        print("[成功] 流式处理器已启动")
    
    def stop_processing(self):
        """停止流式处理"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止LLM处理器
        if self.llm_handler:
            self.llm_handler.stop_processing()
        
        # 等待处理线程结束
        if self.sentence_processing_thread:
            self.sentence_processing_thread.join(timeout=3.0)
        
        # 音频客户端不需要显式关闭，因为它是基于请求的
        
        print("[停止] 流式处理器已停止")
    
    def submit_voice_text(self, text: str) -> str:
        """
        提交语音文本进行流式LLM处理
        
        Args:
            text: 识别出的语音文本
            
        Returns:
            请求ID
        """
        if not text.strip():
            print("[警告] 空文本，跳过处理")
            return ""
        
        # 存储用户输入以便后续记录对话
        self.current_user_input = text.strip()
        
        # 清空之前的响应状态
        self.current_response = ""
        self.processed_sentences.clear()
        
        # 提交到LLM处理器
        request_id = self.llm_handler.submit_voice_text(text)
        
        if request_id:
            print(f"[流式] 已提交语音文本: {text[:50]}... (ID: {request_id})")
        
        return request_id
    
    def _on_llm_streaming_response(self, response: VoiceLLMResponse):
        """处理LLM流式响应"""
        if not response.success:
            print(f"[错误] LLM处理失败: {response.error}")
            if hasattr(self.main_app, 'log'):
                self.main_app.log(f"[LLM错误] {response.error}")
            return
        
        # 显示LLM返回的完整内容
        print(f"[LLM返回] 完整回复: {response.llm_response}")
        if hasattr(self.main_app, 'log'):
            self.main_app.log(f"[LLM返回] {response.llm_response}")
        
        # 流式处理的重复检测机制
        if not hasattr(self, '_processed_requests'):
            self._processed_requests = set()
        if not hasattr(self, '_last_response_length'):
            self._last_response_length = {}
        
        # 检查是否是新的请求或内容有更新
        current_length = len(response.llm_response)
        last_length = self._last_response_length.get(response.request_id, 0)
        
        # 如果这是已完成的请求且内容没有增长，跳过
        if (response.request_id in self._processed_requests and 
            current_length <= last_length):
            print(f"[重复检测] 跳过重复的LLM响应处理: {response.request_id} (长度: {current_length})")
            if hasattr(self.main_app, 'log'):
                self.main_app.log(f"[重复检测] 跳过重复的LLM响应处理: {response.request_id}")
            return
        
        # 更新长度记录
        self._last_response_length[response.request_id] = current_length
        
        # 如果响应完整，标记为已处理
        if current_length > last_length:
            # 清理旧的记录（保持最近50个请求）
            if len(self._last_response_length) > 50:
                oldest_keys = list(self._last_response_length.keys())[:-25]
                for key in oldest_keys:
                    self._last_response_length.pop(key, None)
                    self._processed_requests.discard(key)

        # 累积响应文本
        self.current_response = response.llm_response

        # 检测完整句子
        new_sentences = self._detect_complete_sentences()

        # 语音合成完全由LLM Handler的voice_synthesis_callback处理
        # 此处只记录检测到的句子，不再使用句子队列进行二次处理
        if new_sentences:
            for sentence in new_sentences:
                print(f"[句子检测] 检测到完整句子: {sentence} (已由LLM Handler处理合成)")
                if hasattr(self.main_app, 'log'):
                    self.main_app.log(f"[句子检测] 检测到完整句子: {sentence[:30]}...")
        else:
            print(f"[流式完成] 无新句子，已处理句子数: {len(self.processed_sentences)}")
            if hasattr(self.main_app, 'log'):
                self.main_app.log(f"[流式完成] 无新句子，已处理句子数: {len(self.processed_sentences)}")
        
        # 调用额外的回调函数
        if self.additional_callback:
            try:
                self.additional_callback(response)
                if hasattr(self.main_app, 'log'):
                    self.main_app.log(f"[回调] 已调用额外回调函数")
            except Exception as e:
                if hasattr(self.main_app, 'log'):
                    self.main_app.log(f"[错误] 额外回调函数执行失败: {e}")
        
        # 注释掉直接的UI显示，由LLM_process.py统一处理
        # if hasattr(self.main_app, 'add_speech_output') and callable(self.main_app.add_speech_output):
        #     self.main_app.add_speech_output(response.llm_response, "AI回复")
        #     if hasattr(self.main_app, 'log'):
        #         self.main_app.log(f"[界面显示] AI回复已显示到语音识别框")
        
        # 记录对话和发送VRChat消息（现在每个响应只会处理一次）
        # 记录对话
        if hasattr(self, 'current_user_input') and self.current_user_input:
            self._record_conversation(self.current_user_input, response.llm_response)
            # 清空当前用户输入
            self.current_user_input = None
            
            # 标记请求为已完成（只有在有用户输入时才是完整的响应）
            self._processed_requests.add(response.request_id)
            print(f"[完成标记] 请求已完成: {response.request_id}")

        # 发送完整回复到AI端VRChat (而不是用户VRChat端)
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
                    self.main_app.log(f"[AI回复→AI端] 文本已发送: {response.llm_response[:50]}...")
                else:
                    self.main_app.log(f"[AI回复→AI端] 文本发送失败: {response.llm_response[:50]}...")
            except Exception as e:
                self.main_app.log(f"[AI回复→AI端] 发送异常: {e}")
        else:
            self.main_app.log("[AI回复] AI端未连接，无法发送文本消息")
    
    def _detect_complete_sentences(self) -> List[str]:
        """
        检测完整句子
        
        Returns:
            新检测到的完整句子列表
        """
        if not self.current_response:
            return []
        
        # 找出所有句子分割点
        sentences = []
        current_text = self.current_response
        
        # 使用正则表达式分割句子
        for pattern in self.sentence_patterns:
            parts = re.split(pattern, current_text)
            if len(parts) > 1:
                # 保留分割符
                temp_sentences = []
                splits = re.findall(pattern, current_text)
                
                for i, part in enumerate(parts[:-1]):
                    if part.strip():
                        sentence = part.strip()
                        if i < len(splits):
                            sentence += splits[i].strip()
                        temp_sentences.append(sentence)
                
                sentences.extend(temp_sentences)
                break
        
        # 过滤出新句子（未处理过的）
        new_sentences = []
        for sentence in sentences:
            if sentence and sentence not in self.processed_sentences:
                if len(sentence.strip()) >= 3:  # 至少3个字符才认为是完整句子
                    new_sentences.append(sentence)
                    self.processed_sentences.append(sentence)
        
        return new_sentences
    
    def _sentence_processing_loop(self):
        """句子处理循环"""
        while self.is_running:
            try:
                # 获取待处理句子
                sentence_data = self.sentence_queue.get(timeout=1.0)
                
                # 处理句子
                self._process_sentence(sentence_data)
                
                # 标记任务完成
                self.sentence_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[错误] 句子处理循环异常: {e}")
    
    def _process_sentence(self, sentence_data: StreamingSentence):
        """
        处理单个句子
        
        Args:
            sentence_data: 句子数据
        """
        try:
            sentence_text = sentence_data.text
            print(f"[处理] 开始处理句子: {sentence_text}")
            
            # 语音合成已由LLM Handler的voice_synthesis_callback处理
            # 此处不再重复合成，避免同一句子被合成两次
            print(f"[句子处理] 句子已通过回调处理合成: {sentence_text}")
            if hasattr(self.main_app, 'log'):
                self.main_app.log(f"[句子处理] 跳过重复合成: {sentence_text[:30]}...")
            
            # 调用句子回调（如果有）
            if self.sentence_callback:
                try:
                    self.sentence_callback(sentence_text)
                except Exception as e:
                    print(f"[错误] 句子回调执行失败: {e}")
            
        except Exception as e:
            print(f"[错误] 处理句子失败: {e}")
            import traceback
            traceback.print_exc()
    
    def set_sentence_callback(self, callback: Callable[[str], None]):
        """
        设置句子处理回调
        
        Args:
            callback: 句子处理回调函数
        """
        self.sentence_callback = callback
        print("[成功] 已设置句子处理回调")
    
    def set_voice_synthesis_enabled(self, enabled: bool):
        """
        设置语音合成开关
        
        Args:
            enabled: 是否启用语音合成
        """
        self.voice_synthesis_enabled = enabled
        status = "启用" if enabled else "禁用"
        print(f"[设置] 语音合成已{status}")
    
    def is_client_ready(self) -> bool:
        """检查客户端是否就绪"""
        return (self.llm_handler and 
                self.llm_handler.is_client_ready() and
                self.is_running)
    
    def get_queue_size(self) -> int:
        """获取句子处理队列大小"""
        return self.sentence_queue.qsize()
    
    def clear_conversation_history(self):
        """清空对话历史"""
        if self.llm_handler:
            self.llm_handler.clear_conversation_history()
    
    def shutdown(self):
        """关闭处理器"""
        self.stop_processing()
        if self.llm_handler:
            self.llm_handler.stop_processing()
        print("[关闭] 流式LLM处理器已关闭")


# 测试代码
if __name__ == "__main__":
    import sys
    import os
    
    # 添加项目根目录到路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # 模拟主应用程序
    class MockMainApp:
        def __init__(self):
            self.voicevox_area = None
            self.client = None
        
        def add_speech_output(self, text, source):
            print(f"[界面输出] [{source}] {text}")
    
    # 创建测试实例
    mock_app = MockMainApp()
    processor = StreamingLLMProcessor(mock_app)
    
    # 启动处理
    processor.start_processing()
    
    try:
        # 模拟测试
        print("开始测试流式处理...")
        request_id = processor.submit_voice_text("你好，今天天气怎么样？")
        
        # 等待处理
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("测试被中断")
    finally:
        processor.shutdown()