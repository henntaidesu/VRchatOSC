#!/usr/bin/env python3
"""
VRChat OSC 通信工具 - 重构版GUI启动程序
支持文字和语音传输，基于VRChat语音状态的本地Whisper语音识别

注意：这是重构后的版本，采用了新的架构设计
- UI组件与业务逻辑分离  
- 按功能区域组织UI组件
- 独立的服务层处理业务逻辑
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
from ui import VRChatOSCGUI


def main():
    """主启动函数"""
    print("=" * 60)
    print("    VRChat OSC 通信工具 - 重构版")  
    print("    支持本地Whisper语音识别")
    print("    采用分层架构设计")
    print("=" * 60)
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
