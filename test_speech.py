#!/usr/bin/env python3
"""
Simple test script to verify speech recognition functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.speech_engine import SpeechEngine

def test_speech_recognition():
    print("=" * 50)
    print("    动态语音识别测试脚本")
    print("=" * 50)
    
    # 创建语音引擎
    print("初始化语音引擎...")
    engine = SpeechEngine("base")
    
    if not engine.is_model_loaded():
        print("语音模型未加载成功！")
        return False
    
    print("语音引擎初始化成功！")
    print("动态语音检测参数:")
    print(f"  - 语音阈值: {engine.voice_threshold}")
    print(f"  - 最小语音时长: {engine.min_speech_duration}秒")
    print(f"  - 最大语音时长: {engine.max_speech_duration}秒")
    print(f"  - 静音检测时长: {engine.silence_duration}秒")
    print()
    
    # 测试固定时长录制
    print("=== 测试1: 固定时长录制 ===")
    input("按回车开始测试固定时长录制（3秒）...")
    
    audio_data = engine.record_audio(duration=3)
    if audio_data is not None:
        text = engine.recognize_audio(audio_data, 16000, "ja-JP")
        if text:
            print(f"固定时长识别结果: {text}")
        else:
            print("固定时长识别失败")
    else:
        print("固定时长录制失败")
    
    print()
    
    # 测试动态录制
    print("=== 测试2: 动态语音检测录制 ===")
    print("提示：系统会自动检测你开始说话和停止说话的时机")
    print("说话后请保持1秒静音以结束录制")
    input("按回车开始测试动态录制...")
    
    # 动态录制音频
    print("等待语音输入（动态检测中）...")
    audio_data = engine.record_audio_dynamic()
    
    if audio_data is None:
        print("动态录制失败！")
        return False
    
    print("动态录制完成，开始识别...")
    
    # 识别音频
    text = engine.recognize_audio(audio_data, 16000, "ja-JP")
    
    if text:
        print(f"动态录制识别结果: {text}")
        return True
    else:
        print("识别失败或未检测到语音")
        return False

if __name__ == "__main__":
    try:
        success = test_speech_recognition()
        if success:
            print("\n测试成功！语音识别功能正常。")
        else:
            print("\n测试失败！请检查麦克风设置和语音输入。")
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()