from models.loader import load_models
from core.processor import VideoProcessor
from models.analyzer import ImageAnalyzer
import requests
import threading
from .schema import CctvAnalyzeRequest, CctvCallbackRequest, DetectionInfo
from core.logger import TheftLogger
from core.processor import VideoProcessor

class CctvService:
    def __init__(self):
        # 1. 모델 가져오기
        self.clip_model, self.processor, self.yolo_model = load_models()

        self.analyzer = ImageAnalyzer(self.clip_model, self.processor)
        self.logger = TheftLogger()
        
        # 동시성 제어를 위한 락 (GPU 리소스 및 트래커 보호)
        self.lock = threading.Lock()
    
    def analyze_video_async(self, request: CctvAnalyzeRequest):
        """
        백그라운드에서 실행될 비디오 분석 및 결과 전송 로직
        """
        print(f"[INFO]     Queueing async video analysis for job: {request.job_id}")
        
        # 여러 요청이 들어와도 하나씩 순차적으로 처리 (Lock 사용)
        with self.lock:
            print(f"[INFO]     Starting analysis for job: {request.job_id}")
            detections = []
            
            # 요청마다 독립적인 VideoProcessor 생성 (상태 간섭 방지)
            video_proc = VideoProcessor(self.yolo_model)
            
            try:
                for video in request.videos:
                    # 1. 영상 처리 (도난 의심 장면 추출)
                    snapshots = video_proc.process(video.url)
                    
                    # 2. 추출된 스냅샷 상세 분석
                    if snapshots:
                        # 카테고리 및 색상 분석
                        category, color = self.analyzer.analyze_item(snapshots['baseline'])
                        
                        detection = DetectionInfo(
                            video_id=video.video_id,
                            detected_at=video.recorded_at.isoformat(),
                            confidence=snapshots.get('confidence'),
                            category=category,
                            color=color,
                            snapshot_url=f"{snapshots['moment']}"
                        )
                        detections.append(detection)
                        break
                
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