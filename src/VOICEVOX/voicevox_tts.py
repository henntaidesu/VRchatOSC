#!/usr/bin/env python3
"""
VOICEVOX Text-to-Speech 集成模块
支持多角色语音合成
"""

import requests
import json
import io
import logging
from typing import Dict, List, Optional, Tuple
import pygame
from pathlib import Path


class VOICEVOXClient:
    """VOICEVOX API客户端"""
    
    def __init__(self, host="localhost", port=50021):
        """
        初始化VOICEVOX客户端
        
        Args:
            host: VOICEVOX Engine主机地址
            port: VOICEVOX Engine端口
        """
        self.logger = logging.getLogger(__name__)
        self.base_url = f"http://{host}:{port}"
        self.speakers = []
        self.current_speaker_id = 3  # 默认使用ずんだもん ノーマル
        self.current_speaker_name = "ずんだもん"
        self.current_style_name = "ノーマル"
        
        # 语音参数设置
        self.speed_scale = 1.0      # 语速倍率 (0.5 - 2.0)
        self.pitch_scale = 0.0      # 音高偏移 (-0.15 - 0.15) 
        self.intonation_scale = 1.0 # 抑扬顿挫 (0.0 - 2.0)
        self.volume_scale = 1.0     # 音量倍率 (0.0 - 2.0)
        
        # 初始化pygame音频
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        
        # 加载可用角色
        self.load_speakers()
    
    def load_speakers(self) -> bool:
        """加载可用的VOICEVOX角色"""
        try:
            response = requests.get(f"{self.base_url}/speakers", timeout=5)
            response.raise_for_status()
            
            self.speakers = response.json()
            self.logger.info(f"成功加载 {len(self.speakers)} 个VOICEVOX角色")
            
            # 打印前几个角色用于调试
            for i, speaker in enumerate(self.speakers[:5]):
                self.logger.info(f"角色 {i+1}: {speaker['name']} - 样式数量: {len(speaker['styles'])}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"加载VOICEVOX角色失败: {e}")
            return False
    
    def get_speakers_list(self) -> List[Dict[str, str]]:
        """
        获取格式化的角色列表，用于UI显示
        
        Returns:
            包含角色信息的字典列表 [{"display": "角色名 - 样式", "speaker_id": id, "name": "角色名", "style": "样式"}]
        """
        speakers_list = []
        
        # 定义VOICEVOX角色的期数映射
        character_periods = {
            # 一期角色
            "四国めたん": "1期",
            "ずんだもん": "1期", 
            "春日部つむぎ": "1期",
            "雨晴はう": "1期",
            "波音リツ": "1期",
            "玄野武宏": "1期",
            "白上虎太郎": "1期",
            "青山龍星": "1期",
            "冥鳴ひまり": "1期",
            "九州そら": "1期",
            
            # 二期角色  
            "もち子さん": "2期",
            "剣崎雌雄": "2期",
            "WhiteCUL": "2期",
            "後鬼": "2期",
            "No.7": "2期",
            "ちび式じい": "2期",
            "櫻歌ミコ": "2期",
            "小夜/SAYO": "2期",
            "ナースロボ_タイプT": "2期",
            
            # 三期角色
            "†聖騎士 紅桜†": "3期",
            "雀松朱司": "3期",
            "麒ヶ島宗麟": "3期",
            "春歌ナナ": "3期",
            "猫使アル": "3期",
            "猫使ビィ": "3期",
            "中国うさぎ": "3期",
            "栗田まろん": "3期",
            "あいえるたん": "3期",
            "満別花丸": "3期",
            "琴詠ニア": "3期"
        }
        
        for speaker in self.speakers:
            for style in speaker['styles']:
                # 获取角色期数
                period = character_periods.get(speaker['name'], "其他")
                # 格式化显示名称：[期数] 角色名 - 样式
                display_name = f"[{period}] {speaker['name']} - {style['name']}"
                speakers_list.append({
                    "display": display_name,
                    "speaker_id": style['id'],
                    "name": speaker['name'],
                    "style": style['name'],
                    "period": period
                })
        
        # 按期数和角色名排序
        def sort_key(item):
            period_order = {"1期": 1, "2期": 2, "3期": 3, "其他": 9}
            return (period_order.get(item["period"], 9), item["name"], item["style"])
        
        speakers_list.sort(key=sort_key)
        return speakers_list
    
    def get_periods_list(self) -> List[str]:
        """获取所有可用的期数列表"""
        return ["1期", "2期", "3期"]
    
    def get_speakers_by_period(self, period: str) -> List[Dict[str, str]]:
        """
        根据期数获取角色列表
        
        Args:
            period: 期数 ("1期", "2期", "3期")
            
        Returns:
            指定期数的角色列表
        """
        # 定义VOICEVOX角色的期数映射
        character_periods = {
            # 一期角色
            "四国めたん": "1期",
            "ずんだもん": "1期", 
            "春日部つむぎ": "1期",
            "雨晴はう": "1期",
            "波音リツ": "1期",
            "玄野武宏": "1期",
            "白上虎太郎": "1期",
            "青山龍星": "1期",
            "冥鳴ひまり": "1期",
            "九州そら": "1期",
            
            # 二期角色  
            "もち子さん": "2期",
            "剣崎雌雄": "2期",
            "WhiteCUL": "2期",
            "後鬼": "2期",
            "No.7": "2期",
            "ちび式じい": "2期",
            "櫻歌ミコ": "2期",
            "小夜/SAYO": "2期",
            "ナースロボ_タイプT": "2期",
            
            # 三期角色
            "†聖騎士 紅桜†": "3期",
            "雀松朱司": "3期",
            "麒ヶ島宗麟": "3期",
            "春歌ナナ": "3期",
            "猫使アル": "3期",
            "猫使ビィ": "3期",
            "中国うさぎ": "3期",
            "栗田まろん": "3期",
            "あいえるたん": "3期",
            "満別花丸": "3期",
            "琴詠ニア": "3期"
        }
        
        speakers_list = []
        
        for speaker in self.speakers:
            speaker_period = character_periods.get(speaker['name'], "其他")
            if speaker_period == period:
                for style in speaker['styles']:
                    # 不再显示期数标签，只显示角色名和样式
                    display_name = f"{speaker['name']} - {style['name']}"
                    speakers_list.append({
                        "display": display_name,
                        "speaker_id": style['id'],
                        "name": speaker['name'],
                        "style": style['name'],
                        "period": period
                    })
        
        # 按角色名和样式排序
        speakers_list.sort(key=lambda x: (x["name"], x["style"]))
        return speakers_list
    
    def set_speaker(self, speaker_id: int, speaker_name: str = "", style_name: str = ""):
        """
        设置当前使用的角色
        
        Args:
            speaker_id: 角色样式ID
            speaker_name: 角色名称（用于显示）
            style_name: 样式名称（用于显示）
        """
        self.current_speaker_id = speaker_id
        self.current_speaker_name = speaker_name
        self.current_style_name = style_name
        self.logger.info(f"切换到角色: {speaker_name} - {style_name} (ID: {speaker_id})")
    
    def set_voice_parameters(self, speed_scale: float = None, pitch_scale: float = None, 
                           intonation_scale: float = None, volume_scale: float = None):
        """
        设置语音参数
        
        Args:
            speed_scale: 语速倍率 (0.5 - 2.0)
            pitch_scale: 音高偏移 (-0.15 - 0.15)
            intonation_scale: 抑扬顿挫 (0.0 - 2.0)
            volume_scale: 音量倍率 (0.0 - 2.0)
        """
        if speed_scale is not None:
            self.speed_scale = max(0.5, min(2.0, speed_scale))
        if pitch_scale is not None:
            self.pitch_scale = max(-0.15, min(0.15, pitch_scale))
        if intonation_scale is not None:
            self.intonation_scale = max(0.0, min(2.0, intonation_scale))
        if volume_scale is not None:
            self.volume_scale = max(0.0, min(2.0, volume_scale))
            
        self.logger.info(f"更新语音参数 - 语速: {self.speed_scale:.2f}, 音高: {self.pitch_scale:.3f}, "
                        f"抑扬: {self.intonation_scale:.2f}, 音量: {self.volume_scale:.2f}")
    
    def get_voice_parameters(self) -> Dict[str, float]:
        """获取当前语音参数"""
        return {
            "speed_scale": self.speed_scale,
            "pitch_scale": self.pitch_scale,
            "intonation_scale": self.intonation_scale,
            "volume_scale": self.volume_scale
        }
    
    def synthesize_speech(self, text: str) -> Optional[bytes]:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            
        Returns:
            音频数据（bytes）或None
        """
        try:
            # 第一步：获取音频查询
            query_response = requests.post(
                f"{self.base_url}/audio_query",
                params={"text": text, "speaker": self.current_speaker_id},
                timeout=10
            )
            query_response.raise_for_status()
            audio_query = query_response.json()
            
            # 应用语音参数
            audio_query["speedScale"] = self.speed_scale
            audio_query["pitchScale"] = self.pitch_scale
            audio_query["intonationScale"] = self.intonation_scale
            audio_query["volumeScale"] = self.volume_scale
            
            # 第二步：合成音频
            synthesis_response = requests.post(
                f"{self.base_url}/synthesis",
                params={"speaker": self.current_speaker_id},
                headers={"Content-Type": "application/json"},
                data=json.dumps(audio_query),
                timeout=30
            )
            synthesis_response.raise_for_status()
            
            self.logger.info(f"成功合成语音: {text[:20]}... (角色: {self.current_speaker_name})")
            return synthesis_response.content
            
        except Exception as e:
            self.logger.error(f"语音合成失败: {e}")
            return None
    
    def play_audio(self, audio_data: bytes) -> bool:
        """
        播放音频数据
        
        Args:
            audio_data: 音频字节数据
            
        Returns:
            是否播放成功
        """
        try:
            # 将音频数据转换为pygame可播放的格式
            audio_file = io.BytesIO(audio_data)
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            self.logger.info("开始播放语音")
            return True
            
        except Exception as e:
            self.logger.error(f"播放音频失败: {e}")
            return False
    
    def synthesize_and_play(self, text: str) -> bool:
        """
        合成并播放语音（一体化操作）
        
        Args:
            text: 要合成的文本
            
        Returns:
            是否成功
        """
        if not text.strip():
            return False
            
        audio_data = self.synthesize_speech(text)
        if audio_data:
            return self.play_audio(audio_data)
        return False
    
    def save_audio(self, text: str, output_path: str) -> bool:
        """
        合成语音并保存到文件
        
        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            
        Returns:
            是否保存成功
        """
        try:
            audio_data = self.synthesize_speech(text)
            if not audio_data:
                return False
            
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            
            self.logger.info(f"语音已保存到: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存音频失败: {e}")
            return False
    
    def is_playing(self) -> bool:
        """检查是否正在播放音频"""
        return pygame.mixer.music.get_busy()
    
    def stop_playback(self):
        """停止音频播放"""
        pygame.mixer.music.stop()
        self.logger.info("停止语音播放")
    
    def get_current_speaker_info(self) -> Dict[str, str]:
        """获取当前角色信息"""
        return {
            "name": self.current_speaker_name,
            "style": self.current_style_name,
            "id": str(self.current_speaker_id)
        }
    
    def test_connection(self) -> bool:
        """测试与VOICEVOX Engine的连接"""
        try:
            response = requests.get(f"{self.base_url}/version", timeout=5)
            response.raise_for_status()
            version_info = response.json()
            self.logger.info(f"VOICEVOX Engine连接成功，版本: {version_info}")
            return True
        except Exception as e:
            self.logger.error(f"VOICEVOX Engine连接失败: {e}")
            return False


# 全局VOICEVOX客户端实例
voicevox_client = None

def get_voicevox_client() -> VOICEVOXClient:
    """获取全局VOICEVOX客户端实例"""
    global voicevox_client
    if voicevox_client is None:
        voicevox_client = VOICEVOXClient()
    return voicevox_client


def init_voicevox() -> bool:
    """初始化VOICEVOX客户端"""
    try:
        client = get_voicevox_client()
        return client.test_connection()
    except Exception as e:
        logging.getLogger(__name__).error(f"初始化VOICEVOX失败: {e}")
        return False


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 初始化客户端
    client = VOICEVOXClient()
    
    if client.test_connection():
        print("VOICEVOX连接成功!")
        
        # 显示前10个角色
        speakers_list = client.get_speakers_list()
        print(f"\n可用角色数量: {len(speakers_list)}")
        print("前10个角色:")
        for i, speaker in enumerate(speakers_list[:10]):
            print(f"{i+1:2d}. {speaker['display']} (ID: {speaker['speaker_id']})")
        
        # 测试语音合成
        test_text = "こんにちは、VOICEVOX音声合成のテストです。"
        print(f"\n测试文本: {test_text}")
        
        if client.synthesize_and_play(test_text):
            print("语音合成和播放成功!")
            
            # 等待播放完成
            import time
            while client.is_playing():
                time.sleep(0.1)
            print("播放完成")
        else:
            print("语音合成失败")
    else:
        print("VOICEVOX连接失败，请确保Engine正在运行")