#!/usr/bin/env python3
"""
流式LLM处理器测试脚本
用于验证语音识别 -> LLM -> 实时句子分割 -> VOX语音合成 -> 9003端口发送的完整流程
"""

import sys
import os
import time
import threading

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_manager import config_manager
from src.llm.streaming_llm_processor import StreamingLLMProcessor


class MockMainApp:
    """模拟主应用程序"""
    
    def __init__(self):
        self.config = config_manager
        self.voicevox_area = MockVoicevoxArea()
        self.client = None
        
    def log(self, message):
        """模拟日志输出"""
        print(f"[LOG] {message}")
    
    def add_speech_output(self, text, source):
        """模拟语音输出显示"""
        print(f"[界面输出] [{source}] {text}")


class MockVoicevoxArea:
    """模拟VOICEVOX区域"""
    
    def synthesize_with_voicevox(self, text):
        """模拟VOICEVOX语音合成"""
        print(f"[模拟VOICEVOX] 正在合成语音: {text}")
        
        # 模拟返回numpy音频数据
        import numpy as np
        
        # 生成简单的正弦波作为测试音频
        sample_rate = 22050
        duration = len(text) * 0.1  # 每个字符0.1秒
        t = np.linspace(0, duration, int(sample_rate * duration))
        frequency = 440  # A音符
        audio_data = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        print(f"[模拟VOICEVOX] 合成完成，音频长度: {len(audio_data)} samples")
        return audio_data.astype(np.float32)


def test_sentence_detection():
    """测试句子检测功能"""
    print("=" * 50)
    print("测试句子检测功能")
    print("=" * 50)
    
    # 创建模拟应用
    mock_app = MockMainApp()
    
    # 创建流式处理器
    processor = StreamingLLMProcessor(mock_app, config_manager)
    
    # 设置句子回调
    def sentence_callback(sentence):
        print(f"[句子回调] 检测到完整句子: {sentence}")
    
    processor.set_sentence_callback(sentence_callback)
    
    # 测试句子检测
    test_responses = [
        "你好！今天天气很好。希望你过得愉快！",
        "こんにちは。今日はいい天気ですね？ありがとうございます！",
        "Hello! How are you today? I hope you're doing well.",
        "这是一个测试。包含多个句子！最后一句没有标点"
    ]
    
    print("测试不同语言的句子分割:")
    for i, response in enumerate(test_responses):
        print(f"\n测试 {i+1}: {response}")
        processor.current_response = response
        processor.processed_sentences.clear()
        
        sentences = processor._detect_complete_sentences()
        print(f"检测到的句子: {sentences}")
    
    processor.shutdown()
    print("\n句子检测测试完成")


def test_streaming_mode():
    """测试流式处理模式"""
    print("\n" + "=" * 50)
    print("测试流式处理模式")
    print("=" * 50)
    
    # 创建模拟应用
    mock_app = MockMainApp()
    
    # 创建流式处理器
    processor = StreamingLLMProcessor(mock_app, config_manager)
    
    # 启动处理
    processor.start_processing()
    
    # 等待初始化完成
    time.sleep(1)
    
    if not processor.is_client_ready():
        print("[警告] LLM客户端未就绪，可能是API密钥未配置")
        print("请在配置文件中设置Gemini API密钥以进行完整测试")
    else:
        print("[成功] LLM客户端已就绪")
        
        # 提交测试文本
        test_texts = [
            "你好，请介绍一下你自己。",
            "今天天气怎么样？",
            "能帮我写一首短诗吗？"
        ]
        
        for text in test_texts:
            print(f"\n提交测试文本: {text}")
            request_id = processor.submit_voice_text(text)
            if request_id:
                print(f"已提交，请求ID: {request_id}")
                # 等待处理
                time.sleep(3)
            else:
                print("提交失败")
    
    # 等待所有处理完成
    print("\n等待处理完成...")
    time.sleep(5)
    
    processor.shutdown()
    print("流式处理测试完成")


def test_audio_integration():
    """测试音频集成"""
    print("\n" + "=" * 50)
    print("测试音频集成")
    print("=" * 50)
    
    # 检查是否有9003端口服务运行
    import socket
    
    def check_port_open(host, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    if check_port_open("127.0.0.1", 9003):
        print("[成功] 检测到9003端口服务正在运行")
    else:
        print("[警告] 9003端口服务未运行")
        print("请启动remote_audio.py服务以进行完整测试")
        
    # 创建模拟应用
    mock_app = MockMainApp()
    
    # 创建流式处理器
    processor = StreamingLLMProcessor(mock_app, config_manager)
    processor.start_processing()
    
    # 测试音频合成和发送
    test_sentences = [
        "这是一个测试句子。",
        "Testing audio synthesis.",
        "テストの文章です。"
    ]
    
    for sentence in test_sentences:
        print(f"\n测试句子: {sentence}")
        
        # 创建模拟句子数据
        from src.llm.streaming_llm_processor import StreamingSentence
        sentence_data = StreamingSentence(
            text=sentence,
            timestamp=time.time(),
            is_complete=True,
            request_id="test"
        )
        
        processor._process_sentence(sentence_data)
        time.sleep(2)
    
    processor.shutdown()
    print("音频集成测试完成")


def main():
    """主测试函数"""
    print("流式LLM处理器测试开始")
    print(f"配置文件路径: {config_manager.config_file}")
    
    try:
        # 测试1: 句子检测
        test_sentence_detection()
        
        # 测试2: 流式处理
        test_streaming_mode()
        
        # 测试3: 音频集成
        test_audio_integration()
        
        print("\n" + "=" * 50)
        print("所有测试完成")
        print("=" * 50)
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()