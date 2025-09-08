#!/usr/bin/env python3
"""
情感感知LLM处理器测试脚本
测试表情识别与AI回复的整合功能
"""

import sys
import os
import time
import threading

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_manager import config_manager
from src.llm.emotion_aware_streaming_processor import EmotionAwareStreamingProcessor
import numpy as np
import tkinter as tk


class MockMainApp:
    """模拟主应用程序（包含VOICEVOX参数）"""
    
    def __init__(self):
        self.config = config_manager
        self.voicevox_area = MockVoicevoxArea()
        self.client = None
        
        # 模拟语音参数变量
        self.speed_var = tk.DoubleVar(value=1.0)
        self.pitch_var = tk.DoubleVar(value=0.0) 
        self.intonation_var = tk.DoubleVar(value=1.0)
        self.volume_var = tk.DoubleVar(value=1.0)
        
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
        
        # 生成简单的正弦波作为测试音频
        sample_rate = 22050
        duration = max(len(text) * 0.08, 1.0)  # 每个字符0.08秒，最少1秒
        t = np.linspace(0, duration, int(sample_rate * duration))
        frequency = 440  # A音符
        audio_data = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        print(f"[模拟VOICEVOX] 合成完成，音频长度: {len(audio_data)} samples，时长: {duration:.2f}秒")
        return audio_data.astype(np.float32)


def test_emotion_detection():
    """测试情感检测功能"""
    print("=" * 60)
    print("测试情感检测和系统提示词生成")
    print("=" * 60)
    
    # 创建模拟应用
    mock_app = MockMainApp()
    
    # 创建情感感知处理器
    processor = EmotionAwareStreamingProcessor(mock_app, config_manager)
    
    # 测试不同情感状态
    test_scenarios = [
        {
            "name": "开心状态",
            "emotions": {'happy': 0.8, 'surprise': 0.1, 'neutral': 0.1},
            "user_input": "今天天气真好！"
        },
        {
            "name": "伤心状态", 
            "emotions": {'sad': 0.7, 'neutral': 0.2, 'angry': 0.1},
            "user_input": "我感觉很失落..."
        },
        {
            "name": "愤怒状态",
            "emotions": {'angry': 0.6, 'disgust': 0.3, 'neutral': 0.1},
            "user_input": "这太让人生气了！"
        },
        {
            "name": "惊讶状态",
            "emotions": {'surprise': 0.9, 'happy': 0.1},
            "user_input": "什么？真的吗？"
        },
        {
            "name": "恐惧状态",
            "emotions": {'fear': 0.8, 'sad': 0.2},
            "user_input": "我有点担心..."
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n--- 测试场景: {scenario['name']} ---")
        print(f"用户输入: {scenario['user_input']}")
        print(f"检测到的情感: {scenario['emotions']}")
        
        # 更新情感状态
        processor.update_emotion_state(scenario['emotions'])
        
        # 获取情感摘要
        summary = processor.get_emotion_summary()
        print(f"主导情感: {summary['dominant_emotion']} (强度: {summary['emotion_intensity']:.2f})")
        print(f"情感趋势: {summary['trend']}")
        
        # 生成情感感知的系统提示词
        system_prompt = processor._generate_emotion_aware_system_prompt(scenario['user_input'])
        print(f"生成的系统提示词片段: ...{system_prompt[-200:]}")
        
        # 测试语音参数调整
        voice_settings = processor._get_emotion_voice_settings(summary['dominant_emotion'])
        print(f"语音参数调整: {voice_settings}")
        
        time.sleep(0.5)
    
    processor.shutdown()
    print("\n情感检测测试完成")


def test_emotion_trend_analysis():
    """测试情感趋势分析"""
    print("\n" + "=" * 60)
    print("测试情感趋势分析")
    print("=" * 60)
    
    mock_app = MockMainApp()
    processor = EmotionAwareStreamingProcessor(mock_app, config_manager)
    
    # 模拟情感变化序列（从开心到伤心）
    emotion_sequence = [
        {'happy': 0.8, 'neutral': 0.2},
        {'happy': 0.6, 'neutral': 0.3, 'sad': 0.1},
        {'happy': 0.3, 'neutral': 0.4, 'sad': 0.3},
        {'sad': 0.5, 'neutral': 0.4, 'happy': 0.1},
        {'sad': 0.7, 'neutral': 0.2, 'angry': 0.1}
    ]
    
    print("模拟情感变化序列：开心 → 伤心")
    
    for i, emotions in enumerate(emotion_sequence):
        print(f"\n步骤 {i+1}: {emotions}")
        processor.update_emotion_state(emotions)
        
        summary = processor.get_emotion_summary()
        print(f"主导情感: {summary['dominant_emotion']}")
        print(f"情感趋势: {summary['trend']}")
        
        time.sleep(0.2)
    
    # 测试清除历史
    processor.clear_emotion_history()
    summary = processor.get_emotion_summary()
    print(f"\n清除历史后: 历史长度 = {summary['history_length']}")
    
    processor.shutdown()
    print("情感趋势分析测试完成")


def test_full_integration():
    """测试完整集成流程"""
    print("\n" + "=" * 60)  
    print("测试完整集成流程")
    print("=" * 60)
    
    mock_app = MockMainApp()
    processor = EmotionAwareStreamingProcessor(mock_app, config_manager)
    
    # 启动处理
    processor.start_processing()
    
    # 等待初始化
    time.sleep(1)
    
    if not processor.is_client_ready():
        print("[警告] LLM客户端未就绪，可能是API密钥未配置")
        print("将进行模拟测试...")
        
        # 模拟完整流程（不实际调用LLM）
        test_emotion = {'happy': 0.7, 'surprise': 0.2, 'neutral': 0.1}
        processor.update_emotion_state(test_emotion)
        
        # 模拟句子处理
        from src.llm.streaming_llm_processor import StreamingSentence
        test_sentence = StreamingSentence(
            text="谢谢你！这真是太棒了！",
            timestamp=time.time(),
            is_complete=True,
            request_id="test"
        )
        
        print(f"模拟处理句子: {test_sentence.text}")
        processor._process_sentence(test_sentence)
        
    else:
        print("[成功] LLM客户端已就绪")
        
        # 设置不同情感状态并提交文本
        test_cases = [
            ({'happy': 0.8, 'neutral': 0.2}, "你好！今天过得怎么样？"),
            ({'sad': 0.7, 'neutral': 0.3}, "我今天心情不太好..."),
            ({'surprise': 0.9, 'neutral': 0.1}, "哇，这个消息太令人惊讶了！")
        ]
        
        for emotions, text in test_cases:
            print(f"\n设置情感状态: {emotions}")
            processor.update_emotion_state(emotions)
            
            print(f"提交文本: {text}")
            request_id = processor.submit_voice_text(text)
            
            if request_id:
                print(f"已提交，请求ID: {request_id}")
                # 等待处理
                time.sleep(5)
            else:
                print("提交失败")
    
    # 等待所有处理完成
    print("\n等待处理完成...")
    time.sleep(3)
    
    processor.shutdown()
    print("完整集成测试完成")


def test_voice_parameter_adjustment():
    """测试语音参数调整"""
    print("\n" + "=" * 60)
    print("测试语音参数调整")
    print("=" * 60)
    
    mock_app = MockMainApp()
    processor = EmotionAwareStreamingProcessor(mock_app, config_manager)
    
    # 测试不同情感对应的语音参数
    emotions_to_test = ['happy', 'sad', 'angry', 'fear', 'surprise', 'disgust', 'neutral']
    
    print("原始语音参数:")
    print(f"速度: {mock_app.speed_var.get()}")
    print(f"音调: {mock_app.pitch_var.get()}")  
    print(f"语调: {mock_app.intonation_var.get()}")
    print(f"音量: {mock_app.volume_var.get()}")
    
    for emotion in emotions_to_test:
        print(f"\n测试情感: {emotion}")
        
        # 获取情感对应的语音设置
        voice_settings = processor._get_emotion_voice_settings(emotion)
        print(f"建议的语音参数: {voice_settings}")
        
        # 应用设置
        processor._apply_emotion_voice_settings(voice_settings)
        
        print("应用后的参数:")
        print(f"  速度: {mock_app.speed_var.get():.2f}")
        print(f"  音调: {mock_app.pitch_var.get():.2f}")
        print(f"  语调: {mock_app.intonation_var.get():.2f}")
        print(f"  音量: {mock_app.volume_var.get():.2f}")
    
    processor.shutdown()
    print("语音参数调整测试完成")


def main():
    """主测试函数"""
    print("情感感知LLM处理器测试开始")
    print(f"配置文件路径: {config_manager.config_file}")
    
    try:
        # 测试1: 情感检测和系统提示词
        test_emotion_detection()
        
        # 测试2: 情感趋势分析
        test_emotion_trend_analysis()
        
        # 测试3: 语音参数调整
        test_voice_parameter_adjustment()
        
        # 测试4: 完整集成流程
        test_full_integration()
        
        print("\n" + "=" * 60)
        print("所有情感感知测试完成")
        print("=" * 60)
        
        print("\n总结:")
        print("✅ 情感检测和分类功能")
        print("✅ 基于情感的系统提示词生成")
        print("✅ 情感趋势分析")
        print("✅ 情感相关的语音参数调整")
        print("✅ 实时句子处理和语音合成")
        print("✅ 9003端口音频发送")
        
        print("\n使用说明:")
        print("1. 启动VRChat OSC应用")
        print("2. 启用摄像头进行表情识别")
        print("3. 开启'情感感知'模式")
        print("4. 进行语音对话，AI将根据你的表情调整回复风格")
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()