#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头诊断工具
用于检测和测试可用的摄像头设备
"""

import cv2
import numpy as np
import sys
import time
import os

# 设置控制台编码
if sys.platform.startswith('win'):
    os.system('chcp 65001')  # 设置为UTF-8编码

def test_camera_backends():
    """测试不同的OpenCV后端"""
    backends = [
        (cv2.CAP_DSHOW, "DirectShow (Windows)"),
        (cv2.CAP_MSMF, "Media Foundation (Windows)"),
        (cv2.CAP_V4L2, "Video4Linux2"),
        (cv2.CAP_ANY, "Any available")
    ]
    
    print("=== 测试摄像头后端 ===")
    working_backends = []
    
    for backend_id, backend_name in backends:
        try:
            cap = cv2.VideoCapture(0, backend_id)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"[OK] {backend_name} - 工作正常")
                    working_backends.append((backend_id, backend_name))
                else:
                    print(f"[FAIL] {backend_name} - 可以打开但无法读取帧")
                cap.release()
            else:
                print(f"[FAIL] {backend_name} - 无法打开")
        except Exception as e:
            print(f"[ERROR] {backend_name} - 错误: {e}")
    
    return working_backends

def scan_cameras():
    """扫描可用的摄像头设备"""
    print("\n=== 扫描摄像头设备 ===")
    available_cameras = []
    
    for i in range(10):  # 检查前10个设备ID
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    print(f"[OK] 摄像头 {i}: {width}x{height} @ {fps}fps")
                    available_cameras.append({
                        'id': i,
                        'width': width,
                        'height': height,
                        'fps': fps
                    })
                else:
                    print(f"[FAIL] 摄像头 {i}: 可以打开但无法读取帧")
                cap.release()
            # else:
            #     print(f"[FAIL] 摄像头 {i}: 无法打开")
        except Exception as e:
            print(f"[ERROR] 摄像头 {i}: 错误 - {e}")
        
        time.sleep(0.1)  # 短暂延迟避免设备冲突
    
    return available_cameras

def test_camera_with_different_backends(camera_id):
    """使用不同后端测试指定摄像头"""
    print(f"\n=== 测试摄像头 {camera_id} 的不同后端 ===")
    
    backends = [
        (cv2.CAP_DSHOW, "DirectShow"),
        (cv2.CAP_MSMF, "Media Foundation"), 
        (cv2.CAP_ANY, "Default")
    ]
    
    for backend_id, backend_name in backends:
        try:
            print(f"\n尝试 {backend_name}...")
            cap = cv2.VideoCapture(camera_id, backend_id)
            
            if not cap.isOpened():
                print(f"  [FAIL] 无法打开摄像头")
                continue
            
            # 设置分辨率
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # 尝试读取几帧
            success_count = 0
            for i in range(5):
                ret, frame = cap.read()
                if ret and frame is not None:
                    success_count += 1
                time.sleep(0.1)
            
            if success_count > 0:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"  [OK] 成功读取 {success_count}/5 帧 - {width}x{height}")
                
                # 显示预览
                print(f"  显示预览 (按 'q' 退出)...")
                preview_camera(cap, f"Camera {camera_id} - {backend_name}")
            else:
                print(f"  [FAIL] 无法读取帧")
            
            cap.release()
            
        except Exception as e:
            print(f"  [ERROR] 错误: {e}")

def preview_camera(cap, window_name):
    """显示摄像头预览"""
    frame_count = 0
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"警告: 无法读取第 {frame_count} 帧")
            continue
        
        frame_count += 1
        
        # 显示帧率信息
        elapsed = time.time() - start_time
        if elapsed > 0:
            fps = frame_count / elapsed
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 显示帧计数
        cv2.putText(frame, f"Frame: {frame_count}", (10, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow(window_name, frame)
        
        # 按 'q' 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyWindow(window_name)

def check_system_info():
    """检查系统信息"""
    print("=== 系统信息 ===")
    print(f"OpenCV 版本: {cv2.__version__}")
    print(f"Python 版本: {sys.version}")
    
    # 检查OpenCV编译信息
    build_info = cv2.getBuildInformation()
    if "Video I/O" in build_info:
        video_io_start = build_info.find("Video I/O:")
        video_io_end = build_info.find("\n\n", video_io_start)
        if video_io_end == -1:
            video_io_end = len(build_info)
        video_io_info = build_info[video_io_start:video_io_end]
        print(f"\n{video_io_info}")

def main():
    """主函数"""
    print("摄像头诊断工具")
    print("=" * 50)
    
    # 1. 检查系统信息
    check_system_info()
    
    # 2. 测试后端
    working_backends = test_camera_backends()
    
    # 3. 扫描摄像头
    available_cameras = scan_cameras()
    
    if not available_cameras:
        print("\n[ERROR] 未发现可用的摄像头设备!")
        print("\n可能的解决方案:")
        print("1. 检查摄像头是否正确连接")
        print("2. 检查Windows隐私设置中的摄像头权限")
        print("3. 关闭其他可能占用摄像头的应用程序")
        print("4. 更新或重新安装摄像头驱动程序")
        return
    
    print(f"\n[OK] 发现 {len(available_cameras)} 个可用摄像头")
    
    # 4. 交互式测试
    if len(available_cameras) == 1:
        camera_id = available_cameras[0]['id']
        print(f"\n自动选择摄像头 {camera_id} 进行详细测试...")
        test_camera_with_different_backends(camera_id)
    else:
        print("\n请选择要测试的摄像头:")
        for i, cam in enumerate(available_cameras):
            print(f"{i+1}. 摄像头 {cam['id']} - {cam['width']}x{cam['height']}")
        
        try:
            choice = int(input("\n输入选择 (1-{}): ".format(len(available_cameras))))
            if 1 <= choice <= len(available_cameras):
                camera_id = available_cameras[choice-1]['id']
                test_camera_with_different_backends(camera_id)
            else:
                print("无效选择")
        except ValueError:
            print("无效输入")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    finally:
        cv2.destroyAllWindows()