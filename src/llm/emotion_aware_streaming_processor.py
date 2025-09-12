#!/usr/bin/env python3
"""
情感感知流式LLM处理器
结合表情识别功能，根据用户的表情状态调整AI的回复风格
"""

import time
import threading
from typing import Dict, Any, Optional
from .streaming_llm_processor import StreamingLLMProcessor
from .voice_llm_handler import VoiceLLMResponse


class EmotionAwareStreamingProcessor(StreamingLLMProcessor):
    """情感感知的流式LLM处理器"""
    
    def __init__(self, main_app, config=None):
        """
        初始化情感感知流式LLM处理器
        
        Args:
            main_app: 主应用程序实例
            config: 配置管理器实例
        """
        super().__init__(main_app, config)
        
        # 表情状态
        self.current_emotions = {
            'angry': 0.0,
            'disgust': 0.0,
            'fear': 0.0,
            'happy': 0.0,
            'sad': 0.0,
            'surprise': 0.0,
            'neutral': 0.0
        }
        
        # 情感感知开关
        self.emotion_awareness_enabled = True
        
        # 情感历史（用于趋势分析）
        self.emotion_history = []
        self.max_history_length = 10
        
        # 情感系统提示词模板
        self.emotion_prompts = {
            'happy': "用户现在情绪很好，心情愉快。请用轻松、友好、积极的语气回应。可以分享一些有趣或正面的内容。",
            'sad': "用户现在情绪低落，看起来有些难过。请用温和、关怀、安慰的语气回应。避免过于兴奋的内容，多给予理解和支持。",
            'angry': "用户现在看起来有些生气或烦躁。请用冷静、理解、安抚的语气回应。避免争论，多倾听和理解。",
            'fear': "用户现在看起来有些紧张或害怕。请用温和、安心、鼓励的语气回应。给予安全感和支持。",
            'surprise': "用户现在看起来有些惊讶。请用好奇、开放的语气回应，可以询问更多细节或分享相关信息。",
            'disgust': "用户现在看起来有些不悦。请用理解、中性的语气回应，避免可能引起反感的内容。",
            'neutral': "用户现在情绪比较平静。请用自然、友好的语气正常回应。"
        }
        
        print("[成功] 情感感知流式LLM处理器初始化完成")
    
    def update_emotion_state(self, emotions: Dict[str, float]):
        """
        更新用户的情感状态
        
        Args:
            emotions: 情感字典，键为情感名称，值为强度(0.0-1.0)
        """
        # 更新当前情感状态
        for emotion, value in emotions.items():
            if emotion in self.current_emotions:
                self.current_emotions[emotion] = value
        
        # 添加到历史记录
        emotion_record = {
            'timestamp': time.time(),
            'emotions': emotions.copy(),
            'dominant_emotion': self._get_dominant_emotion(emotions)
        }
        
        self.emotion_history.append(emotion_record)
        
        # 保持历史长度限制
        while len(self.emotion_history) > self.max_history_length:
            self.emotion_history.pop(0)
        
        print(f"[情感更新] 主导情感: {emotion_record['dominant_emotion']}, 强度: {emotions.get(emotion_record['dominant_emotion'], 0.0):.2f}")
    
    def _get_dominant_emotion(self, emotions: Dict[str, float]) -> str:
        """
        获取主导情感
        
        Args:
            emotions: 情感字典
            
        Returns:
            主导情感名称
        """
        if not emotions:
            return 'neutral'
        
        # 找到强度最高的情感
        dominant_emotion = max(emotions.items(), key=lambda x: x[1])
        
        # 如果最高强度低于阈值，返回neutral
        if dominant_emotion[1] < 0.3:
            return 'neutral'
        
        return dominant_emotion[0]
    
    def _get_emotion_trend(self) -> str:
        """
        分析情感趋势
        
        Returns:
            情感趋势描述
        """
        if len(self.emotion_history) < 2:
            return "stable"
        
        recent_emotions = [record['dominant_emotion'] for record in self.emotion_history[-3:]]
        
        # 检查是否情感在恶化
        negative_emotions = ['sad', 'angry', 'fear', 'disgust']
        positive_emotions = ['happy', 'surprise']
        
        recent_negative_count = sum(1 for emotion in recent_emotions if emotion in negative_emotions)
        recent_positive_count = sum(1 for emotion in recent_emotions if emotion in positive_emotions)
        
        if recent_negative_count >= 2:
            return "worsening"
        elif recent_positive_count >= 2:
            return "improving"
        else:
            return "stable"
    
    def _generate_emotion_aware_system_prompt(self, user_text: str) -> str:
        """
        生成情感感知的系统提示词
        
        Args:
            user_text: 用户输入文本
            
        Returns:
            系统提示词
        """
        if not self.emotion_awareness_enabled:
            return self.llm_handler.default_system_prompt
        
        # 获取当前主导情感
        dominant_emotion = self._get_dominant_emotion(self.current_emotions)
        emotion_intensity = self.current_emotions.get(dominant_emotion, 0.0)
        
        # 获取情感趋势
        trend = self._get_emotion_trend()
        
        # 构建情感感知提示词
        base_prompt = self.llm_handler.default_system_prompt
        
        emotion_context = self.emotion_prompts.get(dominant_emotion, self.emotion_prompts['neutral'])
        
        # 添加趋势信息
        trend_context = ""
        if trend == "worsening":
            trend_context = "注意用户的情绪似乎在变糟，需要更多关怀和支持。"
        elif trend == "improving":
            trend_context = "用户的情绪似乎在好转，可以适当保持轻松的氛围。"
        
        # 添加强度信息
        intensity_context = ""
        if emotion_intensity > 0.7:
            intensity_context = f"用户的{dominant_emotion}情感很强烈，请特别注意你的回应方式。"
        elif emotion_intensity > 0.5:
            intensity_context = f"用户的{dominant_emotion}情感比较明显。"
        
        emotion_aware_prompt = f"""{base_prompt}

【情感感知信息】
{emotion_context}
{trend_context}
{intensity_context}

请根据用户的情感状态调整你的回复风格，让对话更加自然和贴心。"""
        
        return emotion_aware_prompt
    
    def submit_voice_text(self, text: str) -> str:
        """
        提交带情感感知的语音文本
        
        Args:
            text: 识别出的语音文本
            
        Returns:
            请求ID
        """
        if not text.strip():
            print("[警告] 空文本，跳过处理")
            return ""
        
        # 清空之前的响应状态
        self.current_response = ""
        
        # 生成情感感知的系统提示词
        emotion_system_prompt = self._generate_emotion_aware_system_prompt(text)
        
        # 提交到LLM处理器（使用情感感知的系统提示词）
        request_id = self.llm_handler.submit_voice_text(
            text=text,
            system_prompt=emotion_system_prompt
        )
        
        if request_id:
            dominant_emotion = self._get_dominant_emotion(self.current_emotions)
            print(f"[情感感知LLM] 已提交语音文本: {text[:50]}... (主导情感: {dominant_emotion}, ID: {request_id})")
        
        return request_id
    
    def _on_llm_streaming_response(self, response: VoiceLLMResponse):
        """处理情感感知的LLM流式响应"""
        if not response.success:
            print(f"[错误] 情感感知LLM处理失败: {response.error}")
            if hasattr(self.main_app, 'log'):
                self.main_app.log(f"[情感感知LLM错误] {response.error}")
            return
        
        # 记录情感感知的LLM返回
        dominant_emotion = self._get_dominant_emotion(self.current_emotions)
        emotion_intensity = self.current_emotions.get(dominant_emotion, 0.0)
        
        print(f"[情感感知LLM返回] 回复内容: {response.llm_response}")
        print(f"[情感感知] 已根据用户情感调整回复 - 主导情感: {dominant_emotion} (强度: {emotion_intensity:.2f})")
        
        if hasattr(self.main_app, 'log'):
            self.main_app.log(f"[情感感知LLM] 返回内容: {response.llm_response}")
            self.main_app.log(f"[情感感知] 主导情感: {dominant_emotion} (强度: {emotion_intensity:.2f})")
        
        # 调用父类的响应处理
        super()._on_llm_streaming_response(response)
    
    # _process_sentence 方法已从父类移除，情感处理现在通过 voice_llm_handler 统一处理
    
    def _get_emotion_voice_settings(self, emotion: str) -> Optional[Dict[str, float]]:
        """
        获取情感对应的语音设置
        
        Args:
            emotion: 情感名称
            
        Returns:
            语音参数字典
        """
        emotion_voice_map = {
            'happy': {
                'speed_scale': 1.1,      # 稍快
                'pitch_scale': 0.1,      # 稍高
                'intonation_scale': 1.2, # 更有表现力
                'volume_scale': 1.0
            },
            'sad': {
                'speed_scale': 0.9,      # 稍慢
                'pitch_scale': -0.1,     # 稍低
                'intonation_scale': 0.8,  # 较平淡
                'volume_scale': 0.9       # 稍轻
            },
            'angry': {
                'speed_scale': 1.0,
                'pitch_scale': 0.05,     # 稍高
                'intonation_scale': 1.1,
                'volume_scale': 1.1       # 稍大声
            },
            'fear': {
                'speed_scale': 1.05,     # 稍快，显示紧张
                'pitch_scale': 0.08,     # 稍高
                'intonation_scale': 0.9,
                'volume_scale': 0.95      # 稍轻
            },
            'surprise': {
                'speed_scale': 1.15,     # 较快
                'pitch_scale': 0.12,     # 较高
                'intonation_scale': 1.3,  # 很有表现力
                'volume_scale': 1.0
            },
            'disgust': {
                'speed_scale': 0.95,     # 稍慢
                'pitch_scale': -0.05,    # 稍低
                'intonation_scale': 0.9,
                'volume_scale': 0.95
            },
            'neutral': {
                'speed_scale': 1.0,
                'pitch_scale': 0.0,
                'intonation_scale': 1.0,
                'volume_scale': 1.0
            }
        }
        
        return emotion_voice_map.get(emotion, emotion_voice_map['neutral'])
    
    def _apply_emotion_voice_settings(self, settings: Dict[str, float]):
        """
        应用情感语音设置
        
        Args:
            settings: 语音参数设置
        """
        try:
            if hasattr(self.main_app, 'speed_var'):
                # 保存原始设置（如果需要恢复）
                if not hasattr(self, '_original_voice_settings'):
                    self._original_voice_settings = {
                        'speed_scale': self.main_app.speed_var.get(),
                        'pitch_scale': self.main_app.pitch_var.get(),
                        'intonation_scale': self.main_app.intonation_var.get(),
                        'volume_scale': self.main_app.volume_var.get()
                    }
                
                # 应用情感调整后的设置
                self.main_app.speed_var.set(settings['speed_scale'])
                self.main_app.pitch_var.set(settings['pitch_scale'])
                self.main_app.intonation_var.set(settings['intonation_scale'])
                self.main_app.volume_var.set(settings['volume_scale'])
                
                print(f"[情感语音] 已应用情感语音设置: {settings}")
                
        except Exception as e:
            print(f"[警告] 应用情感语音设置失败: {e}")
    
    def set_emotion_awareness_enabled(self, enabled: bool):
        """
        设置情感感知开关
        
        Args:
            enabled: 是否启用情感感知
        """
        self.emotion_awareness_enabled = enabled
        status = "启用" if enabled else "禁用"
        print(f"[设置] 情感感知已{status}")
    
    def get_emotion_summary(self) -> Dict[str, Any]:
        """
        获取情感状态摘要
        
        Returns:
            情感状态摘要
        """
        dominant_emotion = self._get_dominant_emotion(self.current_emotions)
        trend = self._get_emotion_trend()
        
        return {
            'current_emotions': self.current_emotions.copy(),
            'dominant_emotion': dominant_emotion,
            'emotion_intensity': self.current_emotions.get(dominant_emotion, 0.0),
            'trend': trend,
            'history_length': len(self.emotion_history),
            'awareness_enabled': self.emotion_awareness_enabled
        }
    
    def clear_emotion_history(self):
        """清除情感历史记录"""
        self.emotion_history.clear()
        print("[清除] 已清除情感历史记录")


# 测试代码
if __name__ == "__main__":
    import sys
    import os
    
    # 添加项目根目录到路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    from src.config_manager import config_manager
    
    # 模拟主应用程序
    class MockMainApp:
        def __init__(self):
            self.config = config_manager
            self.voicevox_area = None
            self.client = None
            
            # 模拟语音参数
            import tkinter as tk
            self.speed_var = tk.DoubleVar(value=1.0)
            self.pitch_var = tk.DoubleVar(value=0.0)
            self.intonation_var = tk.DoubleVar(value=1.0)
            self.volume_var = tk.DoubleVar(value=1.0)
        
        def log(self, message):
            print(f"[LOG] {message}")
        
        def add_speech_output(self, text, source):
            print(f"[界面输出] [{source}] {text}")
    
    # 创建测试实例
    mock_app = MockMainApp()
    processor = EmotionAwareStreamingProcessor(mock_app, config_manager)
    
    # 测试情感更新
    print("测试情感感知功能...")
    
    # 模拟不同情感状态
    test_emotions = [
        {'happy': 0.8, 'neutral': 0.2},
        {'sad': 0.7, 'neutral': 0.3},
        {'angry': 0.6, 'disgust': 0.2, 'neutral': 0.2},
        {'surprise': 0.9, 'happy': 0.1}
    ]
    
    for emotions in test_emotions:
        processor.update_emotion_state(emotions)
        summary = processor.get_emotion_summary()
        print(f"情感摘要: {summary}")
        
        # 测试系统提示词生成
        prompt = processor._generate_emotion_aware_system_prompt("你好，今天怎么样？")
        print(f"生成的提示词: {prompt[:200]}...")
        print("-" * 50)
    
    processor.shutdown()
    print("测试完成")