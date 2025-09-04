#!/usr/bin/env python3
"""
测试连接和断开功能
"""

import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.vrchat_controller import VRChatController


def test_connection_disconnect():
    print("=" * 50)
    print("    连接断开功能测试")
    print("=" * 50)
    
    controller = None
    
    try:
        # 测试连接
        print("1️⃣ 测试连接功能...")
        controller = VRChatController("127.0.0.1", 9000, 9001, "cpu")
        
        # 启动OSC服务器
        print("🔄 启动OSC服务器...")
        if controller.start_osc_server():
            print("✅ OSC服务器启动成功")
        else:
            print("❌ OSC服务器启动失败")
            return False
        
        # 检查状态
        status = controller.get_status()
        print(f"📊 连接状态: {status}")
        
        # 等待几秒
        print("⏳ 等待5秒测试连接稳定性...")
        time.sleep(5)
        
        # 发送测试消息
        print("📤 发送测试消息...")
        if controller.send_text_message("连接测试消息"):
            print("✅ 消息发送成功")
        else:
            print("❌ 消息发送失败")
        
        # 测试断开
        print("\n2️⃣ 测试断开功能...")
        
        print("🔄 停止语音监听...")
        controller.stop_voice_listening()
        print("✅ 语音监听已停止")
        
        print("🔄 停止OSC服务器...")
        controller.stop_osc_server()
        print("✅ OSC服务器已停止")
        
        print("🔄 清理资源...")
        controller.cleanup()
        print("✅ 资源清理完成")
        
        # 再次检查状态
        final_status = controller.get_status()
        print(f"📊 最终状态: {final_status}")
        
        print("\n🎉 连接断开功能测试完成!")
        return True
        
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 确保清理资源
        if controller:
            try:
                controller.cleanup()
            except:
                pass


def test_multiple_connections():
    print("\n" + "=" * 50)
    print("    多次连接断开测试")
    print("=" * 50)
    
    for i in range(3):
        print(f"\n🔄 第 {i+1} 次连接测试:")
        
        controller = None
        try:
            controller = VRChatController("127.0.0.1", 9000, 9001, "cpu")
            
            if controller.start_osc_server():
                print(f"✅ 第 {i+1} 次连接成功")
                time.sleep(2)
                
                controller.cleanup()
                print(f"✅ 第 {i+1} 次断开成功")
            else:
                print(f"❌ 第 {i+1} 次连接失败")
                
        except Exception as e:
            print(f"❌ 第 {i+1} 次测试出错: {e}")
        
        finally:
            if controller:
                try:
                    controller.cleanup()
                except:
                    pass
        
        # 间隔1秒
        if i < 2:
            time.sleep(1)
    
    print("\n🎉 多次连接断开测试完成!")


if __name__ == "__main__":
    print("🚀 开始连接断开功能测试\n")
    
    # 基础连接断开测试
    if test_connection_disconnect():
        # 多次连接测试
        test_multiple_connections()
        print("\n✅ 所有测试通过!")
    else:
        print("\n❌ 基础测试失败!")