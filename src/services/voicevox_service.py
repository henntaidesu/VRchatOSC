# -*- coding: utf-8 -*-
"""
VOICEVOX语音合成服务层
负责处理VOICEVOX相关的纯业务逻辑，与UI层分离
"""

import threading
import time

try:
    from src.VOICEVOX.voicevox_tts import VOICEVOXClient
    VOICEVOX_CLIENT_AVAILABLE = True
except ImportError:
    VOICEVOX_CLIENT_AVAILABLE = False


class VoicevoxService:
    """VOICEVOX语音合成业务服务"""
    
    def __init__(self, config_manager):
        """
        初始化VOICEVOX服务
        
        Args:
            config_manager: 配置管理器
        """
        self.config = config_manager
        self.voicevox_client = None
        self.voicevox_connected = False
        self.voicevox_enabled = True
        
        # 语音参数
        self.voice_params = {
            'speed_scale': 1.0,
            'pitch_scale': 0.0,
            'intonation_scale': 1.0,
            'volume_scale': 1.0
        }
        
        # 回调函数
        self.connection_status_callback = None
        self.log_callback = None
    
    def set_callbacks(self, connection_status_cb=None, log_cb=None):
        """设置回调函数"""
        if connection_status_cb:
            self.connection_status_callback = connection_status_cb
        if log_cb:
            self.log_callback = log_cb
    
    def log(self, message: str):
        """日志记录"""
        if self.log_callback:
            self.log_callback(message)
    
    def init_voicevox(self, retry_count=3):
        """初始化VOICEVOX客户端"""
        def init_in_background():
            # 获取配置的主机和端口
            host = self.config.voicevox_host
            port = self.config.voicevox_port
            
            for attempt in range(retry_count):
                try:
                    self.log(f"正在尝试连接VOICEVOX Engine {host}:{port}... (第{attempt + 1}次)")
                    
                    if not VOICEVOX_CLIENT_AVAILABLE:
                        raise Exception("VOICEVOX客户端模块不可用")
                    
                    # 创建客户端实例
                    self.voicevox_client = VOICEVOXClient(host=host, port=port)
                    
                    # 测试连接
                    if self.voicevox_client.test_connection():
                        try:
                            # 获取角色列表
                            speakers_list = self.voicevox_client.get_speakers_list()
                            if speakers_list:
                                self.voicevox_connected = True
                                
                                # 通知UI层连接成功
                                if self.connection_status_callback:
                                    self.connection_status_callback(True, speakers_list, host, port)
                                
                                self.log(f"VOICEVOX连接成功！已加载{len(speakers_list)}个角色")
                                return
                            else:
                                self.log("VOICEVOX连接成功但未获取到角色列表")
                        except Exception as e:
                            self.log(f"获取VOICEVOX角色列表失败: {e}")
                    else:
                        self.log(f"VOICEVOX Engine连接测试失败 (第{attempt + 1}次)")
                        
                except Exception as e:
                    self.log(f"VOICEVOX连接尝试失败 (第{attempt + 1}次): {e}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < retry_count - 1:
                    self.log("等待3秒后重试...")
                    time.sleep(3)
            
            # 所有尝试都失败了
            self.voicevox_connected = False
            error_msg = f"VOICEVOX连接失败！已尝试{retry_count}次。请检查：\n" \
                       f"1. VOICEVOX Engine是否已启动\n" \
                       f"2. 端口50021是否被占用\n" \
                       f"3. 防火墙设置是否正确"
            self.log(error_msg)
            
            # 通知UI层连接失败
            if self.connection_status_callback:
                self.connection_status_callback(False, [], host, port)
        
        # 在后台线程中初始化，避免阻塞UI
        threading.Thread(target=init_in_background, daemon=True).start()
    
    def connect_voicevox(self, host: str = None, port: int = None):
        """手动连接VOICEVOX服务器"""
        def connect_in_background():
            try:
                # 获取连接参数
                host = host or self.config.voicevox_host
                port = port or self.config.voicevox_port
                
                # 验证输入
                if not host:
                    host = "localhost"
                
                if not port:
                    port = 50021
                
                self.log(f"尝试连接VOICEVOX服务器: {host}:{port}")
                
                # 创建新的VOICEVOX客户端实例
                voicevox_client = VOICEVOXClient(host=host, port=port)
                
                # 测试连接
                if voicevox_client.test_connection():
                    # 获取角色列表
                    speakers_list = voicevox_client.get_speakers_list()
                    if speakers_list:
                        # 更新全局客户端实例
                        self.voicevox_client = voicevox_client
                        self.voicevox_connected = True
                        
                        # 通知UI层连接成功
                        if self.connection_status_callback:
                            self.connection_status_callback(True, speakers_list, host, port)
                        
                        self.log(f"VOICEVOX连接成功！服务器: {host}:{port}, 已加载{len(speakers_list)}个角色")
                        return True
                    else:
                        raise Exception("未获取到角色列表")
                else:
                    raise Exception("连接测试失败")
                    
            except Exception as e:
                self.log(f"VOICEVOX连接失败: {e}")
                self.voicevox_connected = False
                
                # 通知UI层连接失败
                if self.connection_status_callback:
                    self.connection_status_callback(False, [], host, port)
                return False
        
        # 在后台线程中连接
        threading.Thread(target=connect_in_background, daemon=True).start()
        return True
    
    def disconnect_voicevox(self):
        """断开VOICEVOX连接"""
        try:
            self.voicevox_connected = False
            if self.voicevox_client:
                self.voicevox_client = None
            
            # 通知UI层连接已断开
            if self.connection_status_callback:
                self.connection_status_callback(False, [], "localhost", 50021)
            
            self.log("VOICEVOX连接已断开")
            return True
            
        except Exception as e:
            self.log(f"断开VOICEVOX连接失败: {e}")
            return False
    
    def get_characters_by_period(self) -> dict:
        """获取按期数分组的角色数据"""
        try:
            if not self.voicevox_connected or not self.voicevox_client:
                return {}
            
            speakers_list = self.voicevox_client.get_speakers_list()
            if not speakers_list:
                return {}
            
            # 按期数分组角色
            period_characters = {"1期": {}, "2期": {}, "3期": {}}
            
            for speaker_item in speakers_list:
                period = speaker_item.get('period', '1期')
                character_name = speaker_item.get('name', '')
                style_name = speaker_item.get('style', '')
                style_id = speaker_item.get('speaker_id', 0)
                display_name = speaker_item.get('display', '')
                
                if not character_name or not style_name:
                    continue
                
                # 确保期数在我们的分组中
                if period not in period_characters:
                    period = "1期"
                
                # 初始化角色条目
                if character_name not in period_characters[period]:
                    period_characters[period][character_name] = {
                        'styles': [],
                        'display_names': []
                    }
                
                # 添加样式信息
                period_characters[period][character_name]['styles'].append({
                    'name': style_name,
                    'id': style_id,
                    'display_name': display_name
                })
                
                period_characters[period][character_name]['display_names'].append(display_name)
            
            return period_characters
            
        except Exception as e:
            self.log(f"获取期数角色数据失败: {e}")
            return {}
    
    def set_character(self, period: str, character_name: str, style_name: str) -> bool:
        """设置VOICEVOX角色"""
        try:
            if not self.voicevox_connected:
                self.log("VOICEVOX未连接，无法设置角色")
                return False
            
            # 获取按期数分组的角色数据
            period_characters = self.get_characters_by_period()
            
            if (period in period_characters and 
                character_name in period_characters[period]):
                
                # 查找对应的样式ID
                character_data = period_characters[period][character_name]
                style_id = None
                
                for style in character_data['styles']:
                    if style['name'] == style_name:
                        style_id = style['id']
                        break
                
                if style_id is not None:
                    # 保存设置到配置
                    self.config.set_voicevox_last_selection(
                        period=period,
                        character=character_name,
                        speaker_id=str(style_id),
                        speaker_name=character_name,
                        speaker_style=style_name
                    )
                    self.config.save_config()
                    
                    # 更新VOICEVOX客户端的当前说话人
                    self.voicevox_client.set_speaker(style_id, character_name, style_name)
                    
                    # 应用当前语音参数
                    self._apply_voice_parameters()
                    
                    self.log(f"VOICEVOX角色已设置为: {period} - {character_name} - {style_name} (ID: {style_id})")
                    return True
                else:
                    self.log(f"在 {period} 中找不到角色 {character_name} 的样式 {style_name}")
                    return False
            else:
                self.log(f"在 {period} 中找不到角色 {character_name}")
                return False
                
        except Exception as e:
            self.log(f"设置VOICEVOX角色失败: {e}")
            return False
    
    def set_voice_parameters(self, speed: float = None, pitch: float = None, 
                           intonation: float = None, volume: float = None):
        """设置语音参数"""
        try:
            if speed is not None:
                self.voice_params['speed_scale'] = speed
            if pitch is not None:
                self.voice_params['pitch_scale'] = pitch
            if intonation is not None:
                self.voice_params['intonation_scale'] = intonation
            if volume is not None:
                self.voice_params['volume_scale'] = volume
            
            # 应用到VOICEVOX客户端
            if self.voicevox_connected and self.voicevox_client:
                self._apply_voice_parameters()
            
            return True
            
        except Exception as e:
            self.log(f"设置语音参数失败: {e}")
            return False
    
    def _apply_voice_parameters(self):
        """应用语音参数到VOICEVOX客户端"""
        if self.voicevox_client:
            self.voicevox_client.set_voice_parameters(
                speed_scale=self.voice_params['speed_scale'],
                pitch_scale=self.voice_params['pitch_scale'],
                intonation_scale=self.voice_params['intonation_scale'],
                volume_scale=self.voice_params['volume_scale']
            )
    
    def synthesize_speech(self, text: str, return_format: str = "bytes") -> bytes:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            return_format: 返回格式 ("bytes" 或 "numpy")
            
        Returns:
            合成的音频数据，失败时返回None
        """
        try:
            if not self.voicevox_connected or not self.voicevox_client:
                self.log("VOICEVOX未连接，跳过语音合成")
                return None
            
            if not self.voicevox_enabled:
                self.log("VOICEVOX已禁用，跳过语音合成")
                return None
            
            # 确保应用当前语音参数
            self._apply_voice_parameters()
            
            # 合成语音
            wait_for_previous = (return_format == "numpy")
            audio_data = self.voicevox_client.synthesize_speech(text, wait_for_previous=wait_for_previous)
            
            if audio_data:
                self.log(f"VOICEVOX语音合成成功: {text[:20]}...")
                
                # 格式转换
                if return_format == "numpy":
                    try:
                        import soundfile as sf
                        import io
                        import numpy as np
                        
                        # 将bytes数据转换为numpy数组
                        audio_file = io.BytesIO(audio_data)
                        numpy_audio, sample_rate = sf.read(audio_file)
                        
                        self.log(f"音频格式转换成功: numpy数组 (采样率: {sample_rate}Hz)")
                        return numpy_audio
                        
                    except Exception as convert_e:
                        self.log(f"音频格式转换失败: {convert_e}")
                        return audio_data
                else:
                    return audio_data
            else:
                self.log("VOICEVOX语音合成失败")
                return None
                
        except Exception as e:
            self.log(f"VOICEVOX语音合成出错: {e}")
            return None
    
    def test_voice_synthesis(self, test_text: str = None) -> bool:
        """测试语音合成"""
        try:
            if not self.voicevox_connected:
                self.log("VOICEVOX未连接，无法进行测试")
                return False
            
            # 使用默认测试文本
            if not test_text:
                test_text = "こんにちは、VOICEVOX音声合成のテストです。"
            
            self.log(f"正在测试VOICEVOX语音合成...")
            
            # 在后台线程中进行语音合成和播放
            def test_in_background():
                try:
                    # 合成语音
                    audio_data = self.synthesize_speech(test_text)
                    
                    if audio_data and self.voicevox_client:
                        self.voicevox_client.play_audio(audio_data)
                        self.log("VOICEVOX语音测试完成")
                        return True
                    else:
                        self.log("VOICEVOX语音合成失败")
                        return False
                        
                except Exception as e:
                    self.log(f"VOICEVOX测试失败: {e}")
                    return False
            
            # 启动后台测试线程
            threading.Thread(target=test_in_background, daemon=True).start()
            return True
            
        except Exception as e:
            self.log(f"VOICEVOX测试失败: {e}")
            return False
    
    def save_voice_params_preset(self, speaker_name: str, speaker_style: str) -> bool:
        """保存语音参数预设"""
        try:
            if not speaker_name or not speaker_style:
                self.log("角色名称和样式不能为空")
                return False
            
            # 保存到配置文件
            section_name = f"VoicePreset_{speaker_name}_{speaker_style}"
            self.config.set(section_name, 'speed', self.voice_params['speed_scale'])
            self.config.set(section_name, 'pitch', self.voice_params['pitch_scale'])
            self.config.set(section_name, 'intonation', self.voice_params['intonation_scale'])
            self.config.set(section_name, 'volume', self.voice_params['volume_scale'])
            self.config.save_config()
            
            self.log(f"保存语音参数预设: {speaker_name} - {speaker_style}")
            return True
            
        except Exception as e:
            self.log(f"保存语音参数失败: {e}")
            return False
    
    def load_voice_params_preset(self, speaker_name: str, speaker_style: str) -> bool:
        """加载语音参数预设"""
        try:
            section_name = f"VoicePreset_{speaker_name}_{speaker_style}"
            
            # 检查是否存在该预设
            if not self.config.config.has_section(section_name):
                return False
            
            # 加载参数
            speed = self.config.get(section_name, 'speed', 1.0)
            pitch = self.config.get(section_name, 'pitch', 0.0)
            intonation = self.config.get(section_name, 'intonation', 1.0)
            volume = self.config.get(section_name, 'volume', 1.0)
            
            # 更新语音参数
            self.set_voice_parameters(speed, pitch, intonation, volume)
            
            self.log(f"加载语音参数预设: {speaker_name} - {speaker_style}")
            return True
            
        except Exception as e:
            self.log(f"加载语音参数预设失败: {e}")
            return False
    
    def reset_voice_parameters(self):
        """重置语音参数为默认值"""
        try:
            self.voice_params = {
                'speed_scale': 1.0,
                'pitch_scale': 0.0,
                'intonation_scale': 1.0,
                'volume_scale': 1.0
            }
            
            # 应用到VOICEVOX
            if self.voicevox_connected and self.voicevox_client:
                self._apply_voice_parameters()
            
            self.log("语音参数已重置为默认值")
            return True
            
        except Exception as e:
            self.log(f"重置语音参数失败: {e}")
            return False
    
    def check_connection_status(self) -> bool:
        """检查连接状态"""
        if self.voicevox_client:
            try:
                if self.voicevox_client.test_connection():
                    if not self.voicevox_connected:
                        # 从断开连接变为连接成功
                        self.voicevox_connected = True
                        self.log("VOICEVOX连接已恢复")
                        
                        # 通知UI层连接状态变化
                        if self.connection_status_callback:
                            speakers_list = self.voicevox_client.get_speakers_list() or []
                            host = self.config.voicevox_host
                            port = self.config.voicevox_port
                            self.connection_status_callback(True, speakers_list, host, port)
                    return True
                else:
                    if self.voicevox_connected:
                        # 从连接变为断开
                        self.voicevox_connected = False
                        self.log("VOICEVOX连接已断开")
                        
                        # 通知UI层连接状态变化
                        if self.connection_status_callback:
                            self.connection_status_callback(False, [], "localhost", 50021)
                    return False
            except Exception as e:
                if self.voicevox_connected:
                    self.voicevox_connected = False
                    self.log(f"VOICEVOX连接异常: {e}")
                    
                    # 通知UI层连接状态变化
                    if self.connection_status_callback:
                        self.connection_status_callback(False, [], "localhost", 50021)
                return False
        else:
            self.voicevox_connected = False
            return False
    
    def get_voice_parameters(self) -> dict:
        """获取当前语音参数"""
        return self.voice_params.copy()
    
    def get_current_speaker_info(self) -> dict:
        """获取当前说话人信息"""
        if self.voicevox_connected and self.voicevox_client:
            return self.voicevox_client.get_current_speaker_info()
        return {}
    
    def get_connection_status(self) -> dict:
        """获取连接状态信息"""
        return {
            'connected': self.voicevox_connected,
            'enabled': self.voicevox_enabled,
            'client_ready': self.voicevox_client is not None,
            'host': self.config.voicevox_host if self.config else "localhost",
            'port': self.config.voicevox_port if self.config else 50021
        }
    
    def set_enabled(self, enabled: bool):
        """设置VOICEVOX启用状态"""
        self.voicevox_enabled = enabled
        status = "已启用" if enabled else "已禁用"
        self.log(f"VOICEVOX状态: {status}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.voicevox_connected:
                self.disconnect_voicevox()
            self.voicevox_client = None
        except Exception as e:
            self.log(f"清理VOICEVOX服务资源时出错: {e}")
