@echo off
chcp 65001 > nul
title VRChat OSC 通信工具

echo ==========================================
echo        VRChat OSC 通信工具
echo ==========================================
echo.

REM 检查Python是否安装
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.7或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [信息] 检测到Python环境
echo.

REM 检查依赖是否安装
echo [信息] 检查依赖库...
python -c "import pythonic" > nul 2>&1
if errorlevel 1 (
    echo [警告] 检测到缺少依赖库，正在安装...
    echo [信息] 安装依赖库，这可能需要几分钟...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖库安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo [信息] 依赖库安装完成
)

echo [信息] 启动VRChat OSC通信工具...
echo.
echo 使用说明：
echo 1. 确保VRChat正在运行并启用了OSC功能
echo 2. 在设置中确认OSC端口为 9000(发送) 和 9001(接收)
echo 3. 在GUI中点击"连接"按钮连接到VRChat
echo.

REM 启动GUI程序
python main.py

echo.
echo [信息] 程序已退出
pause