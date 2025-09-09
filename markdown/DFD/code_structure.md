# VRChat OSC 系统 - 详细代码结构图

## 系统架构和函数调用关系图

```mermaid
graph TB
    %% 主程序入口
    Main[📱 main.py<br/>主程序入口]
    GUI[🖥️ vrchat_osc_gui.py<br/>主界面应用]
    
    %% UI组件层
    subgraph "🎨 UI组件层"
        VoiceVoxArea[🎤 voicevox_area.py<br/>VOICEVOX控制区域]
        LLMProcess[💬 LLM_process.py<br/>LLM处理界面]
        UserVRC[👤 user_vrc.py<br/>用户VRC控制]
    end
    
    %% 核心控制层
    subgraph "🎯 核心控制层"
        VRCController[🎮 vrchat_controller.py<br/>VRChat主控制器]
        OSCClient[📡 osc_client.py<br/>OSC通信客户端]
        SpeechEngine[🎙️ SpeechEngine<br/>语音识别引擎]
    end
    
    %% VRC动态语音处理
    subgraph "🧠 VRC动态语音处理"
        VRCVoiceIntegration[🔄 vrc_voice_integration.py<br/>VRC语音集成]
        VRCDynamicProcessor[⚡ vrc_dynamic_voice_processor.py<br/>VRC动态语音处理器]
    end
    
    %% LLM处理层
    subgraph "💭 LLM处理层"
        VoiceLLMHandler[🤖 voice_llm_handler.py<br/>语音LLM处理器]
        StreamingLLMProcessor[📝 streaming_llm_processor.py<br/>流式LLM处理器]
        EmotionAwareProcessor[😊 emotion_aware_streaming_processor.py<br/>情感感知处理器]
    end
    
    %% 语音合成层
    subgraph "🎵 语音合成层"
        VOICEVOXClient[🎤 voicevox_tts.py<br/>VOICEVOX客户端]
        VoiceQueueManager[📋 voice_queue_manager.py<br/>语音队列管理器]
        RemoteAudioClient[📡 remote_audio.py<br/>远程音频客户端]
    end
    
    %% 配置管理
    ConfigManager[⚙️ config_manager.py<br/>配置管理器]
    
    %% 主要函数调用关系
    Main --> GUI
    GUI --> VoiceVoxArea
    GUI --> LLMProcess
    GUI --> UserVRC
    GUI --> VRCController
    GUI --> ConfigManager
    
    %% VRChat控制器的核心调用
    VRCController --> OSCClient
    VRCController --> SpeechEngine
    VRCController --> VRCVoiceIntegration
    
    %% OSC客户端回调
    OSCClient -.->|_on_parameter_change| VRCController
    OSCClient -.->|vrc_speaking_state| VRCVoiceIntegration
    
    %% VRC动态语音处理流程
    VRCVoiceIntegration --> VRCDynamicProcessor
    VRCDynamicProcessor --> SpeechEngine
    VRCDynamicProcessor --> VoiceLLMHandler
    
    %% LLM处理流程
    VoiceLLMHandler --> StreamingLLMProcessor
    StreamingLLMProcessor --> EmotionAwareProcessor
    StreamingLLMProcessor --> VoiceVoxArea
    
    %% 语音合成流程
    VoiceVoxArea --> VOICEVOXClient
    StreamingLLMProcessor --> VOICEVOXClient
    VoiceQueueManager --> VOICEVOXClient
    VoiceQueueManager --> RemoteAudioClient
    
    %% 样式
    classDef main fill:#ff9800,stroke:#e65100,stroke-width:3px
    classDef ui fill:#2196f3,stroke:#0d47a1,stroke-width:2px
    classDef core fill:#4caf50,stroke:#1b5e20,stroke-width:2px
    classDef vrc fill:#9c27b0,stroke:#4a148c,stroke-width:2px
    classDef llm fill:#f44336,stroke:#b71c1c,stroke-width:2px
    classDef voice fill:#ff5722,stroke:#bf360c,stroke-width:2px
    classDef config fill:#607d8b,stroke:#263238,stroke-width:2px
    
    class Main,GUI main
    class VoiceVoxArea,LLMProcess,UserVRC ui
    class VRCController,OSCClient,SpeechEngine core
    class VRCVoiceIntegration,VRCDynamicProcessor vrc
    class VoiceLLMHandler,StreamingLLMProcessor,EmotionAwareProcessor llm
    class VOICEVOXClient,VoiceQueueManager,RemoteAudioClient voice
    class ConfigManager config
```

## 详细函数调用关系

### 1. 主程序启动流程

```mermaid
sequenceDiagram
    participant Main as main.py
    participant GUI as vrchat_osc_gui.py
    participant Config as config_manager.py
    participant VRC as vrchat_controller.py
    
    Main->>GUI: VRChatOSCGUI()
    GUI->>Config: ConfigManager()
    GUI->>VRC: VRChatController(config)
    VRC->>VRC: _initialize_vrc_voice_integration()
    VRC->>GUI: 初始化完成
    GUI->>Main: 界面就绪
```

### 2. VRC参数变化处理流程

```mermaid
sequenceDiagram
    participant VRChat as VRChat应用
    participant OSC as OSCClient
    participant VRCCtrl as VRChatController
    participant VRCVoice as VRCVoiceIntegration
    participant Processor as VRCDynamicProcessor
    
    VRChat->>OSC: vrc_speaking_state = False
    OSC->>VRCCtrl: _on_parameter_change(param, value)
    VRCCtrl->>VRCVoice: on_vrc_speaking_state_changed(False)
    VRCVoice->>Processor: _handle_mic_closed()
    Processor->>Processor: _stop_recording_and_process()
    Processor->>Processor: _process_audio_async()
```

### 3. 语音识别到LLM处理流程

```mermaid
sequenceDiagram
    participant Speech as SpeechEngine
    participant Processor as VRCDynamicProcessor  
    participant LLM as VoiceLLMHandler
    participant Streaming as StreamingLLMProcessor
    
    Speech->>Processor: 识别的文本
    Processor->>LLM: submit_voice_text(text)
    LLM->>Streaming: 流式LLM请求
    Streaming->>Streaming: _on_llm_streaming_response()
    Streaming->>Streaming: _detect_complete_sentences()
    Streaming->>Streaming: _process_sentence()
```

### 4. 流式语音合成播放流程

```mermaid
sequenceDiagram
    participant Streaming as StreamingLLMProcessor
    participant VoxArea as VoiceVoxArea
    participant VoxClient as VOICEVOXClient
    participant Remote as RemoteAudioClient
    
    Streaming->>VoxArea: synthesize_with_voicevox(text, "numpy")
    VoxArea->>VoxClient: synthesize_speech(text, wait_for_previous=True)
    VoxClient->>VoxClient: _do_synthesis(text)
    VoxClient->>VoxArea: audio_data (bytes)
    VoxArea->>VoxArea: 转换为numpy格式
    VoxArea->>Streaming: numpy_audio
    Streaming->>Remote: play_audio_file(temp_file, use_queue=True)
```

## 关键类和方法详细结构

### VRChatController 核心方法
```mermaid
classDiagram
    class VRChatController {
        +__init__(config)
        +_initialize_vrc_voice_integration()
        +_on_parameter_change(param_name, value)
        +_on_vrc_voice_result(text, is_realtime, trigger_reason, audio_duration)
        +start_voice_listening(language)
        +stop_voice_listening()
        +set_llm_handler(llm_handler)
        +cleanup()
    }
```

### VRCDynamicVoiceProcessor 核心方法
```mermaid
classDiagram
    class VRCDynamicVoiceProcessor {
        +__init__(config)
        +set_speech_engine(engine)
        +set_llm_handler(handler)
        +on_vrc_speaking_state_changed(speaking_state, voice_level)
        +_handle_mic_opened(event)
        +_handle_mic_closed(event)
        +_start_recording()
        +_stop_recording_and_process()
        +_process_audio_async()
        +_calculate_adaptive_duration()
    }
```

### StreamingLLMProcessor 核心方法
```mermaid
classDiagram
    class StreamingLLMProcessor {
        +__init__(main_app, config)
        +start_processing()
        +submit_voice_text(text)
        +_on_llm_streaming_response(response)
        +_detect_complete_sentences()
        +_sentence_processing_loop()
        +_process_sentence(sentence_data)
    }
```

### VOICEVOXClient 核心方法
```mermaid
classDiagram
    class VOICEVOXClient {
        +__init__(host, port)
        +synthesize_speech(text, wait_for_previous)
        +_do_synthesis(text)
        +synthesize_and_play(text, wait_for_previous)
        +save_audio(text, output_path, wait_for_previous)
        +is_busy()
        +is_playing()
    }
```

## 配置文件和依赖关系

### 配置管理结构
```mermaid
graph LR
    Config[config_manager.py] --> VRC[VRChat设置]
    Config --> VOICEVOX[VOICEVOX设置]
    Config --> LLM[LLM API设置]
    Config --> Audio[音频参数设置]
    Config --> UI[界面配置]
```

### 主要依赖库
```mermaid
graph TD
    System[系统核心] --> OSC[python-osc<br/>OSC通信]
    System --> Speech[speech_recognition<br/>语音识别]
    System --> Audio[soundfile<br/>音频处理]
    System --> HTTP[requests<br/>HTTP请求]
    System --> GUI[tkinter<br/>图形界面]
    System --> Threading[threading<br/>多线程]
    System --> Queue[queue<br/>队列管理]
```

## 数据流和状态管理

### 全局状态管理
- **VRC状态**: `vrc_speaking_state`, `vrc_voice_level`
- **录音状态**: `RecordingState.IDLE/RECORDING/PROCESSING`
- **合成状态**: `is_synthesizing`, `synthesis_lock`
- **播放队列**: `voice_queue`, `sentence_queue`

### 关键回调函数
- `_on_parameter_change()`: OSC参数变化
- `_on_llm_streaming_response()`: LLM流式响应
- `_on_vrc_voice_result()`: VRC语音识别结果
- `_on_vrc_status_change()`: VRC状态变化

这个结构图展示了整个系统的完整架构，包括所有主要类、方法和它们之间的调用关系。