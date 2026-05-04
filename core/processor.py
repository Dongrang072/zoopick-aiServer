import cv2
import time
import platform
from typing import Optional, Dict, List, Any
from config import config
from core.detector import TheftDetector
from core.visualizer import Visualizer

class VideoProcessor:
    """비디오 스트림을 처리하고 YOLO 및 TheftDetector를 연동하는 클래스"""
    
    def __init__(self, yolo_model):
        self.model = yolo_model
        # 기본 FPS 30으로 초기화 (process 호출 시 실제 FPS로 갱신됨)
        self.detector = TheftDetector(fps=30.0)
        self.visualizer = Visualizer() if config.SHOW_UI else None
        self.frame_count = 0
        self.start_time: Optional[float] = None
        self.target_indices: List[int] = []
        self._setup_target_classes()

    def _setup_target_classes(self):
        """YOLO 모델에서 추적할 대상 클래스 인덱스를 설정합니다."""
        # 기본적으로 'person' (인덱스 0) 포함
        self.target_indices = [0]
        for idx, name in self.model.names.items():
            if name in config.VALID_LOST_ITEMS:
                self.target_indices.append(idx)

    def process(self, video_path: str, video_id: int = 0, 
                on_progress=None, on_detection=None) -> List[Dict[str, Any]]:
        """비디오 파일을 읽어 도난 탐지 프로세스를 수행하며 실시간 이벤트를 알립니다."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        # 영상 정보 (전체 프레임, FPS) 추출
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        # 매번 영상이 들어올 때마다 상태 초기화
        self.frame_count = 0
        self.start_time = None
        self.detector = TheftDetector(fps=fps, video_id=video_id)
            
        all_detections = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            self.frame_count += 1
            if self.start_time is None:
                self.start_time = time.time()
                
            # YOLO 추적 실행
            results = self.model.track(
                frame, persist=True, verbose=False, 
                classes=self.target_indices, conf=0.5
            )
            
            # 도난 탐지 업데이트
            is_theft = self.detector.update(results[0], frame, config.VALID_LOST_ITEMS)
            
            if is_theft:
                # 탐지 시점의 영상 내 경과 시간 (초)
                detected_seconds = self.frame_count / fps
                last_alert = self.detector.alerts[-1]
                
                detection_data = {
                    'baseline': last_alert['baseline_file'],
                    'moment': last_alert['moment_file'],
                    'confidence': last_alert['confidence'],
                    'detected_seconds': detected_seconds
                }
                all_detections.append(detection_data)
                
                # [실시간] 검출 콜백 호출
                if on_detection:
                    on_detection(detection_data)

            # [실시간] 진행률 보고 (10% 단위)
            progress_interval = max(1, total_frames // 10)
            if self.frame_count % progress_interval == 0 or self.frame_count == total_frames:
                progress_percent = (self.frame_count / total_frames) * 100 if total_frames > 0 else 0
                current_seconds = self.frame_count / fps
                # 마지막 프레임은 completed 콜백이 처리하므로 제외
                if on_progress and self.frame_count < total_frames:
                    on_progress(current_seconds)

                if not config.SHOW_UI:
                    print(f"[INFO]     Processing... {progress_percent:.1f}%")

            # UI 출력 (Visualizer 사용)
            if self.visualizer:
                elapsed_time = time.time() - self.start_time
                avg_fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
                self.visualizer.render(frame, results[0], self.frame_count, total_frames, avg_fps)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
        self._cleanup(cap)
        return all_detections

    def _cleanup(self, cap):
        """리소스 해제 및 UI 종료"""
        cap.release()
        if self.visualizer:
            self.visualizer.close()