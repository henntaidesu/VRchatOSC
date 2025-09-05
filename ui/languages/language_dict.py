#!/usr/bin/env python3
"""
多语言支持字典
支持中文、日语、英语三种语言的界面文本
使用JSON格式存储语言数据
"""

import json
import os

class LanguageManager:
    """语言管理器，负责加载和管理JSON格式的语言文件"""
    
    def __init__(self):
        self.language_dir = os.path.dirname(__file__)
        self._languages = {}
        self._load_languages()
    
    def _load_languages(self):
        """加载所有语言文件"""
        language_files = {
            'zh': 'zh.json',
            'ja': 'ja.json', 
            'en': 'en.json'
        }
        
        for lang_code, filename in language_files.items():
            file_path = os.path.join(self.language_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._languages[lang_code] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Warning: Could not load language file {filename}: {e}")
                self._languages[lang_code] = {}
    
    def get_text(self, language_code: str, key: str, default: str = None) -> str:
        """
        根据语言代码和键值获取对应的文本
        
        Args:
            language_code: 语言代码 ('zh', 'ja', 'en')
            key: 文本键值
            default: 默认值，如果找不到对应文本则返回此值
            
        Returns:
            对应语言的文本，如果找不到则返回默认值或键值本身
        """
        if language_code in self._languages:
            return self._languages[language_code].get(key, default or key)
        return default or key
    
    def get_available_languages(self) -> list:
        """获取所有可用的语言代码"""
        return list(self._languages.keys())

# 创建全局语言管理器实例
_language_manager = LanguageManager()

# 向后兼容的旧字典结构（如果JSON文件加载失败时使用）
LANGUAGE_TEXTS = {
    "zh": {
        # 基本界面
        "title": "VRChat OSC 通信工具",
        "connection_settings": "连接设置",
        "host_address": "主机地址:",
        "send_port": "发送端口:",
        "receive_port": "接收端口:",
        "connect": "连接",
        "disconnect": "断开",
        "connecting": "连接中...",
        "connected": "已连接",
        "disconnected": "未连接",
        
        # 消息发送
        "message_send": "消息发送",
        "send_text": "发送文字",
        "text_message": "文字消息:",
        "send": "发送",
        
        # 语音相关
        "recognition_language": "识别语言:",
        "compute_device": "计算设备:",
        "record_voice": "录制语音",
        "start_listening": "开始监听",
        "stop_listening": "停止监听",
        "upload_voice": "上传语音",
        "send_voice": "发送语音",
        "stop_recording": "停止录制",
        "voice_threshold": "语音阈值:",
        "listening": "监听中...",
        "recording": "录制中...",
        
        # Avatar参数
        "avatar_params": "Avatar参数",
        "param_name": "参数名:",
        "param_value": "参数值:",
        "send_param": "发送参数",
        
        # 界面设置
        "ui_language": "界面语言:",
        "settings": "设置",
        "debug": "调试",
        "show_status": "显示状态",
        
        # 摄像头控制
        "camera_control": "摄像头控制",
        "camera": "摄像头:",
        "model": "模型:",
        "refresh": "刷新",
        "start_camera": "启动摄像头",
        "stop_camera": "停止摄像头",
        "start_face_detection": "启动面部识别",
        "stop_face_detection": "停止面部识别",
        "screenshot": "截图",
        "camera_feed": "摄像头画面",
        "camera_window": "摄像头窗口",
        
        # 表情识别
        "realtime_expression": "实时表情数据",
        "left_eye_blink": "左眼眨眼",
        "right_eye_blink": "右眼眨眼",
        "mouth_open": "嘴巴张开",
        "smile": "微笑",
        "eyeblink": "眨眼",
        
        # 状态信息
        "click_to_start": "点击启动摄像头按钮开始",
        "detecting_cameras": "正在检测摄像头...",
        "no_cameras_found": "未检测到摄像头",
        "detection_failed": "检测失败",
        "camera_started": "摄像头已启动",
        "camera_stopped": "摄像头已停止",
        "face_detection_started": "面部识别已启动",
        "face_detection_stopped": "面部识别已停止",
        
        # 日志相关
        "log": "日志",
        "clear_log": "清空日志",
        "speech_output": "语音识别输出 (基于VRChat语音状态)",
        "clear_speech": "清空语音记录",
        "save_speech": "保存语音记录",
        
        # 错误和警告
        "error": "错误",
        "warning": "警告",
        "success": "成功",
        "failed": "失败",
        "loading": "加载中...",
        "processing": "处理中...",
    },
    
    "ja": {
        # 基本界面
        "title": "VRChat OSC 通信ツール",
        "connection_settings": "接続設定",
        "host_address": "ホストアドレス:",
        "send_port": "送信ポート:",
        "receive_port": "受信ポート:",
        "connect": "接続",
        "disconnect": "切断",
        "connecting": "接続中...",
        "connected": "接続済み",
        "disconnected": "未接続",
        
        # 消息发送
        "message_send": "メッセージ送信",
        "send_text": "テキスト送信",
        "text_message": "テキストメッセージ:",
        "send": "送信",
        
        # 语音相关
        "recognition_language": "認識言語:",
        "compute_device": "計算デバイス:",
        "record_voice": "音声録音",
        "start_listening": "監視開始",
        "stop_listening": "監視停止",
        "upload_voice": "音声アップロード",
        "send_voice": "音声送信",
        "stop_recording": "録音停止",
        "voice_threshold": "音声閾値:",
        "listening": "監視中...",
        "recording": "録音中...",
        
        # Avatar参数
        "avatar_params": "Avatarパラメータ",
        "param_name": "パラメータ名:",
        "param_value": "パラメータ値:",
        "send_param": "パラメータ送信",
        
        # 界面设置
        "ui_language": "UI言語:",
        "settings": "設定",
        "debug": "デバッグ",
        "show_status": "ステータス表示",
        
        # 摄像头控制
        "camera_control": "カメラ制御",
        "camera": "カメラ:",
        "model": "モデル:",
        "refresh": "更新",
        "start_camera": "カメラ開始",
        "stop_camera": "カメラ停止",
        "start_face_detection": "顔認識開始",
        "stop_face_detection": "顔認識停止",
        "screenshot": "スクリーンショット",
        "camera_feed": "カメラ映像",
        "camera_window": "カメラウィンドウ",
        
        # 表情识别
        "realtime_expression": "リアルタイム表情データ",
        "left_eye_blink": "左目まばたき",
        "right_eye_blink": "右目まばたき",
        "mouth_open": "口を開く",
        "smile": "笑顔",
        "eyeblink": "まばたき",
        
        # 状态信息
        "click_to_start": "カメラ開始ボタンをクリック",
        "detecting_cameras": "カメラを検出中...",
        "no_cameras_found": "カメラが見つかりません",
        "detection_failed": "検出失敗",
        "camera_started": "カメラが開始されました",
        "camera_stopped": "カメラが停止されました",
        "face_detection_started": "顔認識が開始されました",
        "face_detection_stopped": "顔認識が停止されました",
        
        # 日志相关
        "log": "ログ",
        "clear_log": "ログクリア",
        "speech_output": "音声認識出力 (VRChat音声状態ベース)",
        "clear_speech": "音声記録クリア",
        "save_speech": "音声記録保存",
        
        # 错误和警告
        "error": "エラー",
        "warning": "警告",
        "success": "成功",
        "failed": "失敗",
        "loading": "読み込み中...",
        "processing": "処理中...",
    },
    
    "en": {
        # 基本界面
        "title": "VRChat OSC Communication Tool",
        "connection_settings": "Connection Settings",
        "host_address": "Host Address:",
        "send_port": "Send Port:",
        "receive_port": "Receive Port:",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "connecting": "Connecting...",
        "connected": "Connected",
        "disconnected": "Disconnected",
        
        # 消息发送
        "message_send": "Message Sending",
        "send_text": "Send Text",
        "text_message": "Text Message:",
        "send": "Send",
        
        # 语音相关
        "recognition_language": "Recognition Language:",
        "compute_device": "Compute Device:",
        "record_voice": "Record Voice",
        "start_listening": "Start Listening",
        "stop_listening": "Stop Listening",
        "upload_voice": "Upload Voice",
        "send_voice": "Send Voice",
        "stop_recording": "Stop Recording",
        "voice_threshold": "Voice Threshold:",
        "listening": "Listening...",
        "recording": "Recording...",
        
        # Avatar参数
        "avatar_params": "Avatar Parameters",
        "param_name": "Parameter Name:",
        "param_value": "Parameter Value:",
        "send_param": "Send Parameter",
        
        # 界面设置
        "ui_language": "UI Language:",
        "settings": "Settings",
        "debug": "Debug",
        "show_status": "Show Status",
        
        # 摄像头控制
        "camera_control": "Camera Control",
        "camera": "Camera:",
        "model": "Model:",
        "refresh": "Refresh",
        "start_camera": "Start Camera",
        "stop_camera": "Stop Camera",
        "start_face_detection": "Start Face Detection",
        "stop_face_detection": "Stop Face Detection",
        "screenshot": "Screenshot",
        "camera_feed": "Camera Feed",
        "camera_window": "Camera Window",
        
        # 表情识别
        "realtime_expression": "Real-time Expression Data",
        "left_eye_blink": "Left Eye Blink",
        "right_eye_blink": "Right Eye Blink",
        "mouth_open": "Mouth Open",
        "smile": "Smile",
        "eyeblink": "Eye Blink",
        
        # 状态信息
        "click_to_start": "Click Start Camera button to begin",
        "detecting_cameras": "Detecting cameras...",
        "no_cameras_found": "No cameras detected",
        "detection_failed": "Detection failed",
        "camera_started": "Camera started",
        "camera_stopped": "Camera stopped",
        "face_detection_started": "Face detection started",
        "face_detection_stopped": "Face detection stopped",
        
        # 日志相关
        "log": "Log",
        "clear_log": "Clear Log",
        "speech_output": "Speech Recognition Output (Based on VRChat Voice State)",
        "clear_speech": "Clear Speech Records",
        "save_speech": "Save Speech Records",
        
        # 错误和警告
        "error": "Error",
        "warning": "Warning",
        "success": "Success",
        "failed": "Failed",
        "loading": "Loading...",
        "processing": "Processing...",
    }
}

# 语言显示名称映射
LANGUAGE_DISPLAY_MAP = {
    "zh": "中文",
    "ja": "日本語", 
    "en": "English"
}

# 反向映射（从显示名称到语言代码）
DISPLAY_TO_LANGUAGE_MAP = {
    "中文": "zh",
    "日本語": "ja",
    "English": "en"
}

# 便捷函数，使用全局语言管理器
def get_text(language_code: str, key: str, default: str = None) -> str:
    """
    根据语言代码和键值获取对应的文本
    
    Args:
        language_code: 语言代码 ('zh', 'ja', 'en')
        key: 文本键值
        default: 默认值，如果找不到对应文本则返回此值
        
    Returns:
        对应语言的文本，如果找不到则返回默认值或键值本身
    """
    # 首先尝试从JSON文件加载的数据获取
    result = _language_manager.get_text(language_code, key, None)
    if result != key:  # 如果找到了对应的翻译
        return result
    
    # 如果JSON数据中没有找到，回退到旧的字典数据
    if language_code in LANGUAGE_TEXTS:
        return LANGUAGE_TEXTS[language_code].get(key, default or key)
    return default or key

def get_available_languages() -> list:
    """获取所有可用的语言代码"""
    # 优先返回JSON数据中的语言
    json_languages = _language_manager.get_available_languages()
    if json_languages:
        return json_languages
    return list(LANGUAGE_TEXTS.keys())

def get_language_display_names() -> list:
    """获取所有语言的显示名称"""
    return list(DISPLAY_TO_LANGUAGE_MAP.keys())