# VRChat OSC 通信工具

一个用于与VRChat进行OSC通信的Python程序，支持文字和语音消息传输。

## 功能特性

- ✅ **文字消息发送**: 向VRChat聊天框发送文字消息
- ✅ **语音识别**: 录制语音并转换为文字发送到VRChat
- ✅ **持续语音监听**: 实时语音识别和发送
- ✅ **Avatar参数控制**: 发送和接收Avatar参数
- ✅ **图形界面**: 基于Tkinter的用户友好界面
- ✅ **命令行界面**: 支持命令行操作
- ✅ **多语言支持**: 支持中文、英文、日文语音识别

## 安装要求

### 系统要求
- Python 3.7 或更高版本
- Windows/macOS/Linux
- 麦克风（用于语音功能）
- VRChat游戏

### 依赖库安装

1. 首先克隆或下载这个项目到本地
2. 在项目目录中打开命令行/终端
3. 安装Python依赖：

```bash
pip install -r requirements.txt
```

### 特殊依赖说明

#### Windows用户
如果安装`pyaudio`时遇到问题，可以：
1. 下载对应版本的wheel文件：https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
2. 使用pip安装：`pip install pyaudio-0.2.11-cp39-cp39-win_amd64.whl`

#### macOS用户
```bash
brew install portaudio
pip install pyaudio
```

#### Linux用户
```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev python3-pyaudio

# CentOS/RHEL
sudo yum install portaudio-devel
```

## VRChat OSC 设置

### 启用OSC功能
1. 启动VRChat
2. 进入设置（Settings）
3. 找到"OSC"选项
4. 启用"Enabled"
5. 确认端口设置：
   - **Incoming Port**: 9000 (VRChat接收消息的端口)
   - **Outgoing Port**: 9001 (VRChat发送消息的端口)

### 聊天框权限
确保你的VRChat账户有聊天权限：
- 需要VRChat账户不是"Visitor"等级
- 确保没有被静音或限制聊天

## 使用方法

### 图形界面模式（推荐）

运行GUI版本：
```bash
python vrchat_osc_gui.py
```

#### GUI功能说明：
1. **连接设置**: 
   - 主机地址：通常为127.0.0.1
   - 发送端口：9000（发送到VRChat）
   - 接收端口：9001（从VRChat接收）

2. **消息发送**:
   - 在文本框中输入消息，点击"发送文字"或按回车键
   - 选择语言后点击"录制语音"进行5秒录音
   - 点击"开始监听"进行持续语音识别

3. **Avatar参数**:
   - 输入参数名和值，点击"发送参数"

### 命令行模式

#### 交互模式
```bash
python vrchat_osc_client.py --mode interactive
```
支持的命令：
- `text <消息>` - 发送文字消息
- `voice` - 录制并发送语音消息  
- `listen` - 开始/停止持续语音识别
- `param <名称> <值>` - 发送Avatar参数
- `quit` - 退出程序

#### 文字模式
```bash
# 发送单条消息
python vrchat_osc_client.py --mode text --message "Hello VRChat!"

# 交互式文字输入
python vrchat_osc_client.py --mode text
```

#### 语音模式
```bash
python vrchat_osc_client.py --mode voice --language zh-CN
```

#### 自定义设置
```bash
python vrchat_osc_client.py --host 127.0.0.1 --send-port 9000 --receive-port 9001 --language en-US
```

## 语言支持

支持的语音识别语言：
- `zh-CN`: 中文（简体）
- `ja-JP`: 日语


## 常见问题

### 1. 连接失败
- 确保VRChat正在运行并启用了OSC
- 检查端口设置是否正确
- 确认防火墙没有阻止程序

### 2. 语音识别不工作
- 检查麦克风权限
- 确保网络连接正常（需要访问Google语音识别服务）
- 尝试调整麦克风音量

### 3. 消息不显示在VRChat中
- 确保VRChat账户有聊天权限
- 检查OSC端口设置
- 重启VRChat和程序

### 4. Avatar参数不生效
- 确保参数名称与Avatar中定义的一致
- 检查参数值类型（bool/int/float）
- 确保Avatar支持OSC参数控制

## 文件说明

- `vrchat_osc_client.py` - 核心OSC客户端类和命令行界面
- `vrchat_osc_gui.py` - 图形用户界面
- `requirements.txt` - Python依赖库列表
- `README.md` - 本说明文档

## 技术细节

### OSC消息格式

#### 发送到VRChat的消息：
- `/chatbox/input` - 聊天框消息: `[message, send_immediately, show_in_chatbox]`
- `/chatbox/typing` - 打字状态: `[boolean]`
- `/avatar/parameters/{param_name}` - Avatar参数: `[value]`

#### 从VRChat接收的消息：
- `/chatbox/input` - 聊天框输入
- `/chatbox/typing` - 打字状态
- `/avatar/parameters/*` - Avatar参数变化

### 网络配置
- 默认发送端口: 9000 (UDP)
- 默认接收端口: 9001 (UDP)
- 协议: OSC (Open Sound Control)

## 贡献和支持

如果你遇到问题或想要贡献代码：
1. 检查现有的Issues
2. 创建详细的Bug报告
3. 提交Pull Request

## 许可证

MIT License - 可自由使用和修改

## 更新日志

### v1.0.0
- 初始版本发布
- 支持文字和语音消息发送
- 图形界面和命令行界面
- Avatar参数控制功能