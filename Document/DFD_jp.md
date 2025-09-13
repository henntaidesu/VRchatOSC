```mermaid
graph TB
    AO[ユーザー] --> A1
    A1[マイク]
    A11[USER_VRC]
    A2[Whisper 音声→テキスト変換]
    A3[Gemini API]
    A4[VOICEVOX 音声合成]
    A5[remote_audio.py]
    A6[VB仮想マイク]
    A7[AI_VRC]
    A8[VRC_service]
    A9[USER_VRC 音声]
    A10[ユーザー]
    A111[空間音声の計算]
    A12[ユーザー]

    A1 -- |発話| --> A11 -- |取得| --> A2 -- |送信| --> A3 -- |テキスト| --> A4 -- |今使っている方法| --> A5 --> A6 --> A7 --> A8 -- |返却| --> A9 --> A10
    A4 -- |検討の方法| --> A111 --> A12