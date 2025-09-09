#!/usr/bin/env python3
"""
VRC动态语音录音使用示例
演示如何集成VRC麦克风状态监听的动态录音功能
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm.vrc_voice_integration import VRCVoiceIntegration
from src.llm.voice_llm_handler import VoiceLLMHandler
from src.voice.engine import SpeechEngine
from src.osc_client import OSCClient


class VRCDynamicVoiceExample:
    """VRC动态语音录音示例"""
    
    def __init__(self):
        self.osc_client = None
        self.speech_engine = None
        self.llm_handler = None
        self.vrc_integration = None
    
    def setup(self):
        """设置所有组件"""
        print("=== VRC动态语音录音示例 ===")
        print("1. 初始化语音识别引擎...")
        
        # 创建语音识别引擎
        self.speech_engine = SpeechEngine(
            model_size="base",  # 可选: tiny, base, small, medium, large
            device="auto"       # 自动检测GPU/CPU
        )
        
        if not self.speech_engine.is_model_loaded():
            print("❌ 语音识别引擎初始化失败")
            return False
        
        print("✓ 语音识别引擎初始化完成")
        
        # 创建LLM处理器（可选）
        print("2. 初始化LLM处理器...")
        self.llm_handler = VoiceLLMHandler()
        self.llm_handler.start_processing()
        print("✓ LLM处理器初始化完成")
        
        # 创建VRC语音集成
        print("3. 初始化VRC语音集成...")
        self.vrc_integration = VRCVoiceIntegration()
        success = self.vrc_integration.initialize(
            speech_engine=self.speech_engine,
            llm_handler=self.llm_handler
        )
        
        if not success:
            print("❌ VRC语音集成初始化失败")
            return False
        
        # 设置回调
        self.vrc_integration.set_voice_result_callback(self.on_voice_result)
        self.vrc_integration.set_status_change_callback(self.on_status_change)
        self.vrc_integration.set_log_callback(self.on_log)
        
        print("✓ VRC语音集成初始化完成")
        
        # 创建OSC客户端
        print("4. 初始化OSC客户端...")
        self.osc_client = OSCClient()
        self.osc_client.set_parameter_callback(self.on_osc_parameter)
        
        if not self.osc_client.start_server():
            print("❌ OSC服务器启动失败")
            return False
        
        print("✓ OSC客户端初始化完成")
        
        # 启动VRC语音处理
        if not self.vrc_integration.start_processing():
            print("❌ VRC语音处理启动失败")
            return False
        
        print("✓ VRC语音处理已启动")
        print("\n=== 设置完成 ===")
        print("现在可以在VRChat中开始说话测试动态录音功能")
        print("当你按下VRC麦克风按键时，系统会开始录音")
        print("当你释放VRC麦克风按键时，系统会停止录音并进行语音识别")
        return True
    
    def on_osc_parameter(self, parameter_name: str, value):
        """处理OSC参数变化"""
        # 监听vrc_speaking_state参数
        if parameter_name == "vrc_speaking_state":
            # 这是核心：当VRC麦克风状态改变时通知集成器
            self.vrc_integration.on_vrc_speaking_state_changed(
                speaking_state=bool(value),
                voice_level=0.5 if value else 0.0
            )
        
        # 也可以监听其他语音相关参数
        elif parameter_name in ["Voice", "VoiceLevel", "IsSpeaking"]:
            voice_level = float(value) if value else 0.0
            is_speaking = voice_level > 0.01
            
            self.vrc_integration.on_vrc_speaking_state_changed(
                speaking_state=is_speaking,
                voice_level=voice_level
            )
    
    def on_voice_result(self, text: str, is_realtime=False, trigger_reason="", audio_duration=0):
        """处理语音识别结果"""
        print(f"\n🎤 [语音识别结果] {text}")
        print(f"   触发原因: {trigger_reason}")
        print(f"   录音时长: {audio_duration:.2f}秒")
        
        # 在这里可以进一步处理识别结果
        # 例如发送到聊天框、保存到文件等
    
    def on_status_change(self, status_type: str, data):
        """处理状态变化"""
        if status_type == "vrc_voice_dynamic":
            event_type = data.get('event_type', '')
            if event_type == "mic_opened":
                print("🎙️ [状态] VRC麦克风开启，开始录音...")
            elif event_type == "mic_closed":
                print("⏹️ [状态] VRC麦克风关闭，停止录音并处理...")
    
    def on_log(self, message: str):
        """处理日志消息"""
        print(f"📋 {message}")
    
    def run(self):
        """运行示例"""
        if not self.setup():
            print("❌ 初始化失败，退出")
            return
        
        try:
            print("\n🚀 系统运行中...")
            print("💡 使用说明:")
            print("   1. 确保VRChat已启动并启用OSC")
            print("   2. 在VRChat中按住麦克风按键开始说话")
            print("   3. 释放麦克风按键停止说话")
            print("   4. 系统会自动识别你的语音并显示结果")
            print("   5. 按 Ctrl+C 退出程序")
            
            # 显示状态信息
            status = self.vrc_integration.get_status()
            print(f"\n📊 当前状态:")
            print(f"   集成就绪: {status.get('integration_ready', False)}")
            print(f"   语音引擎就绪: {status.get('speech_engine_ready', False)}")
            print(f"   LLM处理器就绪: {status.get('llm_handler_ready', False)}")
            print(f"   录音状态: {status.get('recording_state', 'unknown')}")
            
            # 主循环
            while True:
                time.sleep(1)
                
                # 每10秒显示一次状态
                if int(time.time()) % 10 == 0:
                    status = self.vrc_integration.get_status()
                    if status.get('is_recording', False):
                        duration = status.get('recording_duration', 0)
                        print(f"🔴 正在录音中... ({duration:.1f}秒)")
                
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断，正在退出...")
        except Exception as e:
            print(f"\n❌ 运行时错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        print("🧹 清理资源...")
        
        if self.vrc_integration:
            self.vrc_integration.cleanup()
        
        if self.llm_handler:
            self.llm_handler.stop_processing()
        
        if self.osc_client:
            self.osc_client.stop_server()
        
        print("✅ 清理完成")


def main():
    """主函数"""
    example = VRCDynamicVoiceExample()
    example.run()


if __name__ == "__main__":
    main()