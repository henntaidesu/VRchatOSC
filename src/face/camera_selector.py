#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头选择器
用于检测系统中可用的摄像头并提供选择界面
"""

import cv2
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import List, Dict, Optional, Callable
import logging


class CameraInfo:
    """摄像头信息类"""
    def __init__(self, camera_id: int, width: int, height: int, fps: float, backend: str):
        self.id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self.backend = backend
        self.working = True
    
    def __str__(self):
        return f"摄像头 {self.id}: {self.width}x{self.height} @ {self.fps:.1f}fps ({self.backend})"


class CameraDetector:
    """摄像头检测器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_cameras(self) -> List[CameraInfo]:
        """检测所有可用的摄像头"""
        cameras = []
        
        # 测试不同的后端
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (cv2.CAP_ANY, "Default")
        ]
        
        self.logger.info("开始检测摄像头设备...")
        
        # 检查前10个摄像头ID
        for camera_id in range(10):
            for backend_id, backend_name in backends:
                try:
                    cap = cv2.VideoCapture(camera_id, backend_id)
                    if cap.isOpened():
                        # 测试读取帧
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            
                            camera_info = CameraInfo(camera_id, width, height, fps, backend_name)
                            cameras.append(camera_info)
                            
                            self.logger.info(f"发现摄像头: {camera_info}")
                            cap.release()
                            break  # 找到可用后端就不再测试其他后端
                        else:
                            cap.release()
                    else:
                        if cap:
                            cap.release()
                except Exception as e:
                    if 'cap' in locals():
                        cap.release()
                    continue
            
            time.sleep(0.1)  # 避免设备冲突
        
        if not cameras:
            self.logger.warning("未检测到可用的摄像头设备")
        else:
            self.logger.info(f"总共检测到 {len(cameras)} 个可用摄像头")
        
        return cameras


class CameraSelectorGUI:
    """摄像头选择器GUI"""
    
    def __init__(self, cameras: List[CameraInfo], callback: Optional[Callable[[int], None]] = None):
        self.cameras = cameras
        self.callback = callback
        self.selected_camera_id = None
        
        self.root = tk.Tk()
        self.root.title("摄像头选择器")
        self.root.geometry("500x400")
        self.root.resizable(True, True)
        
        self.preview_window = None
        self.preview_cap = None
        self.preview_thread = None
        self.preview_running = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题
        title_label = ttk.Label(main_frame, text="检测到的摄像头设备", font=('Arial', 12, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # 摄像头列表
        self.setup_camera_list(main_frame)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=(tk.W, tk.E))
        
        # 预览按钮
        self.preview_btn = ttk.Button(button_frame, text="预览选中摄像头", command=self.preview_camera)
        self.preview_btn.grid(row=0, column=0, padx=(0, 5))
        
        # 确认按钮
        self.confirm_btn = ttk.Button(button_frame, text="确认选择", command=self.confirm_selection)
        self.confirm_btn.grid(row=0, column=1, padx=5)
        
        # 刷新按钮
        refresh_btn = ttk.Button(button_frame, text="刷新设备", command=self.refresh_cameras)
        refresh_btn.grid(row=0, column=2, padx=5)
        
        # 取消按钮
        cancel_btn = ttk.Button(button_frame, text="取消", command=self.cancel)
        cancel_btn.grid(row=0, column=3, padx=(5, 0))
        
        # 状态标签
        self.status_label = ttk.Label(main_frame, text="请选择一个摄像头设备")
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 默认选择第一个摄像头
        if self.cameras:
            self.tree.selection_set(self.tree.get_children()[0])
            self.on_camera_select(None)
    
    def setup_camera_list(self, parent):
        """设置摄像头列表"""
        # 创建Treeview
        columns = ('ID', 'Resolution', 'FPS', 'Backend')
        self.tree = ttk.Treeview(parent, columns=columns, show='headings', height=8)
        
        # 定义列
        self.tree.heading('ID', text='摄像头ID')
        self.tree.heading('Resolution', text='分辨率')
        self.tree.heading('FPS', text='帧率')
        self.tree.heading('Backend', text='后端')
        
        # 设置列宽
        self.tree.column('ID', width=80, anchor='center')
        self.tree.column('Resolution', width=120, anchor='center')
        self.tree.column('FPS', width=80, anchor='center')
        self.tree.column('Backend', width=150, anchor='center')
        
        # 填充数据
        for camera in self.cameras:
            self.tree.insert('', 'end', values=(
                camera.id,
                f"{camera.width}x{camera.height}",
                f"{camera.fps:.1f}",
                camera.backend
            ))
        
        # 绑定选择事件
        self.tree.bind('<<TreeviewSelect>>', self.on_camera_select)
        
        # 创建滚动条
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 放置组件
        self.tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
    
    def on_camera_select(self, event):
        """摄像头选择事件处理"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            camera_id = int(item['values'][0])
            self.selected_camera_id = camera_id
            
            # 找到对应的摄像头信息
            selected_camera = next((cam for cam in self.cameras if cam.id == camera_id), None)
            if selected_camera:
                self.status_label.config(text=f"已选择: {selected_camera}")
            
            # 启用预览按钮
            self.preview_btn.config(state='normal')
            self.confirm_btn.config(state='normal')
    
    def preview_camera(self):
        """预览摄像头"""
        if self.selected_camera_id is None:
            messagebox.showwarning("警告", "请先选择一个摄像头")
            return
        
        # 停止之前的预览
        self.stop_preview()
        
        # 获取选中的摄像头信息
        selected_camera = next((cam for cam in self.cameras if cam.id == self.selected_camera_id), None)
        if not selected_camera:
            messagebox.showerror("错误", "无法找到选中的摄像头信息")
            return
        
        # 启动新的预览
        self.start_preview(selected_camera)
    
    def start_preview(self, camera_info: CameraInfo):
        """启动摄像头预览"""
        try:
            # 确定使用的后端
            backend_map = {
                "DirectShow": cv2.CAP_DSHOW,
                "Media Foundation": cv2.CAP_MSMF,
                "Default": cv2.CAP_ANY
            }
            backend = backend_map.get(camera_info.backend, cv2.CAP_ANY)
            
            # 打开摄像头
            self.preview_cap = cv2.VideoCapture(camera_info.id, backend)
            if not self.preview_cap.isOpened():
                messagebox.showerror("错误", f"无法打开摄像头 {camera_info.id}")
                return
            
            # 设置分辨率
            self.preview_cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_info.width)
            self.preview_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_info.height)
            
            # 启动预览线程
            self.preview_running = True
            self.preview_thread = threading.Thread(target=self.preview_loop, 
                                                 args=(camera_info,), daemon=True)
            self.preview_thread.start()
            
            self.preview_btn.config(text="停止预览")
            self.preview_btn.config(command=self.stop_preview)
            
        except Exception as e:
            messagebox.showerror("错误", f"启动预览失败: {e}")
    
    def preview_loop(self, camera_info: CameraInfo):
        """预览循环"""
        window_name = f"摄像头预览 - {camera_info}"
        
        while self.preview_running and self.preview_cap and self.preview_cap.isOpened():
            try:
                ret, frame = self.preview_cap.read()
                if ret and frame is not None:
                    # 添加信息文字
                    cv2.putText(frame, f"Camera {camera_info.id}", (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(frame, "Press ESC to close", (10, 70), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    cv2.imshow(window_name, frame)
                    
                    # 检查按键
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:  # ESC键
                        break
                else:
                    time.sleep(0.01)
            except Exception:
                break
        
        # 清理
        if self.preview_cap:
            self.preview_cap.release()
        cv2.destroyWindow(window_name)
        
        # 更新按钮状态
        if self.preview_btn:
            self.root.after(0, self.reset_preview_button)
    
    def reset_preview_button(self):
        """重置预览按钮状态"""
        self.preview_btn.config(text="预览选中摄像头")
        self.preview_btn.config(command=self.preview_camera)
    
    def stop_preview(self):
        """停止预览"""
        self.preview_running = False
        if self.preview_cap:
            self.preview_cap.release()
            self.preview_cap = None
        
        # 等待线程结束
        if self.preview_thread and self.preview_thread.is_alive():
            self.preview_thread.join(timeout=1)
        
        self.reset_preview_button()
    
    def confirm_selection(self):
        """确认选择"""
        if self.selected_camera_id is None:
            messagebox.showwarning("警告", "请先选择一个摄像头")
            return
        
        # 停止预览
        self.stop_preview()
        
        # 调用回调函数
        if self.callback:
            self.callback(self.selected_camera_id)
        
        self.root.quit()
        self.root.destroy()
    
    def refresh_cameras(self):
        """刷新摄像头列表"""
        self.status_label.config(text="正在检测摄像头设备...")
        self.root.update()
        
        # 停止预览
        self.stop_preview()
        
        # 重新检测摄像头
        detector = CameraDetector()
        self.cameras = detector.detect_cameras()
        
        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 重新填充数据
        for camera in self.cameras:
            self.tree.insert('', 'end', values=(
                camera.id,
                f"{camera.width}x{camera.height}",
                f"{camera.fps:.1f}",
                camera.backend
            ))
        
        # 重置选择
        self.selected_camera_id = None
        self.preview_btn.config(state='disabled')
        self.confirm_btn.config(state='disabled')
        
        if self.cameras:
            self.tree.selection_set(self.tree.get_children()[0])
            self.on_camera_select(None)
            self.status_label.config(text=f"检测到 {len(self.cameras)} 个摄像头设备")
        else:
            self.status_label.config(text="未检测到可用的摄像头设备")
    
    def cancel(self):
        """取消选择"""
        self.stop_preview()
        self.selected_camera_id = None
        self.root.quit()
        self.root.destroy()
    
    def show(self) -> Optional[int]:
        """显示选择器并返回选中的摄像头ID"""
        if not self.cameras:
            messagebox.showerror("错误", "未检测到可用的摄像头设备")
            return None
        
        self.root.mainloop()
        return self.selected_camera_id


def select_camera() -> Optional[int]:
    """显示摄像头选择器"""
    logging.basicConfig(level=logging.INFO)
    
    # 检测摄像头
    detector = CameraDetector()
    cameras = detector.detect_cameras()
    
    if not cameras:
        messagebox.showerror("错误", "未检测到可用的摄像头设备！\n\n请检查:\n1. 摄像头是否正确连接\n2. 摄像头权限设置\n3. 是否有其他程序占用摄像头")
        return None
    
    # 显示选择器
    selector = CameraSelectorGUI(cameras)
    return selector.show()


if __name__ == "__main__":
    selected_id = select_camera()
    if selected_id is not None:
        print(f"用户选择了摄像头 ID: {selected_id}")
    else:
        print("用户取消了选择")