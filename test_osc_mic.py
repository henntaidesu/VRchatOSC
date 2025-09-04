#!/usr/bin/env python3
"""
测试OSC麦克风状态读取
"""

import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.osc_client import OSCClient


def test_osc_mic_detection():
    print("=" * 50)
    print("    OSC麦克风状态检测测试")
    print("=" * 50)
    
    # 创建OSC客户端
    osc_client = OSCClient()
    
    # 设置回调来监听参数变化
    def on_parameter_change(param_name, value):
        if param_name in ["Voice", "VoiceLevel", "Viseme"]:
            print(f"[参数] {param_name}: {value}")
        elif param_name == "vrc_speaking_state":
            status = "开始说话" if value else "停止说话"
            print(f"[状态变化] {status}")
    
    def on_message_received(msg_type, content):
        print(f"[消息] {msg_type}: {content}")
    
    osc_client.set_parameter_callback(on_parameter_change)
    osc_client.set_message_callback(on_message_received)
    
    # 启动OSC服务器
    print("启动OSC服务器...")
    if not osc_client.start_server():
        print("❌ OSC服务器启动失败")
        return False
    
    print("✅ OSC服务器启动成功")
    print("\n请在VRChat中:")
    print("1. 确保OSC功能已启用 (Settings -> OSC -> Enabled)")
    print("2. 按住Push-to-Talk键或开启Voice Activity说话")
    print("3. 观察下方的状态变化")
    print("\n按Ctrl+C退出测试\n")
    
    try:
        last_speaking = False
        last_voice_level = 0.0
        
        while True:
            current_speaking = osc_client.get_vrc_speaking_state()
            current_voice_level = osc_client.get_vrc_voice_level()
            
            # 只在状态或音量变化时输出
            if current_speaking != last_speaking or abs(current_voice_level - last_voice_level) > 0.01:
                status = "🎤 说话中" if current_speaking else "🔇 静音"
                print(f"[实时状态] {status} | 音量: {current_voice_level:.3f}")
                
                last_speaking = current_speaking
                last_voice_level = current_voice_level
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\n测试结束")
        osc_client.stop_server()
        return True
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        osc_client.stop_server()
        return False


if __name__ == "__main__":
    test_osc_mic_detection()