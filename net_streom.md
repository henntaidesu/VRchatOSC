```mermaid
graph TB
    

    A1[麦克风]
    A11[USER_VRC]
    A2[Whisper 语音转文字]
    A3[Gemini API]
    A4[VOICEVOX]
    A5[remote_audio]
    A6[VB]
    A7[AI_VRC]
    A8[VRC_service]
    A9[USER_VRC 音频]
    A10[UESE_EIR]

    A1 -- |说话| --> A11 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7--> A8--> A9 --> A10
    
