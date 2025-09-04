#!/usr/bin/env python3
"""
Emotion Detection Module
基于面部关键点几何分析的情感识别模块
"""

import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional
import logging
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import json


class GeometricEmotionDetector:
    """基于几何特征的情感识别器"""
    
    # 7种基本情感
    EMOTIONS = ['neutral', 'happy', 'sad', 'angry', 'surprise', 'fear', 'disgust']
    
    # 中文情感映射
    EMOTION_CHINESE = {
        'neutral': '中性',
        'happy': '开心',
        'sad': '悲伤',
        'angry': '愤怒',
        'surprise': '惊讶',
        'fear': '恐惧',
        'disgust': '厌恶'
    }
    
    # 面部关键点索引定义
    # 眼部关键点
    LEFT_EYE_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
    RIGHT_EYE_INDICES = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
    
    # 眉毛关键点
    LEFT_EYEBROW_INDICES = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
    RIGHT_EYEBROW_INDICES = [296, 334, 293, 300, 276, 283, 282, 295, 285, 336]
    
    # 嘴部关键点
    MOUTH_OUTER_INDICES = [61, 84, 17, 314, 405, 320, 307, 375, 321, 308, 324, 318]
    MOUTH_INNER_INDICES = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
    
    # 鼻子关键点
    NOSE_TIP_INDEX = 1
    NOSE_BRIDGE_INDICES = [6, 168, 8, 9, 10]
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scaler = None
        self.classifier = None
        self.model_path = "models/emotion_model.joblib"
        self.scaler_path = "models/emotion_scaler.joblib"
        
        # 创建模型目录
        os.makedirs("models", exist_ok=True)
        
        # 尝试加载已训练的模型
        self.load_model()
        
        # 如果没有模型，创建并训练一个基础模型
        if self.classifier is None:
            self.create_baseline_model()
    
    def extract_facial_features(self, landmarks: List, image_width: int, image_height: int) -> np.ndarray:
        """从面部关键点提取几何特征"""
        features = []
        
        try:
            # 转换关键点为像素坐标
            points = np.array([[lm.x * image_width, lm.y * image_height] for lm in landmarks])
            
            # 1. 眼部特征
            left_eye_features = self._extract_eye_features(points, self.LEFT_EYE_INDICES)
            right_eye_features = self._extract_eye_features(points, self.RIGHT_EYE_INDICES)
            features.extend(left_eye_features)
            features.extend(right_eye_features)
            
            # 2. 眉毛特征
            left_eyebrow_features = self._extract_eyebrow_features(points, self.LEFT_EYEBROW_INDICES, self.LEFT_EYE_INDICES)
            right_eyebrow_features = self._extract_eyebrow_features(points, self.RIGHT_EYEBROW_INDICES, self.RIGHT_EYE_INDICES)
            features.extend(left_eyebrow_features)
            features.extend(right_eyebrow_features)
            
            # 3. 嘴部特征
            mouth_features = self._extract_mouth_features(points)
            features.extend(mouth_features)
            
            # 4. 整体面部比例特征
            face_features = self._extract_face_features(points)
            features.extend(face_features)
            
            # 5. 对称性特征
            symmetry_features = self._extract_symmetry_features(points)
            features.extend(symmetry_features)
            
        except Exception as e:
            self.logger.error(f"特征提取出错: {e}")
            # 返回零特征向量
            features = [0.0] * 50  # 预期特征数量
        
        return np.array(features, dtype=np.float32)
    
    def _extract_eye_features(self, points: np.ndarray, eye_indices: List[int]) -> List[float]:
        """提取眼部特征"""
        features = []
        
        try:
            eye_points = points[eye_indices[:6]]  # 取前6个点计算EAR
            
            # 眼部长宽比 (Eye Aspect Ratio)
            A = np.linalg.norm(eye_points[1] - eye_points[5])
            B = np.linalg.norm(eye_points[2] - eye_points[4])
            C = np.linalg.norm(eye_points[0] - eye_points[3])
            ear = (A + B) / (2.0 * C + 1e-6)
            features.append(ear)
            
            # 眼部区域面积
            if len(eye_points) >= 4:
                area = self._calculate_polygon_area(eye_points[:4])
                features.append(area)
            else:
                features.append(0.0)
            
            # 眼部开合度
            eye_openness = B / (C + 1e-6)
            features.append(eye_openness)
            
        except Exception:
            features = [0.0, 0.0, 0.0]
        
        return features
    
    def _extract_eyebrow_features(self, points: np.ndarray, eyebrow_indices: List[int], eye_indices: List[int]) -> List[float]:
        """提取眉毛特征"""
        features = []
        
        try:
            eyebrow_points = points[eyebrow_indices[:5]]
            eye_points = points[eye_indices[:6]]
            
            # 眉毛与眼部的距离
            eyebrow_center = np.mean(eyebrow_points, axis=0)
            eye_center = np.mean(eye_points, axis=0)
            distance = np.linalg.norm(eyebrow_center - eye_center)
            features.append(distance)
            
            # 眉毛的倾斜角度
            if len(eyebrow_points) >= 2:
                angle = np.arctan2(eyebrow_points[-1][1] - eyebrow_points[0][1],
                                  eyebrow_points[-1][0] - eyebrow_points[0][0])
                features.append(np.degrees(angle))
            else:
                features.append(0.0)
            
            # 眉毛弯曲度
            if len(eyebrow_points) >= 3:
                # 使用中间点与两端连线的距离来衡量弯曲度
                mid_point = eyebrow_points[len(eyebrow_points)//2]
                line_start = eyebrow_points[0]
                line_end = eyebrow_points[-1]
                
                # 点到直线的距离
                curvature = self._point_to_line_distance(mid_point, line_start, line_end)
                features.append(curvature)
            else:
                features.append(0.0)
            
        except Exception:
            features = [0.0, 0.0, 0.0]
        
        return features
    
    def _extract_mouth_features(self, points: np.ndarray) -> List[float]:
        """提取嘴部特征"""
        features = []
        
        try:
            # 嘴角点 (左右嘴角)
            left_corner = points[61]   # 左嘴角
            right_corner = points[291] # 右嘴角
            
            # 嘴部上下点
            top_lip = points[13]       # 上唇中心
            bottom_lip = points[14]    # 下唇中心
            
            # 嘴部宽度
            mouth_width = np.linalg.norm(right_corner - left_corner)
            features.append(mouth_width)
            
            # 嘴部高度
            mouth_height = np.linalg.norm(top_lip - bottom_lip)
            features.append(mouth_height)
            
            # 嘴部长宽比
            mouth_ratio = mouth_height / (mouth_width + 1e-6)
            features.append(mouth_ratio)
            
            # 嘴角上扬度 (微笑检测)
            mouth_center_y = (top_lip[1] + bottom_lip[1]) / 2
            corner_lift = mouth_center_y - (left_corner[1] + right_corner[1]) / 2
            features.append(corner_lift)
            
            # 嘴部张开程度
            mouth_openness = mouth_height / 20.0  # 归一化
            features.append(mouth_openness)
            
            # 嘴唇厚度比例
            if len(self.MOUTH_OUTER_INDICES) >= 4 and len(self.MOUTH_INNER_INDICES) >= 4:
                outer_area = self._calculate_mouth_area(points, self.MOUTH_OUTER_INDICES[:8])
                inner_area = self._calculate_mouth_area(points, self.MOUTH_INNER_INDICES[:8])
                thickness_ratio = (outer_area - inner_area) / (outer_area + 1e-6)
                features.append(thickness_ratio)
            else:
                features.append(0.0)
            
        except Exception:
            features = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        
        return features
    
    def _extract_face_features(self, points: np.ndarray) -> List[float]:
        """提取整体面部特征"""
        features = []
        
        try:
            # 面部轮廓关键点
            face_outline = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
                           397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
                           172, 58, 132, 93, 234, 127, 162, 21, 54]
            
            # 计算面部边界框
            face_points = points[face_outline]
            
            # 面部宽度和高度
            min_x, max_x = np.min(face_points[:, 0]), np.max(face_points[:, 0])
            min_y, max_y = np.min(face_points[:, 1]), np.max(face_points[:, 1])
            
            face_width = max_x - min_x
            face_height = max_y - min_y
            
            features.append(face_width)
            features.append(face_height)
            
            # 面部长宽比
            face_ratio = face_height / (face_width + 1e-6)
            features.append(face_ratio)
            
            # 面部中心点
            face_center = np.mean(face_points, axis=0)
            features.extend(face_center.tolist())
            
        except Exception:
            features = [0.0, 0.0, 0.0, 0.0, 0.0]
        
        return features
    
    def _extract_symmetry_features(self, points: np.ndarray) -> List[float]:
        """提取对称性特征"""
        features = []
        
        try:
            # 计算左右眼的对称性
            left_eye_center = np.mean(points[self.LEFT_EYE_INDICES[:6]], axis=0)
            right_eye_center = np.mean(points[self.RIGHT_EYE_INDICES[:6]], axis=0)
            
            # 眼部高度差异
            eye_height_diff = abs(left_eye_center[1] - right_eye_center[1])
            features.append(eye_height_diff)
            
            # 嘴角对称性
            left_mouth_corner = points[61]
            right_mouth_corner = points[291]
            mouth_center = points[13]  # 上唇中心作为参考
            
            left_distance = np.linalg.norm(left_mouth_corner - mouth_center)
            right_distance = np.linalg.norm(right_mouth_corner - mouth_center)
            mouth_symmetry = abs(left_distance - right_distance) / (left_distance + right_distance + 1e-6)
            features.append(mouth_symmetry)
            
            # 眉毛对称性
            left_eyebrow_center = np.mean(points[self.LEFT_EYEBROW_INDICES[:5]], axis=0)
            right_eyebrow_center = np.mean(points[self.RIGHT_EYEBROW_INDICES[:5]], axis=0)
            eyebrow_height_diff = abs(left_eyebrow_center[1] - right_eyebrow_center[1])
            features.append(eyebrow_height_diff)
            
        except Exception:
            features = [0.0, 0.0, 0.0]
        
        return features
    
    def _calculate_polygon_area(self, points: np.ndarray) -> float:
        """计算多边形面积"""
        try:
            if len(points) < 3:
                return 0.0
            
            # 使用鞋带公式计算多边形面积
            x = points[:, 0]
            y = points[:, 1]
            return 0.5 * abs(sum(x[i]*y[i+1] - x[i+1]*y[i] for i in range(-1, len(x)-1)))
        except:
            return 0.0
    
    def _calculate_mouth_area(self, points: np.ndarray, mouth_indices: List[int]) -> float:
        """计算嘴部面积"""
        try:
            mouth_points = points[mouth_indices]
            return self._calculate_polygon_area(mouth_points)
        except:
            return 0.0
    
    def _point_to_line_distance(self, point: np.ndarray, line_start: np.ndarray, line_end: np.ndarray) -> float:
        """计算点到直线的距离"""
        try:
            # 向量
            line_vec = line_end - line_start
            point_vec = point - line_start
            
            # 投影长度
            line_len = np.linalg.norm(line_vec)
            if line_len == 0:
                return np.linalg.norm(point_vec)
            
            line_unitvec = line_vec / line_len
            proj_length = np.dot(point_vec, line_unitvec)
            proj = line_start + proj_length * line_unitvec
            
            return np.linalg.norm(point - proj)
        except:
            return 0.0
    
    def create_baseline_model(self):
        """创建基线情感识别模型"""
        try:
            # 创建一个简单的基于规则的分类器
            self.scaler = StandardScaler()
            
            # 生成一些合成训练数据用于初始化
            synthetic_features, synthetic_labels = self._generate_synthetic_training_data()
            
            # 训练分类器
            scaled_features = self.scaler.fit_transform(synthetic_features)
            
            self.classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced'
            )
            
            self.classifier.fit(scaled_features, synthetic_labels)
            
            # 保存模型
            self.save_model()
            
            self.logger.info("基线情感识别模型创建完成")
            
        except Exception as e:
            self.logger.error(f"创建基线模型失败: {e}")
    
    def _generate_synthetic_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """生成合成训练数据"""
        features = []
        labels = []
        
        # 为每种情感生成特征模式
        emotion_patterns = {
            'neutral': {
                'eye_features': [0.25, 100, 0.3] * 2,     # 正常眼部特征
                'eyebrow_features': [20, 0, 2] * 2,       # 正常眉毛特征
                'mouth_features': [40, 5, 0.125, 0, 0.25, 0.1],  # 闭合的嘴
                'face_features': [150, 200, 1.33, 100, 100],
                'symmetry_features': [1, 0.1, 1]
            },
            'happy': {
                'eye_features': [0.2, 80, 0.25] * 2,      # 稍微眯眼
                'eyebrow_features': [22, 5, 3] * 2,       # 眉毛略高
                'mouth_features': [45, 8, 0.18, 5, 0.4, 0.15],   # 嘴角上扬
                'face_features': [150, 200, 1.33, 100, 100],
                'symmetry_features': [1, 0.05, 1]
            },
            'sad': {
                'eye_features': [0.22, 90, 0.28] * 2,     # 眼部稍下垂
                'eyebrow_features': [18, -5, 1] * 2,      # 眉毛下垂
                'mouth_features': [38, 4, 0.105, -3, 0.2, 0.08],  # 嘴角下垂
                'face_features': [150, 200, 1.33, 100, 100],
                'symmetry_features': [1, 0.1, 1]
            },
            'angry': {
                'eye_features': [0.18, 70, 0.22] * 2,     # 眯眼
                'eyebrow_features': [15, -10, 1] * 2,     # 眉毛紧皱
                'mouth_features': [35, 3, 0.086, -2, 0.15, 0.06],  # 嘴部紧绷
                'face_features': [150, 200, 1.33, 100, 100],
                'symmetry_features': [2, 0.15, 2]
            },
            'surprise': {
                'eye_features': [0.35, 120, 0.4] * 2,     # 眼部睁大
                'eyebrow_features': [25, 15, 4] * 2,      # 眉毛高挑
                'mouth_features': [42, 15, 0.36, 2, 0.75, 0.2],   # 嘴巴张开
                'face_features': [150, 200, 1.33, 100, 100],
                'symmetry_features': [1, 0.05, 1]
            },
            'fear': {
                'eye_features': [0.3, 110, 0.35] * 2,     # 眼部张大
                'eyebrow_features': [23, 8, 3] * 2,       # 眉毛略高
                'mouth_features': [40, 8, 0.2, -1, 0.4, 0.12],    # 嘴部紧张
                'face_features': [150, 200, 1.33, 100, 100],
                'symmetry_features': [1.5, 0.12, 1.5]
            },
            'disgust': {
                'eye_features': [0.2, 85, 0.24] * 2,      # 眼部稍眯
                'eyebrow_features': [19, -3, 2] * 2,      # 眉毛稍皱
                'mouth_features': [38, 6, 0.16, -4, 0.3, 0.1],    # 嘴部扭曲
                'face_features': [150, 200, 1.33, 100, 100],
                'symmetry_features': [1, 0.2, 1]
            }
        }
        
        # 为每种情感生成多个样本
        for emotion_idx, (emotion, pattern) in enumerate(emotion_patterns.items()):
            for _ in range(50):  # 每种情感生成50个样本
                # 添加随机噪声
                feature_vector = []
                for feature_group in ['eye_features', 'eyebrow_features', 'mouth_features', 
                                    'face_features', 'symmetry_features']:
                    base_features = pattern[feature_group]
                    noisy_features = [f + np.random.normal(0, f * 0.1) for f in base_features]
                    feature_vector.extend(noisy_features)
                
                features.append(feature_vector)
                labels.append(emotion_idx)
        
        return np.array(features), np.array(labels)
    
    def predict_emotion(self, landmarks: List, image_width: int, image_height: int) -> Dict[str, any]:
        """预测面部情感"""
        try:
            # 提取特征
            features = self.extract_facial_features(landmarks, image_width, image_height)
            
            if self.classifier is None or self.scaler is None:
                return self._get_default_emotion_result()
            
            # 特征标准化
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            
            # 预测情感
            emotion_probs = self.classifier.predict_proba(features_scaled)[0]
            emotion_idx = np.argmax(emotion_probs)
            emotion_name = self.EMOTIONS[emotion_idx]
            confidence = emotion_probs[emotion_idx]
            
            # 创建结果字典
            result = {
                'emotion': emotion_name,
                'emotion_chinese': self.EMOTION_CHINESE[emotion_name],
                'confidence': float(confidence),
                'all_emotions': {
                    emotion: float(prob) for emotion, prob in zip(self.EMOTIONS, emotion_probs)
                }
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"情感预测出错: {e}")
            return self._get_default_emotion_result()
    
    def _get_default_emotion_result(self) -> Dict[str, any]:
        """获取默认情感结果"""
        return {
            'emotion': 'neutral',
            'emotion_chinese': '中性',
            'confidence': 0.5,
            'all_emotions': {emotion: 0.14 for emotion in self.EMOTIONS}  # 均匀分布
        }
    
    def save_model(self):
        """保存模型"""
        try:
            if self.classifier:
                joblib.dump(self.classifier, self.model_path)
            if self.scaler:
                joblib.dump(self.scaler, self.scaler_path)
            self.logger.info("情感识别模型已保存")
        except Exception as e:
            self.logger.error(f"保存模型失败: {e}")
    
    def load_model(self):
        """加载模型"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.classifier = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.logger.info("情感识别模型加载成功")
                return True
        except Exception as e:
            self.logger.error(f"加载模型失败: {e}")
        return False


def main():
    """测试函数"""
    import mediapipe as mp
    
    # 初始化MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    # 初始化情感检测器
    emotion_detector = GeometricEmotionDetector()
    
    # 打开摄像头测试
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 转换BGR到RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # 进行情感识别
                    height, width = frame.shape[:2]
                    emotion_result = emotion_detector.predict_emotion(
                        face_landmarks.landmark, width, height
                    )
                    
                    # 显示结果
                    emotion_text = f"{emotion_result['emotion_chinese']} ({emotion_result['confidence']:.2f})"
                    cv2.putText(frame, emotion_text, (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    # 显示所有情感概率
                    y_offset = 60
                    for emotion, prob in emotion_result['all_emotions'].items():
                        chinese_name = emotion_detector.EMOTION_CHINESE[emotion]
                        prob_text = f"{chinese_name}: {prob:.3f}"
                        cv2.putText(frame, prob_text, (10, y_offset), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        y_offset += 20
            
            cv2.imshow('Emotion Detection', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        cap.release()
        cv2.destroyAllWindows()
        face_mesh.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()