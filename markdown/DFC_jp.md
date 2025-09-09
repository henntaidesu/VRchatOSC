```mermaid
graph TB
    A10[カメラ] --> A11[EmoNeXt] -- |ユーザーの感情を取得| --> B4[VOICEVOX 音声合成]

    B1[USER_VRC_OSC] -- |音声入力を取得| --> B2[Whisper 音声→テキスト変換]
    B2 -- |テキスト送信| --> B3[Gemini API]
    B3 -- |応答テキストを取得| --> B31[句読点でテキストを分割]
    B31 --> B32[音声生成キューに投入]
    B32 --> B4[VOICEVOX 音声合成]

    B4 -- |リモート音声をポート9003に送信| --> B5[remote_audio.py]
    B5 --> B52[再生キューに保存]
    B52 -- |音声再生中か判定| --> B51[VB仮想マイクに音声を再生]
    B51 --> B6[AI_VRC_OSC]
