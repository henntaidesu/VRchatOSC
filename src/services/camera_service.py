# -*- coding: utf-8 -*-
"""
摄像头和情感识别服务层
负责处理摄像头和面部识别相关的纯业务逻辑，与UI层分离
"""

import threading
import time
import os
from datetime import datetime

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class CameraService:
    """摄像头和情感识别业务服务"""
    
    def __init__(self, config_manager):
        """
        初始化摄像头服务
        
        Args:
            config_manager: 配置管理器
        """
        self.config = config_manager
        
        # 摄像头状态
        self.camera_running = False
        self.face_detection_running = False
        self.camera = None
        self.camera_thread = None
        self.current_frame = None
        
        # 情感识别相关
        self.emotion_model_type = 'ResEmoteNet'
        self.gpu_detector = None
        self.expressions = {
            'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0,
            'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0
        }
        
        # 表情数据缓存
        self.emotion_data_cache = []
        self.last_emotion_update_time = 0
        
        # 摄像头信息缓存
        self.detected_cameras_info = {}
        
        # 控制参数
        self.current_zoom_level = 1.0
        
        # 回调函数
        self.camera_status_callback = None
        self.emotion_update_callback = None
        self.frame_callback = None
        self.log_callback = None
    
    def set_callbacks(self, camera_status_cb=None, emotion_update_cb=None, 
                     frame_cb=None, log_cb=None):
        """设置回调函数"""
        if camera_status_cb:
            self.camera_status_callback = camera_status_cb
        if emotion_update_cb:
            self.emotion_update_callback = emotion_update_cb
        if frame_cb:
            self.frame_callback = frame_cb
        if log_cb:
            self.log_callback = log_cb
    
    def log(self, message: str):
        """日志记录"""
        if self.log_callback:
            self.log_callback(message)
    
    def detect_available_cameras(self) -> list:
        """检测可用的摄像头"""
        available_cameras = []
        detected_cameras_info = {}
        
        if not CV2_AVAILABLE:
            self.log("OpenCV不可用，无法检测摄像头")
            return available_cameras
        
        self.log("开始检测摄像头和分辨率...")
        
        # 检查多个摄像头ID
        for i in range(8):
            try:
                self.log(f"正在检测摄像头 {i}...")
                camera_info = self.get_camera_info(i)
                
                if camera_info:
                    # 获取最大支持分辨率作为默认分辨率
                    if camera_info['supported_resolutions']:
                        max_res = max(camera_info['supported_resolutions'], key=lambda res: res[0] * res[1])
                        max_res_str = f"{max_res[0]}x{max_res[1]}"
                        camera_info['default_width'] = max_res[0]
                        camera_info['default_height'] = max_res[1]
                        default_res = max_res_str
                    else:
                        default_res = f"{camera_info['default_width']}x{camera_info['default_height']}"
                    
                    supported_count = len(camera_info['supported_resolutions'])
                    
                    if supported_count > 1:
                        display_name = f"摄像头 {i} (最大{default_res}, {supported_count}种分辨率)"
                    else:
                        display_name = f"摄像头 {i} ({default_res})"
                    
                    available_cameras.append((i, display_name))
                    detected_cameras_info[i] = camera_info
                    
                    # 详细日志
                    resolutions_str = ", ".join([f"{w}x{h}" for w, h in camera_info['supported_resolutions']])
                    self.log(f"[OK] 摄像头 {i}: 最大分辨率{default_res}, FPS:{camera_info['fps']:.1f}")
                    self.log(f"  支持分辨率: {resolutions_str}")
                    
            except Exception as e:
                continue
        
        # 保存摄像头信息
        self.detected_cameras_info = detected_cameras_info
        
        self.log(f"检测完成，发现 {len(available_cameras)} 个可用摄像头")
        return available_cameras
    
    def get_camera_info(self, camera_id: int) -> dict:
        """获取摄像头详细信息"""
        try:
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return None
            
            # 获取基本信息
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # 测试读取
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return None
            
            cap.release()
            
            # 获取支持的分辨率
            supported_resolutions = self.detect_camera_resolutions(camera_id)
            
            camera_info = {
                'id': camera_id,
                'default_width': width,
                'default_height': height,
                'fps': fps if fps > 0 else 30,
                'supported_resolutions': supported_resolutions,
                'working': True
            }
            
            return camera_info
            
        except Exception as e:
            self.log(f"获取摄像头 {camera_id} 信息失败: {e}")
            return None
    
    def detect_camera_resolutions(self, camera_id: int) -> list:
        """检测摄像头支持的分辨率"""
        supported_resolutions = []
        
        # 常见分辨率列表
        common_resolutions = [
            (320, 240), (640, 480), (800, 600), (1024, 768),
            (1280, 720), (1280, 960), (1600, 1200), (1920, 1080),
            (2560, 1440), (3840, 2160)
        ]
        
        try:
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return supported_resolutions
            
            for width, height in common_resolutions:
                # 尝试设置分辨率
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
                # 读取实际设置的分辨率
                actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # 如果实际分辨率与目标分辨率匹配，说明支持
                if actual_width == width and actual_height == height:
                    # 测试是否能实际读取帧
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.shape[:2] == (height, width):
                        supported_resolutions.append((width, height))
            
            cap.release()
            
        except Exception as e:
            self.log(f"检测摄像头 {camera_id} 分辨率失败: {e}")
        
        return supported_resolutions
    
    def start_camera(self, camera_id: int = 0, width: int = None, height: int = None) -> bool:
        """启动摄像头"""
        try:
            if not CV2_AVAILABLE:
                self.log("OpenCV不可用，无法启动摄像头")
                return False
                
            self.log(f"正在启动摄像头: ID {camera_id}")
            
            # 创建摄像头实例
            self.camera = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            
            if not self.camera.isOpened():
                raise RuntimeError(f"无法打开摄像头 {camera_id}")
            
            # 测试读取
            ret, frame = self.camera.read()
            if not ret or frame is None:
                raise RuntimeError(f"摄像头 {camera_id} 无法读取画面")
            
            # 设置分辨率
            if camera_id in self.detected_cameras_info:
                camera_info = self.detected_cameras_info[camera_id]
                width = width or camera_info['default_width']
                height = height or camera_info['default_height']
                self.log(f"设置摄像头分辨率为: {width}x{height}")
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            else:
                # 后备选项：使用高分辨率
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width or 1920)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height or 1080)
            
            self.camera_running = True
            
            # 启动视频显示线程
            self.camera_thread = threading.Thread(target=self._video_loop, daemon=True)
            self.camera_thread.start()
            
            # 通知UI层摄像头状态变化
            if self.camera_status_callback:
                self.camera_status_callback("camera_started", camera_id)
            
            self.log(f"摄像头启动成功: ID {camera_id}")
            return True
            
        except Exception as e:
            self.log(f"启动摄像头失败: {e}")
            if self.camera:
                self.camera.release()
                self.camera = None
            self.camera_running = False
            return False
    
    def stop_camera(self) -> bool:
        """停止摄像头"""
        try:
            self.log("正在停止摄像头...")
            self.camera_running = False
            
            # 同时停止面部识别
            if self.face_detection_running:
                self.stop_face_detection()
            
            # 等待线程结束
            if self.camera_thread and self.camera_thread.is_alive():
                self.camera_thread.join(timeout=2)
            
            # 释放摄像头
            if self.camera:
                self.camera.release()
                self.camera = None
            
            # 释放GPU检测器资源
            if self.gpu_detector is not None:
                try:
                    self.gpu_detector.release()
                    self.gpu_detector = None
                    self.log("GPU情感检测器资源已释放")
                except Exception as e:
                    self.log(f"释放GPU检测器资源时出错: {e}")
            
            # 通知UI层摄像头状态变化
            if self.camera_status_callback:
                self.camera_status_callback("camera_stopped", None)
            
            self.log("摄像头已停止")
            return True
            
        except Exception as e:
            self.log(f"停止摄像头错误: {e}")
            return False
    
    def start_face_detection(self) -> bool:
        """启动面部识别"""
        try:
            self.log(f"正在启动面部识别模型: {self.emotion_model_type}")
            
            # 如果使用GPU模型，初始化检测器
            if self.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
                if not self.gpu_detector:
                    try:
                        from src.face.gpu_emotion_detector import GPUEmotionDetector
                        self.gpu_detector = GPUEmotionDetector(model_type=self.emotion_model_type, device='auto')
                        self.log(f"成功初始化GPU情感检测器: {self.emotion_model_type}")
                    except Exception as e:
                        self.log(f"GPU检测器初始化失败: {e}")
                        self.log("将使用Simple模式作为后备")
                        self.emotion_model_type = 'Simple'
            
            self.face_detection_running = True
            
            # 重置表情数据和缓存
            self.last_emotion_update_time = time.time()
            self.emotion_data_cache.clear()
            
            # 通知UI层面部识别状态变化
            if self.camera_status_callback:
                self.camera_status_callback("face_detection_started", self.emotion_model_type)
            
            self.log("面部识别启动成功")
            return True
            
        except Exception as e:
            self.log(f"面部识别启动失败: {e}")
            return False
    
    def stop_face_detection(self) -> bool:
        """停止面部识别"""
        try:
            self.face_detection_running = False
            
            # 清空缓存
            self.emotion_data_cache.clear()
            
            # 重置表情数据为默认值
            default_expressions = {
                'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0,
                'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0
            }
            self._update_expressions(default_expressions)
            
            # 通知UI层面部识别状态变化
            if self.camera_status_callback:
                self.camera_status_callback("face_detection_stopped", None)
            
            self.log("面部识别已停止")
            return True
            
        except Exception as e:
            self.log(f"停止面部识别失败: {e}")
            return False
    
    def _video_loop(self):
        """视频显示循环"""
        frame_count = 0
        last_error_time = 0
        
        while self.camera_running and self.camera and self.camera.isOpened():
            try:
                ret, frame = self.camera.read()
                if ret and frame is not None and frame.size > 0:
                    frame_count += 1
                    
                    # 如果启用了面部识别，进行处理
                    if self.face_detection_running:
                        try:
                            display_frame, expressions = self.process_face_detection(frame)
                            # 更新表情数据
                            self._update_expressions(expressions)
                        except Exception as face_e:
                            display_frame = frame
                            if time.time() - last_error_time > 5:
                                self.log(f"面部检测错误: {face_e}")
                                last_error_time = time.time()
                    else:
                        display_frame = frame
                    
                    # 应用数字变焦
                    if self.current_zoom_level > 1.0:
                        display_frame = self.apply_digital_zoom(display_frame, self.current_zoom_level)
                    
                    # 保存当前帧
                    self.current_frame = frame
                    
                    # 通知UI层有新帧可用
                    if self.frame_callback:
                        self.frame_callback(display_frame)
                    
                else:
                    time.sleep(0.1)
                    continue
                    
                time.sleep(0.03)  # 约33fps
                
            except Exception as e:
                if self.camera_running:
                    current_time = time.time()
                    if current_time - last_error_time > 3:
                        self.log(f"视频循环错误: {e}")
                        last_error_time = current_time
                time.sleep(0.1)
    
    def process_face_detection(self, frame):
        """处理面部识别"""
        expressions = {
            'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0,
            'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0
        }
        
        try:
            if self.emotion_model_type == 'Simple':
                # 使用简单的OpenCV检测
                return self._process_simple_detection(frame)
            
            elif self.emotion_model_type in ['ResEmoteNet', 'FER2013', 'EmoNeXt']:
                # 使用GPU加速的情感识别模型
                if self.gpu_detector is not None:
                    try:
                        annotated_frame, expressions = self.gpu_detector.process_frame(frame)
                        return annotated_frame, expressions
                    except Exception as gpu_e:
                        self.log(f"GPU情感识别处理错误: {gpu_e}")
                        return self._process_simple_detection(frame)
                else:
                    try:
                        from src.face.gpu_emotion_detector import GPUEmotionDetector
                        self.gpu_detector = GPUEmotionDetector(model_type=self.emotion_model_type, device='auto')
                        annotated_frame, expressions = self.gpu_detector.process_frame(frame)
                        return annotated_frame, expressions
                    except Exception as init_e:
                        self.log(f"GPU情感检测器初始化失败: {init_e}")
                        return self._process_simple_detection(frame)
            
        except Exception as e:
            self.log(f"面部识别处理错误: {e}")
        
        return frame, expressions
    
    def _process_simple_detection(self, frame):
        """简单的面部检测处理"""
        expressions = {
            'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0,
            'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0
        }
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            
            faces = face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
                maxSize=(400, 400),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # 验证并绘制面部框
            valid_faces = []
            for (x, y, w, h) in faces:
                if self._is_valid_face(gray, x, y, w, h):
                    valid_faces.append((x, y, w, h))
                    
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
                    cv2.putText(frame, "Face Detected (Simple)", (x, y-15), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    size_text = f"Size: {w}x{h}"
                    cv2.putText(frame, size_text, (x, y + h + 20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            if len(valid_faces) > 0:
                stats_text = f"Faces: {len(valid_faces)}"
                cv2.putText(frame, stats_text, (frame.shape[1] - 120, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
        except Exception as e:
            self.log(f"简单面部检测错误: {e}")
        
        return frame, expressions
    
    def _is_valid_face(self, gray_frame, x, y, w, h):
        """验证面部区域是否有效"""
        try:
            # 检查区域大小合理性
            if w < 60 or h < 60 or w > 400 or h > 400:
                return False
            
            # 检查宽高比（人脸通常接近1:1.2）
            aspect_ratio = w / h
            if aspect_ratio < 0.7 or aspect_ratio > 1.5:
                return False
            
            # 检查区域是否在图像边界内
            if x < 0 or y < 0 or x + w > gray_frame.shape[1] or y + h > gray_frame.shape[0]:
                return False
            
            # 检查区域内的纹理复杂度
            roi = gray_frame[y:y+h, x:x+w]
            texture_variance = np.var(roi)
            if texture_variance < 50:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _update_expressions(self, expressions: dict):
        """更新表情数据"""
        try:
            # 更新表情数据
            self.expressions.update(expressions)
            
            # 将表情数据添加到缓存
            self._add_emotion_to_cache(expressions)
            
            # 通知UI层表情数据更新
            if self.emotion_update_callback:
                self.emotion_update_callback(expressions)
            
        except Exception as e:
            self.log(f"更新表情数据失败: {e}")
    
    def _add_emotion_to_cache(self, emotions: dict):
        """将表情数据添加到缓存中"""
        try:
            emotion_data = emotions.copy()
            emotion_data['timestamp'] = time.time()
            
            self.emotion_data_cache.append(emotion_data)
            
            # 限制缓存大小
            max_cache_size = 1000
            if len(self.emotion_data_cache) > max_cache_size:
                self.emotion_data_cache.pop(0)
            
        except Exception as e:
            self.log(f"添加表情数据到缓存失败: {e}")
    
    def get_average_emotions(self, interval_seconds: float = 3.0) -> dict:
        """获取指定时间间隔内的平均情感数据"""
        if not self.emotion_data_cache:
            return {'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0, 
                   'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0}
        
        try:
            current_time = time.time()
            cutoff_time = current_time - interval_seconds
            
            # 获取时间间隔内的数据
            recent_data = [data for data in self.emotion_data_cache 
                          if data.get('timestamp', 0) >= cutoff_time]
            
            if not recent_data:
                return self.expressions.copy()
            
            # 计算平均值
            avg_emotions = {}
            emotion_names = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
            
            for emotion in emotion_names:
                values = [data.get(emotion, 0.0) for data in recent_data]
                avg_emotions[emotion] = sum(values) / len(values) if values else 0.0
            
            return avg_emotions
            
        except Exception as e:
            self.log(f"计算平均情感数据失败: {e}")
            return self.expressions.copy()
    
    def get_dominant_emotion(self, emotions: dict = None) -> tuple:
        """获取主导情感"""
        if not emotions:
            emotions = self.expressions
        
        try:
            dominant_emotion = max(emotions.items(), key=lambda x: x[1])
            return dominant_emotion
        except Exception:
            return ('neutral', 0.0)
    
    def apply_digital_zoom(self, frame, zoom_level: float):
        """对单帧图像应用数字变焦"""
        try:
            if zoom_level <= 1.0 or frame is None:
                return frame
            
            height, width = frame.shape[:2]
            
            # 计算裁剪区域（从中心裁剪）
            crop_width = int(width / zoom_level)
            crop_height = int(height / zoom_level)
            
            # 确保裁剪尺寸不会过小
            crop_width = max(crop_width, 50)
            crop_height = max(crop_height, 50)
            
            # 计算裁剪的起始位置（居中）
            start_x = (width - crop_width) // 2
            start_y = (height - crop_height) // 2
            
            # 裁剪图像
            cropped_frame = frame[start_y:start_y+crop_height, start_x:start_x+crop_width]
            
            # 将裁剪后的图像放大回原始尺寸
            zoomed_frame = cv2.resize(cropped_frame, (width, height), interpolation=cv2.INTER_LINEAR)
            
            return zoomed_frame
            
        except Exception as e:
            return frame
    
    def capture_screenshot(self) -> str:
        """截图功能"""
        if not self.camera_running or not self.current_frame:
            return None
        
        try:
            # 创建截图目录
            screenshot_dir = "screenshots"
            if not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.jpg"
            filepath = os.path.join(screenshot_dir, filename)
            
            # 保存图片
            cv2.imwrite(filepath, self.current_frame)
            self.log(f"截图已保存: {filepath}")
            return filepath
            
        except Exception as e:
            self.log(f"截图失败: {e}")
            return None
    
    def save_expression_data(self) -> str:
        """保存表情数据"""
        try:
            import json
            
            # 创建数据目录
            data_dir = "expression_data"
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"expressions_{timestamp}.json"
            filepath = os.path.join(data_dir, filename)
            
            # 保存数据
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.expressions, f, ensure_ascii=False, indent=2)
            
            self.log(f"表情数据已保存: {filepath}")
            return filepath
            
        except Exception as e:
            self.log(f"保存表情数据失败: {e}")
            return None
    
    def set_emotion_model(self, model_type: str):
        """设置情感识别模型"""
        old_model = self.emotion_model_type
        self.emotion_model_type = model_type
        self.log(f"情感识别模型已切换为: {model_type}")
        
        # 释放现有的GPU检测器
        if self.gpu_detector is not None:
            try:
                self.gpu_detector.release()
                self.gpu_detector = None
                self.log("已释放旧的GPU检测器")
            except Exception as e:
                self.log(f"释放旧GPU检测器时出错: {e}")
        
        # 如果面部识别正在运行且模型发生变化，需要重启
        if self.face_detection_running and old_model != model_type:
            self.log("检测到模型变更，正在重启面部识别...")
            self.stop_face_detection()
            # 延迟重启
            threading.Timer(1.0, self.start_face_detection).start()
    
    def set_zoom_level(self, zoom_level: float):
        """设置数字变焦级别"""
        self.current_zoom_level = max(1.0, min(5.0, zoom_level))  # 限制在1.0-5.0之间
        self.log(f"数字变焦级别设置为: {self.current_zoom_level:.1f}x")
    
    def auto_focus(self) -> bool:
        """自动对焦"""
        try:
            if self.camera_running and self.camera:
                self.log("正在执行自动对焦...")
                
                success1 = self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                success2 = self.camera.set(cv2.CAP_PROP_FOCUS, 0)
                
                if success1 or success2:
                    self.log("自动对焦命令已发送")
                    
                    # 等待对焦完成
                    for i in range(10):
                        ret, frame = self.camera.read()
                        if not ret:
                            break
                        time.sleep(0.1)
                    
                    self.log("对焦操作完成")
                    return True
                else:
                    self.log("此摄像头可能不支持程序化对焦控制")
                    return False
                    
        except Exception as e:
            self.log(f"自动对焦失败: {e}")
            return False
    
    def get_camera_status(self) -> dict:
        """获取摄像头状态信息"""
        return {
            'camera_running': self.camera_running,
            'face_detection_running': self.face_detection_running,
            'emotion_model_type': self.emotion_model_type,
            'current_zoom_level': self.current_zoom_level,
            'expressions': self.expressions.copy(),
            'available_cameras': len(self.detected_cameras_info),
            'gpu_detector_ready': self.gpu_detector is not None
        }
    
    def cleanup(self):
        """清理资源"""
        if self.camera_running:
            self.stop_camera()
