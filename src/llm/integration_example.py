#!/usr/bin/env python3
"""
LLM集成示例 - 展示如何将语音识别与LLM功能集成
"""

import sys
import os
import time

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config_manager import config_manager
from voice.engine import SpeechEngine
from llm.voice_llm_handler import VoiceLLMHandler, VoiceLLMResponse


class VoiceLLMIntegration:
    """语音LLM集成类 - 示例实现"""
    
    def __init__(self):
        """初始化集成"""
        self.config = config_manager
        
        # 初始化语音引擎
        print("[语音] 初始化语音引擎...")
        self.speech_engine = SpeechEngine(
            model_size="medium",  # 可以根据需求调整
            device="auto",
            config=self.config
        )
        
        # 初始化LLM处理器
        print("[AI] 初始化LLM处理器...")
        self.llm_handler = VoiceLLMHandler(config=self.config)
        self.llm_handler.set_response_callback(self.on_llm_response)
        
        # 检查是否启用LLM
        if self.config.enable_llm and self.llm_handler.is_client_ready():
            self.llm_handler.start_processing()
            print("[成功] LLM功能已启用")
        else:
            print("[警告] LLM功能未启用或配置不完整")
    
    def on_llm_response(self, response: VoiceLLMResponse):
        """
        LLM响应回调
        
        Args:
            response: LLM响应数据
        """
        print(f"\n{'='*50}")
        print(f"[日志] 原始语音: {response.original_text}")
        
        if response.success:
            print(f"[AI] LLM回复: {response.llm_response}")
            print(f"[时间] 处理耗时: {response.processing_time:.2f}秒")
            
            # 这里可以添加其他处理，比如：
            # 1. 将回复发送到VRChat OSC
            # 2. 保存到聊天记录
            # 3. 触发其他动作
            
        else:
            print(f"[错误] LLM处理失败: {response.error}")
        
        print(f"{'='*50}\n")
    
    def start_voice_llm_loop(self):
        """开始语音LLM循环"""
        if not self.speech_engine.is_model_loaded():
            print("[错误] 语音引擎模型未加载，无法开始")
            return
        
        print("[目标] 开始语音LLM交互循环...")
        print("说话时会自动识别并发送到LLM处理")
        print("按Ctrl+C退出\n")
        
        try:
            while True:
                # 录制语音
                print("[语音] 等待语音输入...")
                audio_data = self.speech_engine.record_audio_dynamic()
                
                if audio_data is None:
                    print("[警告] 未录制到音频数据")
                    continue
                
                # 识别语音
                print("[搜索] 识别语音中...")
                text = self.speech_engine.recognize_audio(
                    audio_data, 
                    self.speech_engine.sample_rate,
                    self.config.voice_language
                )
                
                if not text:
                    print("[警告] 未识别到文本")
                    continue
                
                print(f"[目标] 识别结果: {text}")
                
                # 发送到LLM处理
                if self.config.enable_llm and self.llm_handler.is_client_ready():
                    request_id = self.llm_handler.submit_voice_text(text)
                    if request_id:
                        print(f"📤 已提交到LLM处理 (ID: {request_id})")
                else:
                    print("[警告] LLM功能未启用，跳过处理")
                
                # 等待一小段时间再进行下一轮
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n👋 用户终止程序")
        except Exception as e:
            print(f"[错误] 运行异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def process_single_text(self, text: str):
        """
        处理单个文本（用于测试）
        
        Args:
            text: 要处理的文本
        """
        print(f"[日志] 处理文本: {text}")
        
        if self.config.enable_llm and self.llm_handler.is_client_ready():
            request_id = self.llm_handler.submit_voice_text(text)
            if request_id:
                print(f"📤 已提交到LLM处理 (ID: {request_id})")
                
                # 等待处理完成
                time.sleep(5)
            else:
                print("[错误] 提交失败")
        else:
            print("[警告] LLM功能未启用或配置不完整")
    
    def cleanup(self):
        """清理资源"""
        if hasattr(self, 'llm_handler'):
            self.llm_handler.stop_processing()
        print("🧹 资源清理完成")


def main():
    """主函数 - 演示如何使用"""
    print("[启动] VRChat OSC 语音LLM集成示例")
    print("=" * 50)
    
    # 检查配置
    if not config_manager.enable_llm:
        print("[警告] LLM功能未在配置中启用")
        print("请在设置中启用LLM功能并配置API Key")
        return
    
    if not config_manager.gemini_api_key:
        print("[警告] 未配置Gemini API Key")
        print("请在设置中配置有效的API Key")
        return
    
    # 创建集成实例
    integration = VoiceLLMIntegration()
    
    # 选择运行模式
    print("\n选择运行模式:")
    print("1. 语音循环模式 (持续录音和处理)")
    print("2. 文本测试模式 (输入文本测试LLM)")
    
    choice = input("请选择 (1/2): ").strip()
    
    if choice == '1':
        integration.start_voice_llm_loop()
    elif choice == '2':
        while True:
            text = input("\n请输入测试文本 (输入'quit'退出): ").strip()
            if text.lower() == 'quit':
                break
            if text:
                integration.process_single_text(text)
            time.sleep(2)  # 等待处理
    else:
        print("无效选择")
    
    integration.cleanup()


if __name__ == "__main__":
    main()