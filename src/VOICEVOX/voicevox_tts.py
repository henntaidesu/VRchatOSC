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
        
        for speaker in self.speakers:
            for style in speaker['styles']:
                display_name = f"{speaker['name']} - {style['name']}"
                speakers_list.append({
                    "display": display_name,
                    "speaker_id": style['id'],
                    "name": speaker['name'],
                    "style": style['name']
                })
        
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