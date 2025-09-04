import threading
import time
from typing import Dict, Optional, Callable
from .face_mesh_detector import FaceMeshCamera
import logging


class FaceExpressionController:
    def __init__(self, camera_id: int = 0, update_rate: int = 30):
        """
        Face expression controller for real-time expression tracking.
        
        Args:
            camera_id: Camera device ID
            update_rate: Updates per second
        """
        self.camera = FaceMeshCamera(camera_id)
        self.update_rate = update_rate
        self.is_running = False
        self.thread = None
        self.logger = logging.getLogger(__name__)
        
        # Current expression values
        self.current_expressions = {
            'eyeblink_left': 0.0,
            'eyeblink_right': 0.0,
            'mouth_open': 0.0,
            'smile': 0.0
        }
        
        # Callbacks for expression changes
        self.expression_callbacks = []
        
        # Thread lock for thread safety
        self._lock = threading.Lock()

    def add_expression_callback(self, callback: Callable[[Dict[str, float]], None]):
        """
        Add callback function to be called when expressions are updated.
        
        Args:
            callback: Function that takes expressions dict as parameter
        """
        self.expression_callbacks.append(callback)

    def get_current_expressions(self) -> Dict[str, float]:
        """Get current expression values thread-safely."""
        with self._lock:
            return self.current_expressions.copy()

    def start(self) -> bool:
        """Start the face expression tracking."""
        if self.is_running:
            self.logger.warning("Face controller is already running")
            return True
        
        if not self.camera.start_camera():
            self.logger.error("Failed to start camera")
            return False
        
        self.is_running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        
        self.logger.info("Face expression controller started")
        return True

    def stop(self):
        """Stop the face expression tracking."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.thread:
            self.thread.join()
        
        self.camera.release()
        self.logger.info("Face expression controller stopped")

    def _update_loop(self):
        """Main update loop running in separate thread."""
        frame_time = 1.0 / self.update_rate
        
        while self.is_running:
            start_time = time.time()
            
            try:
                frame, expressions = self.camera.get_frame_with_expressions()
                
                if expressions:
                    # Update current expressions
                    with self._lock:
                        self.current_expressions.update(expressions)
                    
                    # Call callbacks
                    for callback in self.expression_callbacks:
                        try:
                            callback(expressions)
                        except Exception as e:
                            self.logger.error(f"Error in expression callback: {e}")
                
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
            
            # Maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


def main():
    """Example usage of FaceExpressionController."""
    logging.basicConfig(level=logging.INFO)
    
    def on_expression_update(expressions: Dict[str, float]):
        """Callback function for expression updates."""
        expr_str = " | ".join([f"{k}: {v:.2f}" for k, v in expressions.items()])
        print(f"\rExpressions: {expr_str}", end="", flush=True)
    
    # Create controller
    controller = FaceExpressionController()
    controller.add_expression_callback(on_expression_update)
    
    try:
        print("Starting face expression controller...")
        if controller.start():
            print("Controller started. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        else:
            print("Failed to start controller")
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()