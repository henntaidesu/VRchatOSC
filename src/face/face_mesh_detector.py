import cv2
import mediapipe as mp
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging


class FaceMeshDetector:
    def __init__(self, max_num_faces: int = 1, min_detection_confidence: float = 0.5, 
                 min_tracking_confidence: float = 0.5):
        """
        Initialize the Face Mesh detector.
        
        Args:
            max_num_faces: Maximum number of faces to detect
            min_detection_confidence: Minimum confidence value for face detection
            min_tracking_confidence: Minimum confidence value for face tracking
        """
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_num_faces,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        self.logger = logging.getLogger(__name__)
        
        # Key landmark indices for facial expressions
        self.LEFT_EYE_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
        self.RIGHT_EYE_INDICES = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
        self.MOUTH_INDICES = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 78]
        self.EYEBROW_LEFT = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
        self.EYEBROW_RIGHT = [296, 334, 293, 300, 276, 283, 282, 295, 285, 336]

    def calculate_eye_aspect_ratio(self, landmarks: List, eye_indices: List[int], 
                                 image_width: int, image_height: int) -> float:
        """Calculate Eye Aspect Ratio (EAR) for blink detection."""
        eye_points = []
        for idx in eye_indices[:6]:  # Use first 6 points for EAR calculation
            point = landmarks[idx]
            eye_points.append([point.x * image_width, point.y * image_height])
        
        eye_points = np.array(eye_points)
        
        # Vertical distances
        A = np.linalg.norm(eye_points[1] - eye_points[5])
        B = np.linalg.norm(eye_points[2] - eye_points[4])
        
        # Horizontal distance
        C = np.linalg.norm(eye_points[0] - eye_points[3])
        
        # EAR calculation
        ear = (A + B) / (2.0 * C)
        return ear

    def calculate_mouth_aspect_ratio(self, landmarks: List, image_width: int, 
                                   image_height: int) -> float:
        """Calculate Mouth Aspect Ratio (MAR) for mouth opening detection."""
        mouth_points = []
        for idx in self.MOUTH_INDICES[:8]:  # Use first 8 points for MAR calculation
            point = landmarks[idx]
            mouth_points.append([point.x * image_width, point.y * image_height])
        
        mouth_points = np.array(mouth_points)
        
        # Vertical distances
        A = np.linalg.norm(mouth_points[2] - mouth_points[6])
        B = np.linalg.norm(mouth_points[4] - mouth_points[8] if len(mouth_points) > 8 else mouth_points[3] - mouth_points[7])
        
        # Horizontal distance
        C = np.linalg.norm(mouth_points[0] - mouth_points[4])
        
        # MAR calculation
        mar = (A + B) / (2.0 * C)
        return mar

    def detect_expressions(self, landmarks: List, image_width: int, 
                         image_height: int) -> Dict[str, float]:
        """
        Detect facial expressions from landmarks.
        
        Returns:
            Dictionary containing expression values (0.0 to 1.0)
        """
        expressions = {}
        
        try:
            # Eye blink detection
            left_ear = self.calculate_eye_aspect_ratio(landmarks, self.LEFT_EYE_INDICES, 
                                                     image_width, image_height)
            right_ear = self.calculate_eye_aspect_ratio(landmarks, self.RIGHT_EYE_INDICES, 
                                                      image_width, image_height)
            
            # Average EAR and convert to blink value
            avg_ear = (left_ear + right_ear) / 2.0
            blink_value = max(0.0, min(1.0, (0.25 - avg_ear) / 0.1))  # Threshold around 0.25
            
            expressions['eyeblink_left'] = blink_value
            expressions['eyeblink_right'] = blink_value
            
            # Mouth opening detection
            mar = self.calculate_mouth_aspect_ratio(landmarks, image_width, image_height)
            mouth_open = max(0.0, min(1.0, (mar - 0.02) / 0.03))  # Normalize to 0-1
            
            expressions['mouth_open'] = mouth_open
            
            # Simple smile detection (corners of mouth vs center)
            mouth_left = landmarks[78]  # Left corner
            mouth_right = landmarks[308]  # Right corner
            mouth_center = landmarks[13]  # Center bottom
            
            left_y = mouth_left.y * image_height
            right_y = mouth_right.y * image_height
            center_y = mouth_center.y * image_height
            
            # If corners are higher than center, it's likely a smile
            smile_value = max(0.0, min(1.0, (center_y - (left_y + right_y) / 2) / 5))
            expressions['smile'] = smile_value
            
        except Exception as e:
            self.logger.error(f"Error detecting expressions: {e}")
            expressions = {
                'eyeblink_left': 0.0,
                'eyeblink_right': 0.0,
                'mouth_open': 0.0,
                'smile': 0.0
            }
        
        return expressions

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Process a single frame and return annotated frame with expression data.
        
        Args:
            frame: Input BGR image from camera
            
        Returns:
            Tuple of (annotated_frame, expressions_dict)
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        expressions = {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
        }
        
        annotated_frame = frame.copy()
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # Draw the face mesh
                self.mp_drawing.draw_landmarks(
                    annotated_frame,
                    face_landmarks,
                    self.mp_face_mesh.FACEMESH_CONTOURS,
                    None,
                    self.mp_drawing_styles.get_default_face_mesh_contours_style()
                )
                
                # Extract expression data
                height, width = frame.shape[:2]
                expressions = self.detect_expressions(face_landmarks.landmark, width, height)
                
                # Draw expression values on frame
                y_offset = 30
                for expr_name, value in expressions.items():
                    text = f"{expr_name}: {value:.2f}"
                    cv2.putText(annotated_frame, text, (10, y_offset), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    y_offset += 25
        
        return annotated_frame, expressions

    def release(self):
        """Release resources."""
        if hasattr(self, 'face_mesh'):
            self.face_mesh.close()


class FaceMeshCamera:
    def __init__(self, camera_id: int = 0, width: int = 640, height: int = 480):
        """
        Initialize camera for face mesh detection.
        
        Args:
            camera_id: Camera device ID
            width: Camera frame width
            height: Camera frame height
        """
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.cap = None
        self.detector = FaceMeshDetector()
        self.logger = logging.getLogger(__name__)

    def start_camera(self) -> bool:
        """Start the camera capture."""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                self.logger.error(f"Failed to open camera {self.camera_id}")
                return False
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            self.logger.info(f"Camera {self.camera_id} started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting camera: {e}")
            return False

    def get_frame_with_expressions(self) -> Tuple[Optional[np.ndarray], Dict[str, float]]:
        """
        Capture a frame and return it with expression data.
        
        Returns:
            Tuple of (frame, expressions_dict) or (None, empty_dict) if failed
        """
        if self.cap is None or not self.cap.isOpened():
            return None, {}
        
        try:
            ret, frame = self.cap.read()
            if not ret:
                self.logger.warning("Failed to read frame from camera")
                return None, {}
            
            annotated_frame, expressions = self.detector.process_frame(frame)
            return annotated_frame, expressions
            
        except Exception as e:
            self.logger.error(f"Error processing frame: {e}")
            return None, {}

    def run_preview(self):
        """Run a preview window showing the camera feed with face mesh."""
        if not self.start_camera():
            return
        
        self.logger.info("Starting face mesh preview. Press 'q' to quit.")
        
        try:
            while True:
                frame, expressions = self.get_frame_with_expressions()
                
                if frame is not None:
                    cv2.imshow('Face Mesh Preview', frame)
                    
                    # Print expressions to console
                    if expressions:
                        expr_str = " | ".join([f"{k}: {v:.2f}" for k, v in expressions.items()])
                        print(f"\r{expr_str}", end="", flush=True)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except KeyboardInterrupt:
            self.logger.info("Preview interrupted by user")
        finally:
            self.release()
            cv2.destroyAllWindows()

    def release(self):
        """Release camera and detector resources."""
        if self.cap is not None:
            self.cap.release()
        self.detector.release()
        self.logger.info("Camera resources released")


def main():
    """Main function to run the face mesh camera preview."""
    logging.basicConfig(level=logging.INFO)
    
    camera = FaceMeshCamera()
    camera.run_preview()


if __name__ == "__main__":
    main()