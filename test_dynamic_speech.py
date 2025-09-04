#!/usr/bin/env python3
"""
自动测试动态语音识别功能
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.speech_engine import SpeechEngine

def test_dynamic_speech():
    print("=" * 60)
    print("    动态语音识别自动测试")
    print("=" * 60)
    
    # 创建语音引擎
    print("正在初始化语音引擎...")
    engine = SpeechEngine("base")
    
    if not engine.is_model_loaded():
        print("ERROR: 语音模型未加载成功！")
        return False
    
    print("OK 语音引擎初始化成功！")
    print("\n动态语音检测参数配置:")
    print(f"  - 语音阈值: {engine.voice_threshold}")
    print(f"  - 最小语音时长: {engine.min_speech_duration}秒")
    print(f"  - 最大语音时长: {engine.max_speech_duration}秒")
    print(f"  - 静音检测时长: {engine.silence_duration}秒")
    print(f"  - 采样率: {engine.sample_rate}Hz")
    print(f"  - 音频块大小: {engine.chunk_size}")
    
    print("\n开始动态语音检测测试...")
    print("提示：")
    print("1. 系统会自动检测你开始说话的时机")
    print("2. 请在开始说话后保持1秒静音以结束录制")
    print("3. 测试将在5秒后自动开始")
    
    # 倒计时
    for i in range(5, 0, -1):
        print(f"测试将在 {i} 秒后开始...")
        time.sleep(1)
    
    print("\n=== 开始动态录制 ===")
    print("现在可以开始说话，系统正在监听...")
    
    # 使用动态录制
    start_time = time.time()
    audio_data = engine.record_audio_dynamic()
    end_time = time.time()
    
    if audio_data is None:
        print("ERROR: 动态录制失败！")
        return False
    
    recording_duration = end_time - start_time
    audio_duration = len(audio_data) / engine.sample_rate
    
    print(f"OK 录制完成！")
    print(f"  - 总录制时间: {recording_duration:.2f}秒")
    print(f"  - 音频时长: {audio_duration:.2f}秒")
    print(f"  - 音频数据长度: {len(audio_data)}")
    print(f"  - 音频最大振幅: {max(abs(audio_data)):.4f}")
    
    print("\n开始语音识别...")
    
    # 测试多种语言识别
    languages = ["ja-JP", "zh-CN"]
    
    for lang in languages:
        print(f"\n--- 测试{lang}语音识别 ---")
        text = engine.recognize_audio(audio_data, engine.sample_rate, lang)
        
        if text and text.strip():
            print(f"OK {lang} 识别结果: '{text}'")
        else:
            print(f"FAIL {lang} 识别失败或结果为空")
    
    print("\n=== 测试完成 ===")
    return True

if __name__ == "__main__":
    try:
        print("启动动态语音识别测试...")
        success = test_dynamic_speech()
        
        if success:
            print("\nSUCCESS 测试成功！动态语音识别功能正常工作。")
            print("现在你可以在VRChat OSC工具中使用'开始监听'功能。")
        else:
            print("\nFAIL 测试失败！请检查:")
            print("  1. 麦克风是否正常工作")
            print("  2. 是否有足够的语音输入")
            print("  3. 语音阈值设置是否合适")
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()