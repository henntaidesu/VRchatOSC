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
        
        # 初始化
        self._init_audio_client()
        self._setup_llm_handler()
        
        print("[成功] 流式LLM处理器初始化完成")
    
    def _init_audio_client(self):
        """初始化音频客户端"""
        try:
            # 创建远程音频客户端实例
            self.remote_audio_client = RemoteAudioClient(host="127.0.0.1", port=9003)
            print("[成功] 远程音频客户端已创建 (9003)")
        except Exception as e:
            print(f"[错误] 初始化音频客户端失败: {e}")
            self.remote_audio_client = None
    
    def _setup_llm_handler(self):
        """设置LLM处理器"""
        # 设置LLM响应回调为流式处理
        self.llm_handler.set_response_callback(self._on_llm_streaming_response)
        
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
        
        # 累积响应文本
        self.current_response = response.llm_response
        
        # 检测完整句子
        new_sentences = self._detect_complete_sentences()
        
        # 将新检测到的句子加入处理队列
        for sentence in new_sentences:
            sentence_data = StreamingSentence(
                text=sentence,
                timestamp=time.time(),
                is_complete=True,
                request_id=response.request_id
            )
            
            try:
                self.sentence_queue.put(sentence_data, timeout=0.1)
                print(f"[句子检测] 发现完整句子: {sentence}")
                if hasattr(self.main_app, 'log'):
                    self.main_app.log(f"[句子检测] 发现完整句子: {sentence}")
            except queue.Full:
                print("[警告] 句子处理队列已满")
                if hasattr(self.main_app, 'log'):
                    self.main_app.log("[警告] 句子处理队列已满")
        
        # 显示完整回复到界面
        if hasattr(self.main_app, 'add_speech_output'):
            self.main_app.add_speech_output(response.llm_response, "AI回复")
        
        # 发送完整回复到VRChat
        if hasattr(self.main_app, 'client') and self.main_app.client:
            self.main_app.client.send_text_message(f"[AI] {response.llm_response}")
    
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
            
            # 1. 使用VOICEVOX合成语音
            if self.voice_synthesis_enabled and hasattr(self.main_app, 'voicevox_area'):
                print(f"[语音合成] 开始合成语音: {sentence_text}")
                if hasattr(self.main_app, 'log'):
                    self.main_app.log(f"[语音合成] 开始合成: {sentence_text}")
                
                audio_data = self.main_app.voicevox_area.synthesize_with_voicevox(sentence_text)
                
                if audio_data and isinstance(audio_data, np.ndarray):
                    print(f"[VOICEVOX] 语音合成成功 - 文本: {sentence_text}")
                    if hasattr(self.main_app, 'log'):
                        self.main_app.log(f"[VOICEVOX] 语音合成成功: {sentence_text[:30]}...")
                    
                    # 2. 保存为临时WAV文件
                    try:
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                            temp_audio_path = tmp_file.name
                        
                        # 保存音频数据为WAV文件
                        sf.write(temp_audio_path, audio_data, 22050)  # VOICEVOX通常使用22050Hz
                        print(f"[临时文件] 已保存音频: {temp_audio_path}")
                        
                        # 3. 发送音频文件到9003端口
                        if self.remote_audio_client:
                            try:
                                print(f"[9003发送] 正在发送音频: {sentence_text}")
                                success = self.remote_audio_client.play_audio_file(
                                    temp_audio_path, 
                                    use_queue=True, 
                                    priority=0
                                )
                                if success:
                                    print(f"[9003] ✅ 音频发送成功: {sentence_text}")
                                    if hasattr(self.main_app, 'log'):
                                        self.main_app.log(f"[9003] 音频发送成功: {sentence_text[:30]}...")
                                else:
                                    print(f"[9003] ❌ 音频发送失败: {sentence_text}")
                                    if hasattr(self.main_app, 'log'):
                                        self.main_app.log(f"[9003] 音频发送失败: {sentence_text[:30]}...")
                            except Exception as e:
                                print(f"[错误] 发送音频到9003失败: {e}")
                                if hasattr(self.main_app, 'log'):
                                    self.main_app.log(f"[错误] 发送音频到9003失败: {e}")
                            finally:
                                # 清理临时文件
                                try:
                                    if os.path.exists(temp_audio_path):
                                        os.unlink(temp_audio_path)
                                        print(f"[清理] 已删除临时文件: {temp_audio_path}")
                                except Exception as cleanup_e:
                                    print(f"[警告] 清理临时文件失败: {cleanup_e}")
                        else:
                            print("[警告] 远程音频客户端未创建")
                            # 清理临时文件
                            try:
                                if os.path.exists(temp_audio_path):
                                    os.unlink(temp_audio_path)
                            except:
                                pass
                    
                    except Exception as file_e:
                        print(f"[错误] 保存临时音频文件失败: {file_e}")
                        
                elif audio_data:
                    print(f"[警告] VOICEVOX返回的音频数据格式不支持: {type(audio_data)}")
                else:
                    print(f"[警告] VOICEVOX合成失败: {sentence_text}")
            
            # 4. 调用句子回调（如果有）
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