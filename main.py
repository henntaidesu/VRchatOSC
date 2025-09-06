#!/usr/bin/env python3
"""
VRChat OSC 通信工具 - GUI启动程序
支持文字和语音传输，基于VRChat语音状态的本地Whisper语音识别
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.vrchat_osc_gui import VRChatOSCGUI


def main():
    """主启动函数"""
    print("=" * 50)
    print("    VRChat OSC 通信工具 v2.0")
    print("    支持本地Whisper语音识别")
    print("=" * 50)
    print()
    
    try:
        print("启动图形界面...")
        print("提示：在VRChat中启用OSC功能 (Settings → OSC → Enabled)")
        print()
        
        app = VRChatOSCGUI()
        app.run()
        
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行错误: {e}")
        sys.exit(1)
    
    print("\n程序已退出")


if __name__ == "__main__":
    main()