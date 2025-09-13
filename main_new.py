#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRChat OSC 通信工具 - 重构版入口文件

使用分离的UI组件和服务层架构
"""

import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def main():
    """主函数"""
    print("=" * 60)
    print("VRChat OSC 通信工具 - 重构版")
    print("=" * 60)
    print("架构特点:")
    print("- UI组件与业务逻辑分离")
    print("- 按功能区域组织UI组件")
    print("- 独立的服务层处理业务逻辑")
    print("- 清晰的模块依赖关系")
    print("=" * 60)
    print("正在启动...")
    
    try:
        # 导入重构后的GUI类
        from ui import VRChatOSCGUI
        
        # 创建并运行应用
        app = VRChatOSCGUI()
        app.run()
        
    except ImportError as e:
        print(f"导入错误: {e}")
        print("正在尝试启动简化版本...")
        print("注意：某些功能可能不可用")
        
        try:
            from ui import VRChatOSCGUI
            app = VRChatOSCGUI()
            app.run()
        except Exception as retry_e:
            print(f"启动失败: {retry_e}")
            print("请检查以下依赖是否已安装:")
            print("- opencv-python (pip install opencv-python)")
            print("- PIL/Pillow (pip install Pillow)")
            print("- numpy (pip install numpy)")
            print("- tkinter (通常Python内置)")
            sys.exit(1)
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()



