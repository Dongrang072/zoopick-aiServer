import cv2
import time
import platform
from typing import Optional, Dict, List
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

    def process(self, video_path: str) -> Optional[Dict[str, str]]:
        """비디오 파일을 읽어 도난 탐지 프로세스를 수행합니다."""
        # 매번 영상이 들어올 때마다 프레임 수, 추적기 상태 등을 초기화
        self.frame_count = 0
        self.start_time = None
        self.detector = TheftDetector(
            stationary_threshold_frames=50, 
            proximity_pixels=100
        )
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"[ERROR]    Could not open video file: {video_path}")
            return None
            
        theft_snapshots = None
        
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
                theft_snapshots = self._handle_theft_detection()
                break

            # UI 또는 상태 출력
            if config.SHOW_UI:
                self._render_ui(frame, results[0], cap)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            elif self.frame_count % 100 == 0:
                print(f"[INFO]     Processing... (Frame: {self.frame_count})")
                
        self._cleanup(cap)
        return theft_snapshots

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
        cv2.destroyAllWindows()
        if platform.system() == 'Darwin':
            cv2.waitKey(1)