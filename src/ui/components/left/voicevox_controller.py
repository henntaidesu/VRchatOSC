# -*- coding: utf-8 -*-
"""
VOICEVOX控制UI功能类
负责处理VOICEVOX语音合成相关的UI交互逻辑
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

try:
    from src.VOICEVOX.voicevox_tts import VOICEVOXClient
    VOICEVOX_CLIENT_AVAILABLE = True
except ImportError:
    VOICEVOX_CLIENT_AVAILABLE = False


class VoicevoxController:
    """VOICEVOX控制UI功能类"""
    
    def __init__(self, main_app):
        """
        初始化VOICEVOX控制器
        
        Args:
            main_app: 主应用程序实例
        """
        self.main_app = main_app
        self.voicevox_client = None
        self.voicevox_connected = False
        self.detected_cameras_info = {}
        self.current_styles = []
    
    def safe_log(self, message):
        """线程安全的日志记录方法"""
        try:
            if self.main_app.root and hasattr(self.main_app.root, 'after'):
                self.main_app.root.after(0, lambda: self.main_app.log(message))
        except RuntimeError:
            print(f"[VOICEVOX] {message}")
        except Exception as e:
            print(f"[VOICEVOX] {message} (logging error: {e})")
    
    def safe_ui_update(self, callback):
        """线程安全的UI更新方法"""
        try:
            if self.main_app.root and hasattr(self.main_app.root, 'after'):
                self.main_app.root.after(0, callback)
        except RuntimeError:
            print("[VOICEVOX] Skipped UI update - main thread not in main loop")
        except Exception as e:
            print(f"[VOICEVOX] UI update error: {e}")
    
    def init_voicevox(self, retry_count=3):
        """初始化VOICEVOX客户端"""
        def init_in_background():
            # 获取配置的主机和端口
            host = self.main_app.config.voicevox_host
            port = self.main_app.config.voicevox_port
            
            for attempt in range(retry_count):
                try:
                    log_msg = f"正在尝试连接VOICEVOX Engine {host}:{port}... (第{attempt + 1}次)"
                    self.safe_log(log_msg)
                    
                    # 创建客户端实例
                    self.voicevox_client = VOICEVOXClient(host=host, port=port)
                    
                    # 测试连接
                    if self.voicevox_client.test_connection():
                        try:
                            # 获取角色列表
                            speakers_list = self.voicevox_client.get_speakers_list()
                            if speakers_list:
                                speaker_names = [speaker['display'] for speaker in speakers_list]
                                self.voicevox_connected = True
                                
                                # 更新UI
                                self.safe_ui_update(lambda: self.update_voicevox_ui(speaker_names, True))
                                success_msg = f"VOICEVOX连接成功！已加载{len(speaker_names)}个角色"
                                self.safe_log(success_msg)
                                return
                            else:
                                self.safe_log("VOICEVOX连接成功但未获取到角色列表")
                        except Exception as e:
                            error_msg = f"获取VOICEVOX角色列表失败: {e}"
                            self.safe_log(error_msg)
                    else:
                        fail_msg = f"VOICEVOX Engine连接测试失败 (第{attempt + 1}次)"
                        self.safe_log(fail_msg)
                        
                except Exception as e:
                    error_msg = f"VOICEVOX连接尝试失败 (第{attempt + 1}次): {e}"
                    self.safe_log(error_msg)
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < retry_count - 1:
                    self.safe_log("等待3秒后重试...")
                    time.sleep(3)
            
            # 所有尝试都失败了
            self.voicevox_connected = False
            error_msg = f"VOICEVOX连接失败！已尝试{retry_count}次。请检查：\n" \
                       f"1. VOICEVOX Engine是否已启动\n" \
                       f"2. 端口50021是否被占用\n" \
                       f"3. 防火墙设置是否正确"
            self.safe_log(error_msg)
            self.safe_ui_update(lambda: self.update_voicevox_ui([], False))
        
        # 在后台线程中初始化，避免阻塞UI
        threading.Thread(target=init_in_background, daemon=True).start()
    
    def connect_voicevox(self):
        """手动连接VOICEVOX服务器"""
        def connect_in_background():
            try:
                # 更新按钮状态
                self.safe_ui_update(lambda: self.main_app.voicevox_connect_btn.config(
                    state="disabled", text="正在连接..."))
                self.safe_ui_update(lambda: self.main_app.voicevox_status_label.config(
                    text="正在连接...", foreground="orange"))
                
                # 获取用户输入的IP和端口
                host = self.main_app.voicevox_host_var.get().strip()
                port = self.main_app.voicevox_port_var.get().strip()
                
                # 验证输入
                if not host:
                    host = "localhost"
                    self.main_app.voicevox_host_var.set(host)
                
                if not port:
                    port = "50021"
                    self.main_app.voicevox_port_var.set(port)
                
                try:
                    port = int(port)
                except ValueError:
                    self.safe_ui_update(lambda: messagebox.showerror("VOICEVOX错误", "端口必须是数字"))
                    self.safe_ui_update(lambda: self.main_app.voicevox_connect_btn.config(
                        state="normal", text="连接"))
                    self.safe_ui_update(lambda: self.main_app.voicevox_status_label.config(
                        text="连接失败", foreground="red"))
                    return
                
                self.safe_log(f"尝试连接VOICEVOX服务器: {host}:{port}")
                
                # 创建新的VOICEVOX客户端实例
                voicevox_client = VOICEVOXClient(host=host, port=port)
                
                # 测试连接
                if voicevox_client.test_connection():
                    # 获取角色列表
                    speakers_list = voicevox_client.get_speakers_list()
                    if speakers_list:
                        speaker_names = [speaker['display'] for speaker in speakers_list]
                        
                        # 更新全局客户端实例
                        self.voicevox_client = voicevox_client
                        self.voicevox_connected = True
                        
                        # 更新UI
                        self.safe_ui_update(lambda: self.update_voicevox_ui(speaker_names, True))
                        self.safe_ui_update(lambda: self.main_app.voicevox_connect_btn.config(
                            state="normal", text="重连"))
                        self.safe_log(f"VOICEVOX连接成功！服务器: {host}:{port}, 已加载{len(speaker_names)}个角色")
                    else:
                        raise Exception("未获取到角色列表")
                else:
                    raise Exception("连接测试失败")
                    
            except Exception as e:
                self.safe_log(f"VOICEVOX连接失败: {e}")
                self.voicevox_connected = False
                self.safe_ui_update(lambda: self.update_voicevox_ui([], False))
                self.safe_ui_update(lambda: self.main_app.voicevox_connect_btn.config(
                    state="normal", text="连接"))
                self.safe_ui_update(lambda: messagebox.showerror("连接失败", 
                    f"无法连接到VOICEVOX服务器 {host}:{port}\n\n错误信息: {e}\n\n请检查:\n1. VOICEVOX Engine是否已启动\n2. IP地址和端口是否正确\n3. 防火墙设置"))
        
        # 在后台线程中连接
        threading.Thread(target=connect_in_background, daemon=True).start()
    
    def update_voicevox_ui(self, speaker_names, connected):
        """更新VOICEVOX UI状态"""
        try:
            if connected:
                # 连接成功时，更新Avatar控制器的VOICEVOX客户端
                if hasattr(self.main_app, 'avatar_controller'):
                    self.main_app.avatar_controller.set_voicevox_client(self.voicevox_client)
                
                # 初始化SingleAI管理器
                if not getattr(self.main_app, 'single_ai_manager', None):
                    from src.avatar.single_ai_vrc_manager import SingleAIVRCManager
                    
                    # 获取AI主机地址
                    ai_host = "127.0.0.1"
                    if hasattr(self.main_app, 'ai_vrchat_manager') and self.main_app.ai_vrchat_manager:
                        ai_host = getattr(self.main_app.ai_vrchat_manager, 'ai_host', "127.0.0.1")
                    
                    self.main_app.single_ai_manager = SingleAIVRCManager(
                        voicevox_client=self.voicevox_client,
                        ai_host=ai_host
                    )
                    self.main_app.single_ai_manager.init_voice_queue_manager()
                
                # 显示连接详细信息
                host = self.main_app.voicevox_host_var.get()
                port = self.main_app.voicevox_port_var.get()
                self.main_app.voicevox_status_label.config(
                    text=f"已连接 ({host}:{port})", foreground="green")
                
                # 启用相关控件
                self.main_app.voicevox_character_combo['state'] = 'readonly'
                self.main_app.voicevox_style_combo['state'] = 'readonly'
                self.main_app.voicevox_confirm_btn['state'] = 'normal'
                self.main_app.voicevox_test_btn['state'] = 'normal'
                self.main_app.voicevox_period_combo['state'] = 'readonly'
                
                self.voicevox_connected = True
                
                # 使用配置的期数初始化界面
                saved_period = self.main_app.config.voicevox_last_period
                if saved_period:
                    self.main_app.voicevox_period_var.set(saved_period)
                else:
                    self.main_app.voicevox_period_var.set("3期")  # 默认选择3期
                
                # 触发期数变更以加载对应的角色列表
                self.on_voicevox_period_changed()
                
            else:
                self.main_app.voicevox_status_label.config(text="未连接", foreground="red")
                self.main_app.voicevox_character_combo['values'] = []
                self.main_app.voicevox_style_combo['values'] = []
                
                # 禁用相关控件
                self.main_app.voicevox_character_combo['state'] = 'disabled'
                self.main_app.voicevox_style_combo['state'] = 'disabled'
                self.main_app.voicevox_confirm_btn['state'] = 'disabled'
                self.main_app.voicevox_test_btn['state'] = 'disabled'
                self.main_app.voicevox_period_combo['state'] = 'disabled'
                
                self.voicevox_connected = False
                
        except Exception as e:
            self.safe_log(f"更新VOICEVOX UI失败: {e}")
    
    def get_characters_by_period(self):
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
                    period = "1期"  # 默认分到1期
                
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
            self.safe_log(f"获取期数角色数据失败: {e}")
            return {}
    
    def on_voicevox_period_changed(self, event=None):
        """VOICEVOX期数改变事件处理"""
        try:
            new_period = self.main_app.voicevox_period_var.get()
            if not new_period:
                return
            
            # 获取按期数分组的角色数据
            period_characters = self.get_characters_by_period()
            
            if new_period in period_characters:
                # 更新角色下拉框
                character_list = list(period_characters[new_period].keys())
                self.main_app.voicevox_character_combo['values'] = character_list
                
                # 清空样式选择
                self.main_app.voicevox_style_combo['values'] = []
                self.main_app.voicevox_style_var.set("")
                
                # 尝试恢复用户之前的角色选择
                if character_list:
                    saved_character = self.main_app.config.voicevox_last_character
                    if saved_character and saved_character in character_list:
                        self.main_app.voicevox_character_var.set(saved_character)
                        self.safe_log(f"[VOICEVOX] 恢复用户配置: {saved_character}")
                    else:
                        self.main_app.voicevox_character_var.set(character_list[0])
                        self.safe_log(f"[VOICEVOX] 使用默认角色: {character_list[0]}")
                    
                    self.on_voicevox_character_name_changed()
                else:
                    self.main_app.voicevox_character_var.set("")
            else:
                self.safe_log(f"期数 {new_period} 没有可用角色")
                
        except Exception as e:
            self.safe_log(f"切换VOICEVOX期数失败: {e}")
    
    def on_voicevox_character_name_changed(self, event=None):
        """VOICEVOX角色名称改变事件处理"""
        try:
            if not self.voicevox_connected:
                return
                
            character_name = self.main_app.voicevox_character_var.get()
            current_period = self.main_app.voicevox_period_var.get()
            
            if not character_name or not current_period:
                return
            
            # 获取按期数分组的角色数据
            period_characters = self.get_characters_by_period()
            
            if (current_period in period_characters and 
                character_name in period_characters[current_period]):
                
                # 获取该角色的样式列表
                character_data = period_characters[current_period][character_name]
                styles_list = [style['name'] for style in character_data['styles']]
                self.current_styles = character_data['styles']  # 保存完整样式信息
                
                # 更新样式下拉框
                self.main_app.voicevox_style_combo['values'] = styles_list
                
                # 如果配置中有保存的样式且在当前样式列表中，则选中它
                if (self.main_app.config.voicevox_last_speaker_style and 
                    self.main_app.config.voicevox_last_speaker_style in styles_list):
                    self.main_app.voicevox_style_combo.set(self.main_app.config.voicevox_last_speaker_style)
                elif styles_list:
                    # 否则选择第一个样式
                    self.main_app.voicevox_style_combo.set(styles_list[0])
                    
                self.safe_log(f"角色 {character_name} ({current_period}) 有 {len(styles_list)} 个样式")
            else:
                # 清空样式选择
                self.main_app.voicevox_style_combo['values'] = []
                self.main_app.voicevox_style_var.set("")
                self.current_styles = []
                self.safe_log(f"角色 {character_name} 在 {current_period} 中未找到")
            
        except Exception as e:
            self.safe_log(f"更新VOICEVOX样式列表失败: {e}")
    
    def confirm_voicevox_character_change(self):
        """确认VOICEVOX角色变更"""
        try:
            if not self.voicevox_connected:
                messagebox.showwarning("VOICEVOX警告", "VOICEVOX未连接")
                return
                
            character_name = self.main_app.voicevox_character_var.get()
            style_name = self.main_app.voicevox_style_var.get()
            current_period = self.main_app.voicevox_period_var.get()
            
            if not character_name or not style_name or not current_period:
                messagebox.showwarning("VOICEVOX警告", "请选择期数、角色和样式")
                return
            
            # 获取按期数分组的角色数据
            period_characters = self.get_characters_by_period()
            
            if (current_period in period_characters and 
                character_name in period_characters[current_period]):
                
                # 查找对应的样式ID
                character_data = period_characters[current_period][character_name]
                style_id = None
                
                for style in character_data['styles']:
                    if style['name'] == style_name:
                        style_id = style['id']
                        break
                
                if style_id is not None:
                    # 保存设置到配置
                    self.main_app.config.set_voicevox_last_selection(
                        period=current_period,
                        character=character_name,
                        speaker_id=str(style_id),
                        speaker_name=character_name,
                        speaker_style=style_name
                    )
                    self.main_app.config.save_config()
                    
                    # 更新VOICEVOX客户端的当前说话人
                    self.voicevox_client.set_speaker(style_id, character_name, style_name)
                    
                    # 更新Avatar控制器
                    if hasattr(self.main_app, 'avatar_controller'):
                        self.main_app.avatar_controller.set_voicevox_client(self.voicevox_client)
                    
                    # 加载角色特定的语音参数预设
                    loaded_preset = self.load_voice_params_for_speaker(character_name, style_name)
                    if not loaded_preset:
                        # 使用默认语音参数
                        self.main_app.speed_var.set(1.0)
                        self.main_app.pitch_var.set(0.0)
                        self.main_app.intonation_var.set(1.0)
                        self.main_app.volume_var.set(1.0)
                        
                        # 应用默认参数到VOICEVOX
                        if self.voicevox_client:
                            self.voicevox_client.set_voice_parameters(
                                speed_scale=1.0,
                                pitch_scale=0.0,
                                intonation_scale=1.0,
                                volume_scale=1.0
                            )
                    
                    self.safe_log(f"VOICEVOX角色已切换为: {current_period} - {character_name} - {style_name} (ID: {style_id})")
                    messagebox.showinfo("成功", f"角色切换成功:\n期数: {current_period}\n角色: {character_name}\n样式: {style_name}")
                else:
                    messagebox.showerror("错误", f"在 {current_period} 中找不到角色 {character_name} 的样式 {style_name}")
            else:
                messagebox.showerror("错误", f"在 {current_period} 中找不到角色 {character_name}")
                
        except Exception as e:
            self.safe_log(f"切换VOICEVOX角色失败: {e}")
            messagebox.showerror("错误", f"切换角色失败: {e}")
    
    def test_voicevox(self):
        """测试VOICEVOX语音合成"""
        try:
            if not self.voicevox_connected:
                messagebox.showwarning("VOICEVOX警告", "VOICEVOX未连接")
                return
            
            # 获取当前选择的角色和样式
            character_name = self.main_app.voicevox_character_var.get()
            style_name = self.main_app.voicevox_style_var.get()
            
            if not character_name or not style_name:
                messagebox.showwarning("VOICEVOX警告", "请选择角色和样式")
                return
            
            # 测试文本
            test_text = "こんにちは、VOICEVOX音声合成のテストです。"
            
            # 获取样式ID
            actual_character_name = character_name.split('] ')[-1].split(' - ')[0] if '] ' in character_name else character_name.split(' - ')[0]
            style_id = self.voicevox_client.get_speaker_id_by_name_and_style(actual_character_name, style_name)
            
            if style_id is not None:
                self.safe_log(f"正在测试VOICEVOX语音合成... 角色: {character_name} - {style_name}")
                
                # 在后台线程中进行语音合成
                def synthesize_test():
                    try:
                        # 临时设置说话人用于测试
                        original_speaker = getattr(self.voicevox_client, '_current_speaker_id', None)
                        self.voicevox_client.set_speaker(style_id, actual_character_name, style_name)
                        
                        # 设置当前的语音参数
                        self.voicevox_client.set_voice_parameters(
                            speed_scale=self.main_app.speed_var.get(),
                            pitch_scale=self.main_app.pitch_var.get(),
                            intonation_scale=self.main_app.intonation_var.get(),
                            volume_scale=self.main_app.volume_var.get()
                        )
                        
                        # 合成语音
                        audio_data = self.voicevox_client.synthesize_speech(test_text)
                        
                        if audio_data:
                            self.voicevox_client.play_audio(audio_data)
                            self.safe_log("VOICEVOX语音测试完成")
                            self.safe_ui_update(lambda: messagebox.showinfo("成功", "语音测试完成"))
                        else:
                            self.safe_log("VOICEVOX语音合成失败")
                            self.safe_ui_update(lambda: messagebox.showerror("VOICEVOX错误", "语音合成失败"))
                        
                        # 恢复原来的说话人
                        if original_speaker is not None:
                            self.voicevox_client.set_speaker(original_speaker)
                            
                    except Exception as e:
                        self.safe_log(f"VOICEVOX测试失败: {e}")
                        self.safe_ui_update(lambda: messagebox.showerror("错误", f"语音测试失败: {e}"))
                
                # 启动后台合成线程
                threading.Thread(target=synthesize_test, daemon=True).start()
                
            else:
                messagebox.showerror("错误", "无法找到对应的样式ID")
                
        except Exception as e:
            self.safe_log(f"VOICEVOX测试失败: {e}")
            messagebox.showerror("错误", f"测试失败: {e}")
    
    def synthesize_with_voicevox(self, text, return_format="numpy"):
        """
        使用VOICEVOX合成语音
        
        Args:
            text: 要合成的文本
            return_format: 返回格式 ("bytes" 或 "numpy")
        """
        try:
            if not self.voicevox_connected or not self.voicevox_client:
                self.safe_log("VOICEVOX未连接，跳过语音合成")
                return None
            
            if not self.main_app.voicevox_enabled_var.get():
                self.safe_log("VOICEVOX已禁用，跳过语音合成")
                return None
            
            # 设置当前的语音参数
            self.voicevox_client.set_voice_parameters(
                speed_scale=self.main_app.speed_var.get(),
                pitch_scale=self.main_app.pitch_var.get(),
                intonation_scale=self.main_app.intonation_var.get(),
                volume_scale=self.main_app.volume_var.get()
            )
            
            # 合成语音
            wait_for_previous = (return_format == "numpy")
            audio_data = self.voicevox_client.synthesize_speech(text, wait_for_previous=wait_for_previous)
            
            if audio_data:
                self.safe_log(f"VOICEVOX语音合成成功: {text[:20]}...")
                
                # 格式转换
                if return_format == "numpy":
                    try:
                        import soundfile as sf
                        import io
                        import numpy as np
                        
                        # 将bytes数据转换为numpy数组
                        audio_file = io.BytesIO(audio_data)
                        numpy_audio, sample_rate = sf.read(audio_file)
                        
                        self.safe_log(f"音频格式转换成功: numpy数组 (采样率: {sample_rate}Hz)")
                        return numpy_audio
                        
                    except Exception as convert_e:
                        self.safe_log(f"音频格式转换失败: {convert_e}")
                        return audio_data
                else:
                    return audio_data
            else:
                self.safe_log("VOICEVOX语音合成失败")
                return None
                
        except Exception as e:
            self.safe_log(f"VOICEVOX语音合成出错: {e}")
            return None
    
    def load_voice_params_for_speaker(self, speaker_name, speaker_style):
        """为指定角色加载语音参数预设"""
        try:
            section_name = f"VoicePreset_{speaker_name}_{speaker_style}"
            
            # 检查是否存在该预设
            if not self.main_app.config.config.has_section(section_name):
                return False
            
            # 加载参数
            speed = self.main_app.config.get(section_name, 'speed', 1.0)
            pitch = self.main_app.config.get(section_name, 'pitch', 0.0)
            intonation = self.main_app.config.get(section_name, 'intonation', 1.0)
            volume = self.main_app.config.get(section_name, 'volume', 1.0)
            
            # 应用到界面
            self.main_app.speed_var.set(speed)
            self.main_app.pitch_var.set(pitch)
            self.main_app.intonation_var.set(intonation)
            self.main_app.volume_var.set(volume)
            
            # 应用参数到VOICEVOX
            if self.voicevox_client:
                self.voicevox_client.set_voice_parameters(
                    speed_scale=speed,
                    pitch_scale=pitch,
                    intonation_scale=intonation,
                    volume_scale=volume
                )
            
            self.safe_log(f"加载语音参数预设: {speaker_name} - {speaker_style}")
            return True
            
        except Exception as e:
            self.safe_log(f"加载语音参数预设失败: {e}")
            return False
    
    def start_status_monitoring(self):
        """开始状态监控"""
        def monitor_status():
            self.check_voicevox_status()
            # 每30秒检查一次状态
            self.safe_ui_update(lambda: self.main_app.root.after(30000, monitor_status))
        
        # 启动监控（5秒后开始）
        self.safe_ui_update(lambda: self.main_app.root.after(5000, monitor_status))
    
    def check_voicevox_status(self):
        """检查VOICEVOX连接状态"""
        if self.voicevox_client:
            try:
                if self.voicevox_client.test_connection():
                    if not self.voicevox_connected:
                        # 从断开连接变为连接成功
                        self.voicevox_connected = True
                        host = self.main_app.voicevox_host_var.get()
                        port = self.main_app.voicevox_port_var.get()
                        self.main_app.voicevox_status_label.config(
                            text=f"已连接 ({host}:{port})", foreground="green")
                        self.safe_log("VOICEVOX连接已恢复")
                    return True
                else:
                    if self.voicevox_connected:
                        # 从连接变为断开
                        self.voicevox_connected = False
                        self.main_app.voicevox_status_label.config(
                            text="连接丢失", foreground="red")
                        self.safe_log("VOICEVOX连接已断开")
                    return False
            except Exception as e:
                if self.voicevox_connected:
                    self.voicevox_connected = False
                    self.main_app.voicevox_status_label.config(
                        text="连接异常", foreground="red")
                    self.safe_log(f"VOICEVOX连接异常: {e}")
                return False
        else:
            if hasattr(self, 'voicevox_connected'):
                self.voicevox_connected = False
            return False
