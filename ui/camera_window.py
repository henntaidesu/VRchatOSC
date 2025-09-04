#!/usr/bin/env python3
"""
Camera Window for Face Mesh Detection
基于MediaPipe Face Mesh的摄像头面部检测窗口
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.face.face_mesh_detector import FaceMeshCamera
from src.face.face_controller import FaceExpressionController


class CameraWindow:
    """摄像头窗口类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.camera = None
        self.face_controller = None
        self.is_running = False
        self.current_frame = None
        
        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title("摄像头 - Face Mesh 面部检测")
        self.window.geometry("800x700")
        self.window.resizable(True, True)
        
        # 绑定窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_ui()
        
        # 自动初始化摄像头
        self.initialize_camera()
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding="5")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 摄像头控制
        ttk.Label(control_frame, text="摄像头ID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.camera_id_var = tk.StringVar(value="0")
        camera_combo = ttk.Combobox(control_frame, textvariable=self.camera_id_var, 
                                   values=["0", "1", "2"], width=5, state="readonly")
        camera_combo.grid(row=0, column=1, padx=(0, 10))
        
        # 开始/停止按钮
        self.start_btn = ttk.Button(control_frame, text="开始", command=self.toggle_camera)
        self.start_btn.grid(row=0, column=2, padx=(0, 10))
        
        # 截图按钮
        self.capture_btn = ttk.Button(control_frame, text="截图", command=self.capture_screenshot, 
                                     state="disabled")
        self.capture_btn.grid(row=0, column=3, padx=(0, 10))
        
        # 表情数据导出按钮
        self.export_btn = ttk.Button(control_frame, text="导出表情数据", command=self.export_expression_data,
                                    state="disabled")
        self.export_btn.grid(row=0, column=4, padx=(0, 10))
        
        # 视频显示框架
        video_frame = ttk.LabelFrame(main_frame, text="摄像头画面", padding="5")
        video_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 视频显示标签
        self.video_label = ttk.Label(video_frame, text="点击开始按钮启动摄像头", 
                                    background="black", foreground="white",
                                    font=("Arial", 12))
        self.video_label.pack(expand=True, fill=tk.BOTH)
        
        # 表情数据显示框架
        expression_frame = ttk.LabelFrame(main_frame, text="实时表情数据", padding="5")
        expression_frame.pack(fill=tk.X, pady=(0, 10))
        expression_frame.columnconfigure(1, weight=1)
        expression_frame.columnconfigure(3, weight=1)
        
        # 表情数据标签
        self.expressions = {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
        }
        
        # 创建表情显示组件
        row = 0
        col = 0
        self.expression_labels = {}
        self.expression_progress_bars = {}
        
        for expr_name in self.expressions.keys():
            # 表情名称
            display_name = {
                'eyeblink_left': '左眼眨眼',
                'eyeblink_right': '右眼眨眼',
                'mouth_open': '嘴巴张开',
                'smile': '微笑'
            }.get(expr_name, expr_name)
            
            ttk.Label(expression_frame, text=f"{display_name}:").grid(
                row=row, column=col*2, sticky=tk.W, padx=(0, 5))
            
            # 数值显示
            value_label = ttk.Label(expression_frame, text="0.00", width=6)
            value_label.grid(row=row, column=col*2+1, sticky=tk.W, padx=(0, 20))
            self.expression_labels[expr_name] = value_label
            
            # 进度条
            progress = ttk.Progressbar(expression_frame, length=100, mode='determinate')
            progress.grid(row=row, column=col*2+2, sticky=(tk.W, tk.E), padx=(0, 20))
            progress['maximum'] = 100
            self.expression_progress_bars[expr_name] = progress
            
            col += 1
            if col >= 2:
                col = 0
                row += 1
        
        # 状态栏
        self.status_label = ttk.Label(main_frame, text="准备就绪", foreground="blue")
        self.status_label.pack(side=tk.BOTTOM, anchor=tk.W)
    
    def initialize_camera(self):
        """初始化摄像头"""
        try:
            camera_id = int(self.camera_id_var.get())
            self.camera = FaceMeshCamera(camera_id)
            self.face_controller = FaceExpressionController(camera_id)
            
            # 添加表情变化回调
            self.face_controller.add_expression_callback(self.on_expression_update)
            
            self.status_label.config(text="摄像头已初始化", foreground="green")
            
        except Exception as e:
            messagebox.showerror("初始化错误", f"摄像头初始化失败: {e}")
            self.status_label.config(text=f"初始化失败: {e}", foreground="red")
    
    def toggle_camera(self):
        """切换摄像头状态"""
        if not self.is_running:
            self.start_camera()
        else:
            self.stop_camera()
    
    def start_camera(self):
        """启动摄像头"""
        try:
            if not self.camera:
                self.initialize_camera()
            
            if not self.camera:
                return
            
            # 启动表情控制器
            if self.face_controller.start():
                self.is_running = True
                self.start_btn.config(text="停止")
                self.capture_btn.config(state="normal")
                self.export_btn.config(state="normal")
                self.status_label.config(text="摄像头运行中", foreground="green")
                
                # 启动视频更新线程
                self.video_thread = threading.Thread(target=self.update_video, daemon=True)
                self.video_thread.start()
            else:
                messagebox.showerror("错误", "无法启动摄像头")
                self.status_label.config(text="启动失败", foreground="red")
                
        except Exception as e:
            messagebox.showerror("启动错误", f"启动摄像头失败: {e}")
            self.status_label.config(text=f"启动错误: {e}", foreground="red")
    
    def stop_camera(self):
        """停止摄像头"""
        try:
            self.is_running = False
            
            if self.face_controller:
                self.face_controller.stop()
            
            self.start_btn.config(text="开始")
            self.capture_btn.config(state="disabled")
            self.export_btn.config(state="disabled")
            self.status_label.config(text="摄像头已停止", foreground="blue")
            
            # 清空视频显示
            self.video_label.config(image="", text="点击开始按钮启动摄像头")
            
        except Exception as e:
            self.status_label.config(text=f"停止错误: {e}", foreground="red")
    
    def update_video(self):
        """视频更新线程"""
        while self.is_running:
            try:
                frame, expressions = self.camera.get_frame_with_expressions()
                
                if frame is not None:
                    # 转换OpenCV图像为PIL图像
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    
                    # 调整图像大小以适应显示区域
                    display_width = min(640, self.video_label.winfo_width())
                    display_height = min(480, self.video_label.winfo_height())
                    
                    if display_width > 0 and display_height > 0:
                        img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)
                    
                    # 转换为PhotoImage
                    photo = ImageTk.PhotoImage(img)
                    
                    # 更新显示（需要在主线程中执行）
                    self.current_frame = frame  # 保存当前帧用于截图
                    self.window.after(0, lambda: self.update_video_display(photo))
                    
                time.sleep(0.03)  # 约33fps
                
            except Exception as e:
                print(f"视频更新错误: {e}")
                time.sleep(0.1)
    
    def update_video_display(self, photo):
        """更新视频显示（在主线程中调用）"""
        try:
            if self.is_running:
                self.video_label.config(image=photo, text="")
                self.video_label.image = photo  # 保持引用防止垃圾回收
        except Exception as e:
            print(f"更新显示错误: {e}")
    
    def on_expression_update(self, expressions):
        """表情数据更新回调"""
        # 在主线程中更新UI
        self.window.after(0, lambda: self._update_expression_display(expressions))
    
    def _update_expression_display(self, expressions):
        """更新表情显示（在主线程中调用）"""
        try:
            for expr_name, value in expressions.items():
                if expr_name in self.expression_labels:
                    # 更新数值显示
                    self.expression_labels[expr_name].config(text=f"{value:.2f}")
                    
                    # 更新进度条
                    progress_value = min(100, max(0, value * 100))
                    self.expression_progress_bars[expr_name]['value'] = progress_value
                    
        except Exception as e:
            print(f"更新表情显示错误: {e}")
    
    def capture_screenshot(self):
        """截图功能"""
        try:
            if self.current_frame is not None:
                # 生成文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"face_capture_{timestamp}.png"
                
                # 保存截图
                cv2.imwrite(filename, self.current_frame)
                
                messagebox.showinfo("截图成功", f"截图已保存为: {filename}")
                self.status_label.config(text=f"截图已保存: {filename}", foreground="green")
            else:
                messagebox.showwarning("警告", "没有可用的画面进行截图")
                
        except Exception as e:
            messagebox.showerror("截图错误", f"截图失败: {e}")
            self.status_label.config(text=f"截图错误: {e}", foreground="red")
    
    def export_expression_data(self):
        """导出表情数据"""
        try:
            if self.face_controller:
                current_expressions = self.face_controller.get_current_expressions()
                
                # 生成文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"expression_data_{timestamp}.txt"
                
                # 保存表情数据
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("Face Expression Data\n")
                    f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*40 + "\n\n")
                    
                    for expr_name, value in current_expressions.items():
                        display_name = {
                            'eyeblink_left': '左眼眨眼',
                            'eyeblink_right': '右眼眨眼',
                            'mouth_open': '嘴巴张开',
                            'smile': '微笑'
                        }.get(expr_name, expr_name)
                        
                        f.write(f"{display_name} ({expr_name}): {value:.4f}\n")
                
                messagebox.showinfo("导出成功", f"表情数据已导出至: {filename}")
                self.status_label.config(text=f"数据已导出: {filename}", foreground="green")
            else:
                messagebox.showwarning("警告", "表情控制器未启动")
                
        except Exception as e:
            messagebox.showerror("导出错误", f"导出表情数据失败: {e}")
            self.status_label.config(text=f"导出错误: {e}", foreground="red")
    
    def on_closing(self):
        """窗口关闭事件"""
        try:
            self.stop_camera()
            self.window.destroy()
        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            self.window.destroy()


def main():
    """测试函数"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    app = CameraWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()