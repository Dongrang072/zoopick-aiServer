from models.loader import load_models
from core.processor import VideoProcessor
from models.analyzer import ImageAnalyzer
import requests
import threading
from datetime import timedelta
from .schema import CctvAnalyzeRequest, CctvCallbackRequest, DetectionInfo
from core.logger import TheftLogger

class CctvService:
    def __init__(self):
        # 1. 모델 가져오기
        self.clip_model, self.processor, self.yolo_model = load_models()

        self.analyzer = ImageAnalyzer(self.clip_model, self.processor)
        self.video_proc = VideoProcessor(self.yolo_model)
        self.logger = TheftLogger()
        
        # 동시성 제어를 위한 락 (GPU 리소스 및 트래커 보호)
        self.lock = threading.Lock()
    
    def analyze_video_async(self, request: CctvAnalyzeRequest):
        """
        백그라운드에서 실행될 비디오 분석 및 결과 전송 로직
        """
        print(f"[INFO]     Queueing async video analysis for job: {request.job_id}")
        
        # 변수 초기화 (Lock 외부에서 예외 발생 시 안전 보장)
        detections = []
        status = "FAILED"
        error_msg = None
        
        # 여러 요청이 들어와도 하나씩 순차적으로 처리 (Lock 사용)
        with self.lock:
            print(f"[INFO]     Starting analysis for job: {request.job_id}")
            
            try:
                for video in request.videos:
                    # 1. 영상 처리 (도난 의심 장면들 추출 - 리스트 반환)
                    snapshots_list = self.video_proc.process(video.url, video.video_id)
                    
                    # 2. 추출된 모든 스냅샷들에 대해 상세 분석 수행
                    for snapshots in snapshots_list:
                        # 카테고리 및 색상 분석
                        result = self.analyzer.analyze_item(snapshots['baseline'])
                        if result is None:
                            print(f"[WARN]     Image analysis failed, skipping detection")
                            continue
                        category, color = result
                        
                        # recorded_at + 포착 시점 경과 시간으로 실제 탐지 시각 계산
                        detected_at = video.recorded_at + timedelta(seconds=snapshots['detected_seconds'])
                        
                        detection = DetectionInfo(
                            video_id=video.video_id,
                            detected_at=detected_at.isoformat(),
                            confidence=snapshots.get('confidence'),
                            category=category,
                            color=color,
                            item_snapshot_url=f"{snapshots['baseline']}",
                            moment_snapshot_url=f"{snapshots['moment']}"
                        )
                        detections.append(detection)
                
                status = "COMPLETED" if detections else "NO_DETECTION"
                error_msg = None
                
            except Exception as e:
                print(f"[ERROR]    Async analysis failed: {e}")
                status = "FAILED"
                error_msg = str(e)
            
        # 콜백용 객체
        callback_payload = CctvCallbackRequest(
            job_id=request.job_id,
            status=status,
            detections=detections,
            error_message=error_msg
        )
        
        # 3. 결과 로깅 (콜백 데이터와 동일한 형식)
        self.logger.log_callback(callback_payload.model_dump())
        
        print(f"[INFO]     Analysis complete. Sending callback to: {request.callback_url}")
        try:
            # 콜백 주소로 콜백하기 (.model_dump() 사용)
            response = requests.post(request.callback_url, json=callback_payload.model_dump())
            print(f"[INFO]     Callback Status: {response.status_code}")
        except Exception as e:
            print(f"[CRITICAL] Failed to send callback: {e}")

# 싱글톤 객체
cctv_service = CctvService()