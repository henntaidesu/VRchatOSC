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
import os
import tempfile
from typing import List, Dict, Optional, Callable
import logging

# 只在Unix/Linux系统导入fcntl
try:
    import fcntl
except ImportError:
    fcntl = None


class SingletonLock:
    """单例锁，防止多个摄像头选择器同时运行"""
    
    def __init__(self, lock_name: str = "camera_selector_lock"):
        self.lock_name = lock_name
        self.lock_file = None
        self.lock_path = os.path.join(tempfile.gettempdir(), f"{lock_name}.lock")
    
    def acquire(self) -> bool:
        """获取锁"""
        try:
            self.lock_file = open(self.lock_path, 'w')
            # Windows下使用不同的锁定机制
            if os.name == 'nt':  # Windows
                import msvcrt
                try:
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    self.lock_file.write(str(os.getpid()))
                    self.lock_file.flush()
                    return True
                except OSError:
                    self.lock_file.close()
                    self.lock_file = None
                    return False
            else:  # Unix/Linux或其他系统
                if fcntl is None:
                    # 如果fcntl不可用，使用简单的PID文件检查
                    return self._simple_pid_lock()
                try:
                    fcntl.lockf(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.lock_file.write(str(os.getpid()))
                    self.lock_file.flush()
                    return True
                except OSError:
                    self.lock_file.close()
                    self.lock_file = None
                    return False
        except Exception:
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
    
    def release(self):
        """释放锁"""
        if self.lock_file:
            try:
                if os.name == 'nt':  # Windows
                    import msvcrt
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # Unix/Linux
                    if fcntl is not None:
                        fcntl.lockf(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
            except:
                pass
            finally:
                self.lock_file = None
                # 尝试删除锁文件
                try:
                    if os.path.exists(self.lock_path):
                        os.remove(self.lock_path)
                except:
                    pass
    
    def _simple_pid_lock(self) -> bool:
        """简单的PID文件锁机制（当系统不支持文件锁时使用）"""
        try:
            if os.path.exists(self.lock_path):
                # 检查锁文件中的PID是否还在运行
                with open(self.lock_path, 'r') as f:
                    try:
                        old_pid = int(f.read().strip())
                        # 检查进程是否还存在
                        if self._is_process_running(old_pid):
                            # 进程仍在运行，无法获取锁
                            self.lock_file.close()
                            self.lock_file = None
                            return False
                        else:
                            # 进程已结束，删除旧锁文件
                            os.remove(self.lock_path)
                    except (ValueError, FileNotFoundError):
                        # 锁文件格式错误或已被删除，继续创建新锁
                        pass
            
            # 创建新的锁文件
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            return True
            
        except Exception:
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
    
    def _is_process_running(self, pid: int) -> bool:
        """检查指定PID的进程是否还在运行"""
        try:
            if os.name == 'nt':  # Windows
                import subprocess
                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                      capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                return str(pid) in result.stdout
            else:  # Unix/Linux
                os.kill(pid, 0)  # 发送信号0，不会杀死进程但会检查进程是否存在
                return True
        except (OSError, subprocess.SubprocessError):
            return False
    
    def __enter__(self):
        return self.acquire()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


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
        
        # 单例锁
        self.singleton_lock = SingletonLock("camera_selector_gui")
        
        self.root = tk.Tk()
        self.root.title("摄像头选择器")
        self.root.geometry("500x400")
        self.root.resizable(True, True)
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
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
            
            # 测试读取多帧以确保摄像头稳定工作
            test_success = 0
            for i in range(5):
                ret, test_frame = self.preview_cap.read()
                if ret and test_frame is not None:
                    test_success += 1
                time.sleep(0.1)
            
            if test_success < 3:  # 至少成功3/5次
                messagebox.showerror("错误", f"摄像头 {camera_info.id} 读取不稳定\n"
                                           f"成功率: {test_success}/5\n"
                                           f"可能原因:\n"
                                           f"1. 摄像头被Teams、Chrome、Edge等程序占用\n"
                                           f"2. 摄像头硬件故障\n"
                                           f"3. USB连接不稳定")
                self.preview_cap.release()
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
            if self.preview_cap:
                self.preview_cap.release()
                self.preview_cap = None
            messagebox.showerror("错误", f"启动预览失败: {e}")
    
    def preview_loop(self, camera_info: CameraInfo):
        """预览循环"""
        window_name = f"摄像头预览 - {camera_info}"
        frame_count = 0
        failed_count = 0
        
        try:
            while self.preview_running and self.preview_cap and self.preview_cap.isOpened():
                try:
                    ret, frame = self.preview_cap.read()
                    if ret and frame is not None:
                        frame_count += 1
                        failed_count = 0  # 重置失败计数
                        
                        # 添加信息文字
                        cv2.putText(frame, f"Camera {camera_info.id} - Frame {frame_count}", (10, 30), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.putText(frame, "Press ESC to close or click Stop Preview", (10, 60), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                        
                        cv2.imshow(window_name, frame)
                        
                        # 检查按键
                        key = cv2.waitKey(1) & 0xFF
                        if key == 27:  # ESC键
                            self.preview_running = False
                            break
                    else:
                        failed_count += 1
                        if failed_count > 30:  # 连续失败30次就退出
                            print(f"摄像头 {camera_info.id} 连续读取失败，停止预览")
                            break
                        time.sleep(0.033)  # 约30fps
                        
                except Exception as e:
                    print(f"预览循环异常: {e}")
                    break
        except Exception as e:
            print(f"预览循环严重异常: {e}")
        finally:
            # 清理资源
            try:
                if self.preview_cap:
                    self.preview_cap.release()
                cv2.destroyWindow(window_name)
                cv2.waitKey(1)  # 确保窗口被销毁
            except Exception:
                pass
            
            # 更新按钮状态（使用线程安全的方式）
            try:
                if self.preview_btn:
                    self.root.after(0, self.reset_preview_button)
            except Exception:
                pass
    
    def reset_preview_button(self):
        """重置预览按钮状态"""
        self.preview_btn.config(text="预览选中摄像头")
        self.preview_btn.config(command=self.preview_camera)
    
    def stop_preview(self):
        """停止预览"""
        print("正在停止预览...")
        
        # 设置停止标志
        self.preview_running = False
        
        # 释放摄像头资源
        if self.preview_cap:
            try:
                self.preview_cap.release()
            except Exception:
                pass
            self.preview_cap = None
        
        # 销毁OpenCV窗口
        try:
            cv2.destroyAllWindows()
            cv2.waitKey(1)
        except Exception:
            pass
        
        # 等待线程结束，但设置较短的超时时间避免卡死
        if self.preview_thread and self.preview_thread.is_alive():
            print("等待预览线程结束...")
            self.preview_thread.join(timeout=0.5)  # 减少超时时间
            if self.preview_thread.is_alive():
                print("警告: 预览线程未在预期时间内结束")
        
        # 重置按钮状态
        try:
            self.reset_preview_button()
        except Exception:
            pass
        
        print("预览已停止")
    
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
        self.on_closing()
    
    def on_closing(self):
        """窗口关闭处理"""
        print("正在关闭摄像头选择器...")
        
        # 停止预览
        self.stop_preview()
        
        # 释放单例锁
        try:
            self.singleton_lock.release()
        except Exception:
            pass
        
        # 销毁所有OpenCV窗口
        try:
            cv2.destroyAllWindows()
            cv2.waitKey(1)
        except Exception:
            pass
        
        # 退出Tkinter主循环
        try:
            self.root.quit()
        except Exception:
            pass
        
        # 销毁窗口
        try:
            self.root.destroy()
        except Exception:
            pass
        
        print("摄像头选择器已关闭")
    
    def show(self) -> Optional[int]:
        """显示选择器并返回选中的摄像头ID"""
        if not self.cameras:
            messagebox.showerror("错误", "未检测到可用的摄像头设备")
            return None
        
        # 获取单例锁
        if not self.singleton_lock.acquire():
            messagebox.showwarning("警告", "摄像头选择器已在运行中！\n请关闭已打开的摄像头选择器窗口。")
            return None
        
        try:
            self.root.mainloop()
            return self.selected_camera_id
        finally:
            self.singleton_lock.release()


def select_camera() -> Optional[int]:
    """显示摄像头选择器"""
    logging.basicConfig(level=logging.INFO)
    
    # 检查是否已有实例在运行
    singleton_check = SingletonLock("camera_selector_main")
    if not singleton_check.acquire():
        # 创建一个简单的Tkinter根窗口来显示警告
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        messagebox.showwarning("警告", "摄像头选择器已在运行中！\n请关闭已打开的摄像头选择器窗口。")
        root.destroy()
        return None
    
    try:
        # 检测摄像头
        detector = CameraDetector()
        cameras = detector.detect_cameras()
        
        if not cameras:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            messagebox.showerror("错误", "未检测到可用的摄像头设备！\n\n请检查:\n1. 摄像头是否正确连接\n2. 摄像头权限设置\n3. 是否有其他程序占用摄像头")
            root.destroy()
            return None
        
        # 显示选择器
        selector = CameraSelectorGUI(cameras)
        return selector.show()
    
    finally:
        singleton_check.release()


if __name__ == "__main__":
    selected_id = select_camera()
    if selected_id is not None:
        print(f"用户选择了摄像头 ID: {selected_id}")
    else:
        print("用户取消了选择")