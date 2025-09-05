# VRChat OSC 智能通信工具

一个功能强大的VRChat OSC通信程序，集成语音识别、面部表情识别和智能语音交互。支持多语言识别，具备智能断句、AI情感检测和完善的调试功能。

## ✨ 核心特性

### 🎤 智能语音识别
- **实时语音监听**: 基于VRChat语音状态的智能语音检测
- **智能断句**: 自动检测语音停顿，避免录制过长或过短
- **多语言支持**: 中文（zh-CN）和日语（ja-JP）语音识别
- **GPU加速**: 支持CUDA加速的Whisper模型推理
- **多模式录制**: VRChat状态检测 + 纯音频检测双重保障

### 😊 AI面部表情识别
- **多模型支持**: ResEmoteNet、FER2013、EmoNeXt三种深度学习模型
- **实时情感检测**: 7种基本情感识别（愤怒、厌恶、恐惧、快乐、悲伤、惊讶、中性）
- **表情参数映射**: 智能转换为VRChat Avatar表情参数
- **GPU加速推理**: 支持CUDA加速的神经网络推理
- **热切换模型**: 运行时动态切换AI模型，无需重启
- **摄像头集成**: 内置摄像头界面，实时显示识别结果

### 🌍 多语言界面
- **三语支持**: 中文/日本語/English完整界面翻译
- **JSON语言包**: 模块化语言管理，易于扩展
- **实时切换**: 运行时切换界面语言，立即生效
- **完整本土化**: 所有界面文本、按钮、状态信息全面翻译

### 🎛️ 高级控制功能
- **OSC调试模式**: 实时监控VRChat发送的OSC参数
- **录制模式选择**: 正常模式、强制备用模式、禁用备用模式
- **实时参数调节**: 语音阈值、断句间隔可实时调整
- **连接诊断**: 自动诊断OSC连接问题并提供解决方案
- **详细状态显示**: 完整的系统状态和调试信息

### 💬 通信功能
- **聊天消息发送**: 文字和语音消息发送到VRChat
- **Avatar参数控制**: 双向OSC参数通信
- **实时状态监控**: 监听VRChat语音状态变化
- **表情数据传输**: 实时发送面部表情参数到VRChat

## 🛠️ 系统要求

### 基本要求
- **Python**: 3.10+ 
- **操作系统**: Windows/macOS/Linux
- **硬件**: 麦克风、摄像头、推荐4GB+内存
- **软件**: VRChat游戏客户端

### GPU支持（推荐）
- **NVIDIA GPU**: 支持CUDA的显卡（RTX系列推荐）
- **显存**: 建议4GB+用于AI模型加载
- **CUDA**: 11.8+版本支持

## 📦 安装指南

### 1. 获取项目
```bash
git clone <repository-url>
cd VRchatOSC
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 平台特殊设置

#### Windows
如果遇到PyAudio安装问题：
```bash
pip install pipwin
pipwin install pyaudio
```

#### macOS
```bash
brew install portaudio
pip install pyaudio
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

## ⚙️ VRChat OSC 配置

### VRChat 设置
1. 启动VRChat
2. 进入 **Settings** → **OSC**
3. 启用 **"Enabled"**
4. 确认端口设置：
   - **Incoming**: 9000
   - **Outgoing**: 9001
5. **重启VRChat**（重要！）

### 账户要求
- VRChat账户等级需要为 **"New User"** 及以上
- 确保有聊天权限（未被静音）

## 🚀 使用方法

### 启动程序
```bash
python main.py
```

### 连接设置
- **主机地址**: 127.0.0.1（本地）
- **发送端口**: 9000（发送到VRChat）
- **接收端口**: 9001（从VRChat接收）
- **界面语言**: 中文/日本語/English切换

### 语音功能
- **文字消息**: 直接输入发送或按回车
- **语音文件**: 上传音频文件自动识别发送
- **实时监听**: 点击"开始监听"进行持续语音识别
- **识别语言**: 支持中文和日语语音识别

### 面部表情识别
- **摄像头选择**: 从下拉列表选择可用摄像头
- **模型选择**: 
  - **Simple**: 基础OpenCV面部检测
  - **ResEmoteNet**: ResNet架构情感识别
  - **FER2013**: 经典CNN情感识别
  - **EmoNeXt**: ConvNeXt现代架构（最高精度）
- **实时显示**: 摄像头画面显示在主界面右侧
- **表情数据**: 实时表情参数显示和传输

### 高级设置
- **OSC调试模式**: 查看实际接收的VRChat参数
- **强制备用模式**: 强制使用纯音频检测（不依赖VRChat）
- **语音阈值**: 调节语音检测灵敏度（0.005-0.05）
- **断句间隔**: 调节自动断句检测时间（0.2-1.0秒）

## 🤖 AI模型详解

### ResEmoteNet
- **架构**: 基于ResNet的情感识别模型
- **特点**: 残差连接，训练稳定
- **性能**: 中等参数量，快速推理
- **边框**: 绿色显示

### FER2013
- **架构**: 经典CNN架构
- **特点**: 基于FER2013数据集训练
- **性能**: 参数量小，推理最快
- **边框**: 红色显示

### EmoNeXt
- **架构**: 现代ConvNeXt架构
- **特点**: LayerNorm + GELU + DropPath
- **性能**: 参数量大，精度最高
- **边框**: 蓝色显示

### 表情参数映射
所有AI模型都将7种情感映射为4个VRChat表情参数：
- **eyeblink_left**: 左眼眨眼
- **eyeblink_right**: 右眼眨眼
- **mouth_open**: 嘴巴张开
- **smile**: 微笑

## 🔧 录制模式详解

### 1. 正常模式（默认）
- 等待VRChat发送语音状态参数
- 只在检测到VRChat语音活动时录制
- 最精准，避免误录制环境音

### 2. 备用模式（自动切换）
- 30秒内未收到VRChat参数时自动启用
- 使用纯音频能量检测
- 确保在VRChat OSC异常时仍可工作

### 3. 强制备用模式
- 手动启用纯音频检测
- 不依赖VRChat状态
- 适用于VRChat OSC功能异常时

## 🛠️ 故障排除

### 常见问题诊断

#### 1. 无法检测到VRChat语音
**解决方案**:
1. 启用"OSC调试模式"查看接收参数
2. 确认VRChat OSC设置已启用
3. 重启VRChat应用程序
4. 尝试切换到"强制备用模式"

#### 2. 摄像头无法启动
**解决方案**:
1. 检查摄像头权限设置
2. 关闭其他使用摄像头的应用
3. 尝试切换不同的摄像头
4. 重新启动应用程序

#### 3. AI模型切换失败
**解决方案**:
1. 确保有足够的系统内存
2. 检查CUDA驱动安装（GPU模式）
3. 查看日志中的具体错误信息
4. 回退到Simple模式测试

#### 4. 语言切换不生效
**解决方案**:
1. 检查语言JSON文件是否存在
2. 重启应用程序应用语言设置
3. 确认选择了正确的语言选项

## 📁 项目结构

```
VRchatOSC/
├── ui/
│   ├── vrchat_osc_gui.py          # 主界面
│   └── languages/                 # 多语言支持
│       ├── zh.json                # 中文语言包
│       ├── ja.json                # 日语语言包
│       ├── en.json                # 英语语言包
│       └── language_dict.py       # 语言管理器
├── src/
│   ├── vrchat_controller.py       # VRChat控制器
│   ├── osc_client.py              # OSC客户端
│   ├── voice/
│   │   └── engine.py              # 语音识别引擎
│   └── face/                      # 面部识别模块
│       ├── gpu_emotion_detector.py # 统一GPU检测器
│       ├── simple_face_detector.py # 简单面部检测
│       └── models/                # AI模型模块
│           ├── resemotenet.py     # ResEmoteNet模型
│           ├── fer2013.py         # FER2013模型
│           ├── emonext.py         # EmoNeXt模型
│           └── README.md          # 模型说明文档
├── models/                        # 模型权重文件
│   ├── resemotenet/
│   ├── fer2013/
│   └── emonext/
├── requirements.txt               # 依赖列表
├── main.py                       # 程序入口
└── README.md                     # 项目说明
```

## 🔧 技术架构

### 语音处理流程
1. **音频采集**: 实时麦克风音频流
2. **语音检测**: 多指标语音活动检测
3. **动态录制**: 智能开始/结束判断
4. **断句分析**: AI断句边界检测
5. **语音识别**: Whisper模型转文字
6. **消息发送**: OSC协议发送至VRChat

### 面部识别流程
1. **摄像头采集**: 实时视频流获取
2. **面部检测**: OpenCV Haar级联检测
3. **图像预处理**: 48x48灰度图像标准化
4. **AI推理**: 深度学习模型情感识别
5. **参数映射**: 情感转VRChat表情参数
6. **实时传输**: OSC协议发送表情数据

### OSC通信协议

#### 发送消息
```python
/chatbox/input [message, send_immediately, show_in_chatbox]
/avatar/parameters/{param_name} [value]
/avatar/parameters/eyeblink_left [float]    # 左眼眨眼
/avatar/parameters/eyeblink_right [float]   # 右眼眨眼
/avatar/parameters/mouth_open [float]       # 嘴巴张开
/avatar/parameters/smile [float]            # 微笑
```

#### 接收消息
```python
/avatar/parameters/Voice [float]          # 语音强度
/avatar/parameters/VoiceLevel [float]     # 语音级别  
/avatar/parameters/Viseme [int]           # 口型参数
```

### 性能优化
- **GPU加速**: CUDA支持的AI模型推理
- **多线程**: 异步音频、视频处理
- **内存管理**: 动态缓冲区和资源释放
- **模型缓存**: 热切换减少加载时间
- **JSON本地化**: 高效语言包加载

## 🆕 更新日志

### v2.0 - AI情感识别版本
- ✅ 新增三种AI情感识别模型
- ✅ 摄像头界面集成到主窗口
- ✅ 实时表情参数检测和传输
- ✅ 热切换AI模型功能
- ✅ GPU加速推理支持

### v1.5 - 多语言版本
- ✅ 完整的三语言界面支持
- ✅ JSON语言包管理系统
- ✅ 实时语言切换功能
- ✅ 模块化语言架构

### v1.0 - 基础版本
- ✅ 语音识别和OSC通信
- ✅ 智能断句和多模式录制
- ✅ 调试模式和状态诊断

## 📄 许可证

MIT License - 可自由使用、修改和分发

---

**享受在VRChat中的智能语音和表情交流体验！** 🎉🤖😊