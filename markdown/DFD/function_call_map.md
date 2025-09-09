# VRChat OSC 系统 - 完整函数调用清单

## 全部函数调用关系映射

### 1. 主程序启动函数调用链

```
main.py
└── main()
    └── VRChatOSCGUI.__init__()
        ├── ConfigManager.__init__()
        ├── setup_ui()
        │   ├── VoicevoxArea.setup_voicevox_area()
        │   ├── LLMProcess.setup_llm_area()
        │   └── UserVRC.setup_user_vrc_area()
        ├── VRChatController.__init__()
        │   ├── OSCClient.__init__()
        │   ├── SpeechEngine.__init__()
        │   └── _initialize_vrc_voice_integration()
        │       └── VRCVoiceIntegration.__init__()
        │           └── VRCDynamicVoiceProcessor.__init__()
        └── init_voicevox()
            └── VOICEVOXClient.__init__()
```

### 2. VRC参数监听和处理函数调用

```
OSCClient.server_thread()
├── handle_osc_message()
│   └── _on_parameter_change()  # 回调到VRChatController
└── VRChatController._on_parameter_change()
    ├── status_change_callback()  # 通知UI
    └── vrc_voice_integration.on_vrc_speaking_state_changed()
        └── VRCDynamicVoiceProcessor.on_vrc_speaking_state_changed()
            ├── _handle_mic_opened()
            │   ├── _start_recording()
            │   │   └── speech_engine.start_recording()
            │   └── _schedule_timeout_check()
            └── _handle_mic_closed()
                ├── _stop_recording_and_process()
                │   ├── speech_engine.stop_recording()
                │   └── _process_audio_async()
                │       ├── speech_engine.recognize_audio()
                │       └── llm_handler.submit_voice_text()
                └── _cancel_recording()
```

### 3. 语音识别和LLM处理函数调用

```
VRCDynamicVoiceProcessor._process_audio_async()
└── VoiceLLMHandler.submit_voice_text()
    ├── _prepare_conversation_context()
    ├── _make_llm_request()
    │   └── requests.post()  # API调用
    ├── _process_llm_response()
    └── response_callback()  # 回调到StreamingLLMProcessor
        └── StreamingLLMProcessor._on_llm_streaming_response()
            ├── _detect_complete_sentences()
            │   ├── re.split()  # 句子分割
            │   └── re.findall()  # 标点符号检测
            ├── sentence_queue.put()
            └── main_app.add_speech_output()
```

### 4. 流式句子处理和语音合成函数调用

```
StreamingLLMProcessor._sentence_processing_loop()
└── sentence_queue.get()
    └── _process_sentence()
        ├── voicevox_area.synthesize_with_voicevox()
        │   ├── voicevox_client.set_voice_parameters()
        │   ├── voicevox_client.synthesize_speech()
        │   │   ├── synthesis_lock.acquire()
        │   │   ├── _do_synthesis()
        │   │   │   ├── requests.post("/audio_query")
        │   │   │   └── requests.post("/synthesis")
        │   │   └── synthesis_lock.release()
        │   ├── soundfile.read()  # bytes to numpy转换
        │   └── io.BytesIO()
        ├── tempfile.NamedTemporaryFile()
        ├── soundfile.write()
        ├── remote_audio_client.play_audio_file()
        │   ├── remote_audio_client.ping()
        │   └── requests.post()  # 9003端口发送
        └── os.unlink()  # 临时文件清理
```

### 5. VOICEVOX语音合成详细函数调用

```
VOICEVOXClient.synthesize_speech()
├── synthesis_lock.__enter__()
├── is_synthesizing = True
├── _do_synthesis()
│   ├── requests.post(f"{base_url}/audio_query")
│   │   └── 参数: text, speaker
│   ├── response.raise_for_status()
│   ├── response.json()
│   ├── 设置语音参数
│   │   ├── audio_query["speedScale"]
│   │   ├── audio_query["pitchScale"]  
│   │   ├── audio_query["intonationScale"]
│   │   └── audio_query["volumeScale"]
│   ├── requests.post(f"{base_url}/synthesis")
│   │   └── 参数: speaker, audio_query
│   └── response.content
├── is_synthesizing = False
└── synthesis_lock.__exit__()
```

### 6. 音频队列管理函数调用

```
VoiceQueueManager.add_voicevox_item()
├── VoiceQueueItem()  # 创建队列项
├── voice_queue.put()
└── status_callback()

VoiceQueueManager._processing_loop()
└── voice_queue.get()
    ├── _process_voicevox_item()
    │   ├── voicevox_client.set_speaker()
    │   ├── voicevox_client.save_audio()
    │   ├── _save_generated_voice_file()
    │   └── _send_voice_immediately()
    │       ├── _preprocess_audio_for_vrc()
    │       │   ├── soundfile.read()
    │       │   ├── scipy.signal.resample()
    │       │   └── soundfile.write()
    │       ├── _get_ai_host_address()
    │       ├── RemoteAudioClient()
    │       ├── client.ping()
    │       └── client.play_audio_file()
    └── voice_queue.task_done()
```

### 7. UI交互和回调函数调用

```
VoicevoxArea.connect_voicevox()
├── threading.Thread(target=connect_in_background)
└── connect_in_background()
    ├── VOICEVOXClient(host, port)
    ├── voicevox_client.test_connection()
    ├── voicevox_client.get_speakers_list()
    ├── root.after(0, lambda: update_voicevox_ui())
    └── update_voicevox_ui()
        ├── avatar_controller.set_voicevox_client()
        ├── SingleAIVRCManager.__init__()
        └── single_ai_manager.init_voice_queue_manager()

VoicevoxArea.test_voicevox()
├── threading.Thread(target=synthesize_test)
└── synthesize_test()
    ├── voicevox_client.set_speaker()
    ├── voicevox_client.set_voice_parameters()
    ├── voicevox_client.synthesize_speech()
    ├── voicevox_client.play_audio()
    └── root.after(0, lambda: callback)
```

### 8. 配置管理函数调用

```
ConfigManager.__init__()
├── configparser.ConfigParser()
├── load_config()
│   ├── config.read()
│   └── _validate_config()
└── save_config()
    ├── _backup_config()
    └── config.write()

ConfigManager.set_voicevox_last_selection()
├── set(section, key, value)
└── save_config()
```

### 9. 错误处理和清理函数调用

```
VRChatController.cleanup()
├── stop_voice_listening()
│   ├── vrc_voice_integration.stop_processing()
│   │   └── VRCDynamicVoiceProcessor.stop_processing()
│   └── voice_thread.join()
├── vrc_voice_integration.cleanup()
└── stop_osc_server()
    └── OSCClient.stop()

StreamingLLMProcessor.shutdown()
├── stop_processing()
│   ├── is_running = False
│   ├── llm_handler.stop_processing()
│   └── sentence_processing_thread.join()
└── remote_audio_client cleanup
```

### 10. 异步处理和线程函数调用

```
threading.Thread(target=_voice_listening_loop)
├── _voice_listening_loop()
│   ├── osc_client.get_vrc_speaking_state()
│   ├── record_audio_dynamic()
│   │   ├── pyaudio.PyAudio()
│   │   ├── stream.start_stream()
│   │   ├── detect_voice_activity()
│   │   └── stream.stop_stream()
│   └── voice_result_callback()

threading.Thread(target=_processing_loop)
├── VoiceQueueManager._processing_loop()
│   ├── voice_queue.get(timeout=1)
│   ├── _process_voicevox_item() 或 _process_file_item()
│   └── voice_queue.task_done()
└── time.sleep(0.5)

threading.Thread(target=_sentence_processing_loop)
├── StreamingLLMProcessor._sentence_processing_loop()
│   ├── sentence_queue.get(timeout=1)
│   ├── _process_sentence()
│   └── sentence_queue.task_done()
└── 异常处理
```

## 回调函数映射表

| 回调函数 | 注册位置 | 调用位置 | 参数 |
|---------|---------|----------|------|
| `_on_parameter_change` | OSCClient | OSC消息接收时 | param_name, value |
| `_on_llm_streaming_response` | VoiceLLMHandler | LLM响应时 | VoiceLLMResponse |
| `_on_vrc_voice_result` | VRCVoiceIntegration | 语音识别完成时 | text, is_realtime, trigger_reason, audio_duration |
| `voice_result_callback` | VRChatController | 语音识别结果时 | 同上 |
| `status_change_callback` | VRChatController | 状态变化时 | status_type, status_data |
| `sentence_callback` | StreamingLLMProcessor | 句子处理完成时 | sentence_text |

## 定时器和延时函数

| 函数 | 触发条件 | 延时时间 | 作用 |
|------|----------|----------|------|
| `_schedule_timeout_check` | 麦克风打开时 | self.max_recording_duration | 录音超时检查 |
| `root.after` | UI更新需要时 | 0ms | 主线程UI更新 |
| `voice_queue.get(timeout=1)` | 队列处理循环 | 1000ms | 队列超时等待 |
| `sentence_queue.get(timeout=1)` | 句子处理循环 | 1000ms | 句子队列超时等待 |

## 互斥锁和同步机制

| 锁对象 | 位置 | 保护资源 | 使用方式 |
|--------|------|----------|----------|
| `synthesis_lock` | VOICEVOXClient | 语音合成过程 | `with synthesis_lock:` |
| `recording_state` | VRCDynamicVoiceProcessor | 录音状态 | 原子操作 |
| `is_running` | 各处理器 | 处理循环状态 | 布尔标志 |
| `voice_queue` | VoiceQueueManager | 音频队列 | `queue.Queue()` |
| `sentence_queue` | StreamingLLMProcessor | 句子队列 | `queue.Queue()` |

这个完整的函数调用清单涵盖了系统中所有重要的函数调用关系，包括主要流程、异步处理、错误处理和资源管理等方面。