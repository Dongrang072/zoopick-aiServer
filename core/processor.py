import cv2
import time
import platform
from typing import Optional, Dict, List, Any
import config
from core.detector import TheftDetector

class VideoProcessor:
    """비디오 스트림을 처리하고 YOLO 및 TheftDetector를 연동하는 클래스"""
    
    def __init__(self, yolo_model):
        self.model = yolo_model
        self.detector = TheftDetector(
            stationary_threshold_frames=50, 
            proximity_pixels=100
        )
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
        # 매번 영상이 들어올 때마다 프레임 수, 추적기 상태 등을 초기화
        self.frame_count = 0
        self.start_time = None
        self.detector = TheftDetector(
            stationary_threshold_frames=50, 
            proximity_pixels=100,
            video_id=video_id
        )
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        # 영상 정보 (전체 프레임, FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            
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
                if on_progress:
                    on_progress(current_seconds, progress_percent)
                
                if not config.SHOW_UI:
                    print(f"[INFO]     Processing... {progress_percent:.1f}%")

            # UI 또는 상태 출력
            if config.SHOW_UI:
                self._render_ui(frame, results[0], cap)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
        self._cleanup(cap)
        return all_detections

    def _handle_theft_detection(self) -> dict:
        """도난이 탐지되었을 때 스냅샷 및 신뢰도 정보를 추출합니다."""
        last_alert = self.detector.alerts[-1]
        print("[INFO]     Theft detected. Stopping video processing.")
        return {
            'baseline': last_alert['baseline_file'],
            'moment': last_alert['moment_file'],
            'confidence': last_alert['confidence']
        }

    def _render_ui(self, frame, detection_result, cap):
        """화면에 탐지 결과와 상태 정보를 렌더링합니다."""
        annotated_frame = detection_result.plot()
        
        elapsed_time = time.time() - self.start_time
        avg_fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # UI 오버레이 (반투명 배경)
        overlay = annotated_frame.copy()
        cv2.rectangle(overlay, (10, 10), (320, 90), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.4, annotated_frame, 0.6, 0, annotated_frame)
        
        # 텍스트 정보 표시
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(annotated_frame, f"Frame: {self.frame_count} / {total_frames}", 
                    (20, 40), font, 0.7, (255, 255, 255), 2)
        cv2.putText(annotated_frame, f"Avg FPS: {avg_fps:.2f}", 
                    (20, 75), font, 0.7, (0, 255, 0), 2)

        cv2.imshow("Theft Detection System", annotated_frame)

    def _cleanup(self, cap):
        """리소스 해제 및 윈도우 종료"""
        cap.release()
        if config.SHOW_UI:
            cv2.destroyAllWindows()
            if platform.system() == 'Darwin':
                cv2.waitKey(1)