#!/usr/bin/env python3
"""
音频设备选择工具
用于连接远程音频服务并选择播放设备
"""

import sys
from remote_audio import RemoteAudioClient

def show_devices(devices, current_device_id=None):
    """显示设备列表"""
    print("\n📊 可用音频设备:")
    print("=" * 80)
    
    if not devices:
        print("❌ 未找到任何音频设备")
        return
    
    for device in devices:
        device_id = device['id']
        name = device['name']
        sample_rate = device['sample_rate']
        channels = device['channels']
        
        # 设备状态标识
        status = "✅ 当前" if device_id == current_device_id else "  "
        
        # 设备类型标识和说明
        device_type = device.get('type', 'unknown')
        device_name_lower = name.lower()
        
        if device_type == 'virtual_mic':
            type_icon = "🎤"
            type_desc = "虚拟麦克风"
            extra_info = "💡 用于VRChat AI语音传输"
        else:
            type_icon = "🔊" 
            type_desc = "扬声器"
            extra_info = "💡 普通音频输出设备"
        
        print(f"{status} {type_icon} {device_id:2d}: {name} ({type_desc})")
        print(f"         采样率: {sample_rate:.0f} Hz, 通道数: {channels}")
        print(f"         {extra_info}")
        
        print()

def interactive_device_selection(client):
    """交互式设备选择"""
    while True:
        print("\n🎛️  音频设备管理")
        print("=" * 50)
        print("1. 刷新设备列表")
        print("2. 选择设备")
        print("3. 测试当前设备")
        print("4. 退出")
        
        try:
            choice = input("\n请选择操作 (1-4): ").strip()
            
            if choice == '1':
                print("🔄 正在刷新设备列表...")
                devices = client.list_devices()
                if devices:
                    # 获取当前设备
                    response = client._send_request({"command": "list_devices"})
                    current_device_id = response.get('current_device') if response.get('status') == 'success' else None
                    show_devices(devices, current_device_id)
                else:
                    print("❌ 无法获取设备列表，请检查服务器连接")
            
            elif choice == '2':
                print("🔄 获取设备列表...")
                devices = client.list_devices()
                if not devices:
                    print("❌ 无法获取设备列表")
                    continue
                
                # 获取当前设备
                response = client._send_request({"command": "list_devices"})
                current_device_id = response.get('current_device') if response.get('status') == 'success' else None
                
                show_devices(devices, current_device_id)
                
                try:
                    device_input = input("\n请输入要选择的设备ID (或按回车取消): ").strip()
                    if device_input:
                        device_id = int(device_input)
                        if client.set_device(device_id):
                            print(f"✅ 成功设置设备ID: {device_id}")
                        else:
                            print(f"❌ 设置设备失败")
                    else:
                        print("⏭️  已取消")
                except ValueError:
                    print("❌ 请输入有效的数字")
            
            elif choice == '3':
                print("🧪 测试当前设备连接...")
                if client.ping():
                    print("✅ 服务器连接正常")
                    
                    # 获取当前设备信息
                    response = client._send_request({"command": "list_devices"})
                    if response.get('status') == 'success':
                        current_device_id = response.get('current_device')
                        devices = response.get('devices', [])
                        
                        current_device = next((d for d in devices if d['id'] == current_device_id), None)
                        if current_device:
                            print(f"🎤 当前设备: {current_device['name']} (ID: {current_device_id})")
                            print(f"   采样率: {current_device['sample_rate']} Hz")
                            print(f"   通道数: {current_device['channels']}")
                        else:
                            print(f"🎤 当前设备ID: {current_device_id} (未找到详细信息)")
                    else:
                        print("⚠️  无法获取设备信息")
                else:
                    print("❌ 服务器连接失败")
            
            elif choice == '4':
                print("👋 退出设备选择工具")
                break
            
            else:
                print("❌ 无效的选择，请输入 1-4")
        
        except KeyboardInterrupt:
            print("\n👋 用户中断，退出")
            break
        except EOFError:
            print("\n👋 退出设备选择工具")
            break
        except Exception as e:
            print(f"❌ 操作时出错: {e}")

def main():
    """主函数"""
    print("🎛️  远程音频设备选择工具")
    print("=" * 50)
    
    # 获取服务器地址
    if len(sys.argv) > 1:
        host = sys.argv[1]
    else:
        host = input("请输入AI端IP地址 (默认: 127.0.0.1): ").strip() or "127.0.0.1"
    
    port = 9003
    
    print(f"📡 连接到音频服务: {host}:{port}")
    
    try:
        # 创建客户端
        client = RemoteAudioClient(host=host, port=port)
        
        # 测试连接
        print("🔄 测试连接...")
        if not client.ping():
            print("❌ 无法连接到音频服务")
            print("💡 请确保:")
            print(f"   1. AI端机器 ({host}) 上运行了 python remote_audio.py")
            print("   2. 端口 {port} 未被防火墙阻止")
            print("   3. IP地址正确")
            return
        
        print("✅ 连接成功")
        
        # 获取并显示初始设备列表
        devices = client.list_devices()
        if devices:
            response = client._send_request({"command": "list_devices"})
            current_device_id = response.get('current_device') if response.get('status') == 'success' else None
            show_devices(devices, current_device_id)
        
        # 进入交互式选择
        interactive_device_selection(client)
    
    except Exception as e:
        print(f"❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()