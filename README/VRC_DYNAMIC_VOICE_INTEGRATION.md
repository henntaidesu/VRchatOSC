# VRC动态语音录音集成指南

本指南介绍如何在现有的VRChat OSC项目中集成基于VRC麦克风状态的动态语音录音功能。

## 功能特性

- ✅ **VRC麦克风状态监听**: 实时监听VRChat的 `vrc_speaking_state` 参数
- ✅ **动态录音控制**: 麦克风开启时开始录音，关闭时立即停止并处理
- ✅ **语音识别集成**: 自动将录音提交给Whisper进行语音识别
- ✅ **LLM处理支持**: 可选集成LLM处理器进行智能回复
- ✅ **异步处理**: 不阻塞主线程，保证界面流畅
- ✅ **错误处理**: 完整的异常处理和状态管理

## 核心组件

### 1. VRCDynamicVoiceProcessor
主要的动态语音处理器，负责：
- 监听VRC麦克风状态变化
- 控制录音的开始和停止
- 管理音频流和缓冲区
- 调用语音识别和LLM处理

### 2. VRCVoiceIntegration
集成管理器，提供简化的接口：
- 统一管理各个组件
- 提供便捷的回调设置
- 处理组件间的协调

## 快速集成步骤

### 步骤1: 导入必要模块

```python
from src.llm.vrc_voice_integration import VRCVoiceIntegration
from src.llm.voice_llm_handler import VoiceLLMHandler
from src.voice.engine import SpeechEngine
```

### 步骤2: 初始化组件

```python
# 创建语音识别引擎
speech_engine = SpeechEngine(model_size="base", device="auto")

# 创建LLM处理器（可选）
llm_handler = VoiceLLMHandler()
llm_handler.start_processing()

# 创建VRC语音集成
vrc_integration = VRCVoiceIntegration()
vrc_integration.initialize(speech_engine, llm_handler)

# 设置回调
vrc_integration.set_voice_result_callback(on_voice_result)
vrc_integration.set_status_change_callback(on_status_change)
vrc_integration.set_log_callback(on_log)

# 启动处理
vrc_integration.start_processing()
```

### 步骤3: 连接OSC参数监听

```python
# 在OSC参数回调中添加
def on_osc_parameter(parameter_name: str, value):
    if parameter_name == "vrc_speaking_state":
        # 核心：通知VRC语音集成器状态变化
        vrc_integration.on_vrc_speaking_state_changed(
            speaking_state=bool(value),
            voice_level=0.5 if value else 0.0
        )
    
    # 也可以监听其他语音参数
    elif parameter_name in ["Voice", "VoiceLevel", "IsSpeaking"]:
        voice_level = float(value) if value else 0.0
        is_speaking = voice_level > 0.01
        vrc_integration.on_vrc_speaking_state_changed(
            speaking_state=is_speaking,
            voice_level=voice_level
        )
```

### 步骤4: 处理语音识别结果

```python
def on_voice_result(text: str, is_realtime=False, trigger_reason="", audio_duration=0):
    """处理语音识别结果"""
    print(f"识别结果: {text}")
    print(f"触发原因: {trigger_reason}")
    print(f"录音时长: {audio_duration:.2f}秒")
    
    # 在这里处理识别结果
    # 例如：发送到聊天框、保存到文件、触发其他操作等
```

### 步骤5: 处理状态变化（可选）

```python
def on_status_change(status_type: str, data):
    """处理状态变化"""
    if status_type == "vrc_voice_dynamic":
        event_type = data.get('event_type', '')
        if event_type == "mic_opened":
            print("VRC麦克风开启，开始录音...")
        elif event_type == "mic_closed":
            print("VRC麦克风关闭，停止录音并处理...")
```

## 在现有项目中的具体集成

### 集成到 VRChatController

如果你的项目使用 `VRChatController`，可以这样集成：

```python
class VRChatController:
    def __init__(self):
        # 现有的初始化代码...
        
        # 添加VRC语音集成
        self.vrc_voice_integration = None
        
    def initialize_voice_integration(self):
        """初始化VRC语音集成"""
        if hasattr(self, 'speech_engine') and self.speech_engine:
            self.vrc_voice_integration = VRCVoiceIntegration()
            self.vrc_voice_integration.initialize(
                speech_engine=self.speech_engine,
                llm_handler=getattr(self, 'llm_handler', None)
            )
            
            # 设置回调
            self.vrc_voice_integration.set_voice_result_callback(self.on_dynamic_voice_result)
            self.vrc_voice_integration.set_log_callback(self.log)
            
            # 启动处理
            self.vrc_voice_integration.start_processing()
    
    def on_osc_parameter(self, parameter_name: str, value):
        """现有的OSC参数处理"""
        # 现有的处理逻辑...
        
        # 添加VRC语音状态处理
        if self.vrc_voice_integration and parameter_name == "vrc_speaking_state":
            self.vrc_voice_integration.on_vrc_speaking_state_changed(
                speaking_state=bool(value),
                voice_level=0.5 if value else 0.0
            )
    
    def on_dynamic_voice_result(self, text: str, **kwargs):
        """处理动态语音识别结果"""
        self.log(f"[动态语音] {text}")
        # 可以调用现有的语音结果处理逻辑
        if hasattr(self, 'on_voice_result'):
            self.on_voice_result(text, trigger_reason="vrc_mic_closed", **kwargs)
```

### 集成到GUI应用

如果你的项目有GUI界面：

```python
class MainApplication:
    def __init__(self):
        # 现有的初始化代码...
        
        # 添加VRC语音集成
        self.vrc_voice_integration = None
    
    def setup_vrc_voice_integration(self):
        """设置VRC语音集成"""
        if hasattr(self, 'client') and self.client:
            # 获取现有的语音引擎和LLM处理器
            speech_engine = getattr(self.client, 'speech_engine', None)
            llm_handler = getattr(self, 'llm_processor', None)
            
            if speech_engine:
                self.vrc_voice_integration = VRCVoiceIntegration()
                self.vrc_voice_integration.initialize(speech_engine, llm_handler)
                
                # 设置回调
                self.vrc_voice_integration.set_voice_result_callback(self.on_dynamic_voice_result)
                self.vrc_voice_integration.set_log_callback(self.log)
                
                # 启动处理
                self.vrc_voice_integration.start_processing()
                
                # 连接到OSC客户端的参数回调
                if hasattr(self.client, 'osc_client'):
                    original_callback = self.client.osc_client.parameter_callback
                    
                    def enhanced_callback(param_name, value):
                        # 调用原有的回调
                        if original_callback:
                            original_callback(param_name, value)
                        
                        # 处理VRC语音状态
                        if param_name == "vrc_speaking_state":
                            self.vrc_voice_integration.on_vrc_speaking_state_changed(
                                speaking_state=bool(value),
                                voice_level=0.5 if value else 0.0
                            )
                    
                    self.client.osc_client.set_parameter_callback(enhanced_callback)
    
    def on_dynamic_voice_result(self, text: str, **kwargs):
        """处理动态语音识别结果"""
        self.log(f"[VRC动态语音] {text}")
        
        # 如果启用了LLM处理，可以直接发送
        if hasattr(self, 'llm_processor') and self.llm_processor:
            self.llm_processor.process_voice_text(text)
```

## 配置选项

### 录音参数配置

```python
# 设置录音参数
vrc_integration.set_recording_parameters(
    min_duration=0.5,    # 最小录音时长（秒）
    max_duration=30.0,   # 最大录音时长（秒）
    silence_timeout=2.0  # 静音超时时间（秒）
)
```

### 语音识别参数

```python
# 配置语音识别引擎
speech_engine = SpeechEngine(
    model_size="base",           # tiny, base, small, medium, large
    device="auto",               # auto, cuda, cpu
    config=your_config_manager   # 传入配置管理器
)

# 设置语音检测参数
speech_engine.set_voice_threshold(0.015)           # 语音激活阈值
speech_engine.set_sentence_pause_threshold(0.8)    # 句子停顿阈值
```

## 状态监控

```python
# 获取集成状态
status = vrc_integration.get_status()
print(f"集成就绪: {status['integration_ready']}")
print(f"录音状态: {status['recording_state']}")
print(f"VRC说话状态: {status['vrc_speaking_state']}")
print(f"当前录音时长: {status['recording_duration']:.2f}秒")

# 检查是否就绪
if vrc_integration.is_ready():
    print("VRC动态语音系统就绪")
```

## 错误处理

```python
def on_log(message: str):
    """处理日志和错误信息"""
    print(f"[VRC语音] {message}")
    
    # 检查错误信息并处理
    if "错误" in message or "失败" in message:
        # 进行错误恢复
        try:
            # 重启组件或采取其他恢复措施
            if not vrc_integration.is_ready():
                vrc_integration.stop_processing()
                vrc_integration.start_processing()
        except Exception as e:
            print(f"错误恢复失败: {e}")
```

## 资源清理

```python
def cleanup():
    """清理VRC语音集成资源"""
    if vrc_integration:
        vrc_integration.cleanup()
```

## 测试建议

1. **基础测试**: 确保能接收到 `vrc_speaking_state` 参数
2. **录音测试**: 验证麦克风开启/关闭时的录音行为
3. **识别测试**: 测试短语和长句的识别准确性
4. **性能测试**: 检查内存使用和CPU占用
5. **异常测试**: 测试各种异常情况的处理

## 故障排除

### 常见问题

1. **收不到VRC参数**: 检查VRChat OSC设置是否启用
2. **录音无声音**: 检查麦克风设备和权限
3. **识别失败**: 确认Whisper模型加载成功
4. **处理延迟**: 考虑调整录音参数和模型大小

### 调试技巧

```python
# 启用详细日志
vrc_integration.set_log_callback(lambda msg: print(f"[调试] {msg}"))

# 监控OSC参数
osc_client.set_debug_mode(True)

# 检查组件状态
status = vrc_integration.get_status()
print(json.dumps(status, indent=2, ensure_ascii=False))
```

## 示例代码

完整的使用示例请参考：
- `examples/vrc_dynamic_voice_example.py` - 独立运行示例
- `src/llm/vrc_voice_integration.py` - 集成接口文档

## 注意事项

1. **延迟考虑**: 语音识别需要一定时间，不适合实时对话场景
2. **资源消耗**: Whisper模型会消耗一定的CPU/GPU资源
3. **网络依赖**: LLM处理可能需要网络连接
4. **兼容性**: 确保VRChat版本支持所需的OSC参数

## 许可证

本功能遵循项目的现有许可证。