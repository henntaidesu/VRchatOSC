```mermaid
graph TB
    A1[VRChat OSC Communication Tool]
    A2[VOICEVOX]
    A3[LLM_GeminiAI]
    A4[camera]
    A5[USER_VRC_OSC]
    A6[AI_VRC_OSC]
    A7[remote_audio]


    A1 -- |LINK| --> A2
    A1 -- |LINK| --> A3

    A11[EmoNeXt] -- 获取用户情感 --> B4
    B1[USER_VRC_OSC] -- 获取语音提交 --> B2[Whisper 语音转文字] -- 提交文本 --> B3[Gemini API]
    -- 获取返回文本 --> B3.1[根据标点符号切分文本] --> B3.2[提交音频生成队列]--> B4[VOICEVOX语音合成] 
    -- 发送远端音频9003 --> B5[remote_audio.py]  -- 播放音频至VB虚拟麦克风 --> B6[AI_VRC_OSC] 
    