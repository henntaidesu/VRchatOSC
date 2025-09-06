#!/usr/bin/env python3
"""
AI角色控制器 - 创建和控制程序驱动的VRChat AI角色
"""

import threading
import time
import random
from typing import Dict, List, Optional, Callable
from enum import Enum


class AIPersonality(Enum):
    """AI人格类型"""
    FRIENDLY = "friendly"       # 友好型
    SHY = "shy"                # 害羞型
    ENERGETIC = "energetic"    # 活泼型
    CALM = "calm"              # 冷静型
    PLAYFUL = "playful"        # 调皮型


class AIBehaviorState(Enum):
    """AI行为状态"""
    IDLE = "idle"              # 待机
    TALKING = "talking"        # 说话中
    LISTENING = "listening"    # 听别人说话
    FOLLOWING = "following"    # 跟随某人
    EXPLORING = "exploring"    # 探索环境


class AICharacter:
    """AI角色控制器"""
    
    def __init__(self, name: str, personality: AIPersonality = AIPersonality.FRIENDLY,
                 avatar_controller=None, voicevox_client=None):
        """初始化AI角色
        
        Args:
            name: AI角色名称
            personality: AI人格类型
            avatar_controller: Avatar控制器
            voicevox_client: 语音合成客户端
        """
        self.name = name
        self.personality = personality
        self.avatar_controller = avatar_controller
        self.voicevox_client = voicevox_client
        
        # AI状态
        self.current_state = AIBehaviorState.IDLE
        self.is_active = False
        self.auto_behavior_enabled = True
        
        # 位置和移动
        self.current_position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.target_position = None
        self.follow_target = None
        
        # 对话系统
        self.conversation_memory = []  # 记忆最近的对话
        self.last_speech_time = 0
        self.speech_cooldown = 5  # 说话间隔(秒)
        
        # 行为线程
        self.behavior_thread = None
        self.behavior_running = False
        
        # 人格化设置
        self.setup_personality_traits()
        
        # 预设对话
        self.setup_dialogue_responses()
    
    def setup_personality_traits(self):
        """根据人格类型设置行为特征"""
        if self.personality == AIPersonality.FRIENDLY:
            self.speech_frequency = 0.3  # 说话频率
            self.movement_speed = 0.5    # 移动速度
            self.expression_intensity = 0.7
            self.greeting_chance = 0.8   # 打招呼概率
            
        elif self.personality == AIPersonality.SHY:
            self.speech_frequency = 0.1
            self.movement_speed = 0.3
            self.expression_intensity = 0.4
            self.greeting_chance = 0.3
            
        elif self.personality == AIPersonality.ENERGETIC:
            self.speech_frequency = 0.5
            self.movement_speed = 0.8
            self.expression_intensity = 0.9
            self.greeting_chance = 0.9
            
        elif self.personality == AIPersonality.CALM:
            self.speech_frequency = 0.2
            self.movement_speed = 0.4
            self.expression_intensity = 0.5
            self.greeting_chance = 0.6
            
        elif self.personality == AIPersonality.PLAYFUL:
            self.speech_frequency = 0.4
            self.movement_speed = 0.7
            self.expression_intensity = 0.8
            self.greeting_chance = 0.7
    
    def setup_dialogue_responses(self):
        """设置预设对话回应"""
        # 根据人格类型设置不同的回应
        base_responses = {
            "greetings": [
                "こんにちは！",
                "はじめまして！",
                "よろしくお願いします！"
            ],
            "reactions": [
                "そうですね！",
                "面白いですね！",
                "なるほど！"
            ],
            "farewells": [
                "またね！",
                "さようなら！",
                "また今度！"
            ]
        }
        
        # 根据人格调整对话风格
        if self.personality == AIPersonality.SHY:
            self.responses = {
                "greetings": ["あ、こんにちは...", "よろしくお願いします..."],
                "reactions": ["はい...", "そうですね..."],
                "farewells": ["また..."]
            }
        elif self.personality == AIPersonality.ENERGETIC:
            self.responses = {
                "greetings": ["こんにちは！！", "やっほー！", "元気だよ～！"],
                "reactions": ["すごい！", "わー！", "楽しいね！！"],
                "farewells": ["またね！！", "バイバイ～！"]
            }
        else:
            self.responses = base_responses
    
    def start_ai_behavior(self):
        """启动AI自动行为"""
        if self.is_active:
            return False
            
        self.is_active = True
        self.behavior_running = True
        self.behavior_thread = threading.Thread(target=self._behavior_loop, daemon=True)
        self.behavior_thread.start()
        
        print(f"AI角色 {self.name} 已激活 (人格: {self.personality.value})")
        return True
    
    def stop_ai_behavior(self):
        """停止AI行为"""
        self.is_active = False
        self.behavior_running = False
        print(f"AI角色 {self.name} 已停止")
    
    def _behavior_loop(self):
        """AI行为主循环"""
        while self.behavior_running:
            try:
                current_time = time.time()
                
                # 根据当前状态执行行为
                if self.current_state == AIBehaviorState.IDLE:
                    self._idle_behavior()
                elif self.current_state == AIBehaviorState.TALKING:
                    self._talking_behavior()
                elif self.current_state == AIBehaviorState.LISTENING:
                    self._listening_behavior()
                elif self.current_state == AIBehaviorState.FOLLOWING:
                    self._following_behavior()
                elif self.current_state == AIBehaviorState.EXPLORING:
                    self._exploring_behavior()
                
                # 随机行为触发
                if self.auto_behavior_enabled:
                    self._random_behavior_trigger()
                
                time.sleep(1)  # 行为更新间隔
                
            except Exception as e:
                print(f"AI行为循环错误: {e}")
                time.sleep(5)
    
    def _idle_behavior(self):
        """待机行为"""
        # 随机表情变化
        if random.random() < 0.1:  # 10%概率
            self._random_expression()
        
        # 随机眨眼
        if random.random() < 0.3:  # 30%概率
            self._blink()
    
    def _talking_behavior(self):
        """说话行为"""
        # 说话时的表情和手势
        if self.avatar_controller and self.avatar_controller.is_avatar_connected():
            # 根据说话内容设置嘴部动作
            self.avatar_controller.expression_mapper.set_voice_activity(True, 0.6)
    
    def _listening_behavior(self):
        """听别人说话的行为"""
        # 点头、注视等行为
        pass
    
    def _following_behavior(self):
        """跟随行为"""
        if self.follow_target:
            # 计算移动方向并移动
            pass
    
    def _exploring_behavior(self):
        """探索行为"""
        # 随机移动，探索环境
        pass
    
    def _random_behavior_trigger(self):
        """随机行为触发器"""
        current_time = time.time()
        
        # 随机说话
        if (current_time - self.last_speech_time > self.speech_cooldown and 
            random.random() < self.speech_frequency * 0.1):  # 降低频率
            self._say_random_phrase()
        
        # 随机表情
        if random.random() < 0.05:  # 5%概率
            self._random_expression()
    
    def _say_random_phrase(self, category: str = "reactions"):
        """随机说话"""
        if not self.responses.get(category):
            return
            
        phrase = random.choice(self.responses[category])
        self.say(phrase)
    
    def say(self, text: str, emotion: str = "neutral"):
        """让AI角色说话
        
        Args:
            text: 要说的内容
            emotion: 情感类型
        """
        if not self.voicevox_client or not self.avatar_controller:
            print(f"{self.name}: {text}")  # 如果没有语音合成，就打印文本
            return
        
        try:
            # 设置表情
            if self.avatar_controller.is_avatar_connected():
                # 根据文本分析情感
                detected_emotion = self.avatar_controller.analyze_text_emotion(text)
                if detected_emotion != "neutral":
                    emotion = detected_emotion
                
                # 开始说话状态
                self.avatar_controller.start_speaking(text, emotion, voice_level=0.7)
            
            # 语音合成
            def speak_async():
                try:
                    success = self.voicevox_client.synthesize_and_play(text)
                    if success:
                        print(f"{self.name}: {text}")
                        
                        # 说话完成后停止
                        if self.avatar_controller and self.avatar_controller.is_avatar_connected():
                            # 延迟停止
                            time.sleep(len(text) * 0.15)  # 根据文本长度估算
                            self.avatar_controller.stop_speaking()
                except Exception as e:
                    print(f"AI角色语音合成错误: {e}")
            
            threading.Thread(target=speak_async, daemon=True).start()
            self.last_speech_time = time.time()
            
        except Exception as e:
            print(f"AI角色说话错误: {e}")
    
    def _random_expression(self):
        """随机表情"""
        if not self.avatar_controller or not self.avatar_controller.is_avatar_connected():
            return
        
        emotions = ["happy", "surprise", "neutral"]
        if self.personality == AIPersonality.ENERGETIC:
            emotions = ["happy", "surprise"] * 3 + ["neutral"]  # 更多积极表情
        elif self.personality == AIPersonality.SHY:
            emotions = ["neutral"] * 3 + ["happy"]  # 更多中性表情
        
        emotion = random.choice(emotions)
        intensity = self.expression_intensity * random.uniform(0.5, 1.0)
        self.avatar_controller.set_expression(emotion, intensity)
    
    def _blink(self):
        """眨眼动作"""
        if self.avatar_controller and self.avatar_controller.is_avatar_connected():
            self.avatar_controller.blink(1.0)
    
    # 外部控制接口
    
    def greet_someone(self, target_name: str = ""):
        """向某人打招呼"""
        greeting = random.choice(self.responses.get("greetings", ["こんにちは！"]))
        if target_name:
            greeting = f"{target_name}さん、{greeting}"
        self.say(greeting, "happy")
    
    def react_to_speech(self, speech_text: str, speaker: str = ""):
        """对别人的话做出反应"""
        reaction = random.choice(self.responses.get("reactions", ["そうですね！"]))
        
        # 根据说话内容调整反应
        if any(word in speech_text for word in ["楽しい", "面白い", "すごい"]):
            reaction = random.choice(["そうですね！", "本当ですね！", "面白いですね！"])
            emotion = "happy"
        elif any(word in speech_text for word in ["悲しい", "残念"]):
            reaction = random.choice(["そうですね...", "大丈夫ですか？"])
            emotion = "sad"
        else:
            emotion = "neutral"
        
        # 延迟一点时间再反应，更自然
        def delayed_reaction():
            time.sleep(random.uniform(1, 3))
            self.say(reaction, emotion)
        
        threading.Thread(target=delayed_reaction, daemon=True).start()
    
    def set_follow_target(self, target_name: str):
        """设置跟随目标"""
        self.follow_target = target_name
        self.current_state = AIBehaviorState.FOLLOWING
        print(f"{self.name} 开始跟随 {target_name}")
    
    def stop_following(self):
        """停止跟随"""
        self.follow_target = None
        self.current_state = AIBehaviorState.IDLE
        print(f"{self.name} 停止跟随")
    
    def set_personality(self, personality: AIPersonality):
        """更改AI人格"""
        self.personality = personality
        self.setup_personality_traits()
        self.setup_dialogue_responses()
        print(f"{self.name} 的人格已更改为 {personality.value}")
    
    def get_status(self) -> Dict:
        """获取AI状态"""
        return {
            "name": self.name,
            "personality": self.personality.value,
            "state": self.current_state.value,
            "is_active": self.is_active,
            "position": self.current_position,
            "last_speech": self.last_speech_time
        }