import asyncio
import uuid
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pydantic import BaseModel

from models.loader import load_models
from core.processor import VideoProcessor
from models.analyzer import ImageAnalyzer
from core.logger import TheftLogger
from api.cctv.schema import (
    CctvEnqueueRequest, CctvEnqueueResponse, 
    CctvProgressCallback, DetectionInfo,
    CctvCompletedCallback, CctvFailedCallback,
    CctvStatusResponse
)

class CctvService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CctvService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        print(f"[DEBUG-INIT] CctvService instance created at {hex(id(self))}")
        self.clip_model = None
        self.processor = None
        self.yolo_model = None
        self.analyzer = None
        self.video_proc = None
        self.logger = TheftLogger()
        
        self._queue = None
        self.active_jobs: Dict[int, Dict[str, Any]] = {}
        self._initialized = True

    def initialize(self):
        if self.analyzer is not None:
            return 

        print(f"[DEBUG-LOAD] Initializing models on instance: {hex(id(self))}")
        self.clip_model, self.processor, self.yolo_model = load_models()
        self.analyzer = ImageAnalyzer(self.clip_model, self.processor)
        self.video_proc = VideoProcessor(self.yolo_model)

    @property
    def queue(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
            print(f"[DEBUG-QUEUE] New asyncio.Queue created on instance: {hex(id(self))}")
        return self._queue

    async def enqueue_video(self, request: CctvEnqueueRequest) -> CctvEnqueueResponse:
        print(f"[DEBUG-API] enqueue_video called on instance: {hex(id(self))}")
        if request.video_id in self.active_jobs:
            status = self.active_jobs[request.video_id]['status']
            if status in ["PENDING", "IN_PROGRESS"]:
                return CctvEnqueueResponse(video_id=request.video_id, queued=False, reason="ALREADY_QUEUED")

        job_info = {
            "request": request,
            "status": "PENDING",
            "progress": 0.0,
            "detection_count": 0,
            "started_at": None,
            "total_seconds": request.duration_seconds
        }
        self.active_jobs[request.video_id] = job_info
        await self.queue.put(request.video_id)
        
        pos = self.queue.qsize()
        print(f"[INFO]     Job queued. Current queue size: {pos}")
        return CctvEnqueueResponse(video_id=request.video_id, queued=True, queue_position=pos)

    def get_job_status(self, video_id: int) -> Optional[CctvStatusResponse]:
        if video_id not in self.active_jobs:
            return None 

        info = self.active_jobs[video_id]
        return CctvStatusResponse(
            video_id=video_id,
            status=info["status"],
            analyzed_seconds=int(info["total_seconds"] * (info["progress"] / 100)),
            total_seconds=info["total_seconds"],
            progress_percent=info["progress"],
            detection_count_so_far=info["detection_count"],
            started_at=info["started_at"]
        )

    async def run_worker(self):
        self.initialize()
        print(f"[DEBUG-WORKER] run_worker started on instance: {hex(id(self))}")
        print("[INFO]     Worker started and waiting for jobs...")
        while True:
            video_id = await self.queue.get()
            try:
                print(f"[INFO]     >>> Worker picked up Video ID: {video_id}")
                await self._process_video(video_id)
            except Exception as e:
                print(f"[ERROR]    Worker failed for video {video_id}: {e}")
            finally:
                self.queue.task_done()

    async def _process_video(self, video_id: int):
        job = self.active_jobs[video_id]
        req: CctvEnqueueRequest = job["request"]
        job["status"] = "IN_PROGRESS"
        job["started_at"] = datetime.now()
        
        # 메인 이벤트 루프 획득
        loop = asyncio.get_running_loop()

        def trigger_callback_async(url: str, payload: BaseModel):
            """워커 스레드에서 메인 루프에 동기 함수 실행을 안전하게 요청 (thread-safe)"""
            loop.call_soon_threadsafe(
                lambda: loop.run_in_executor(None, self._send_callback_impl, url, payload)
            )

        def send_progress(current_sec, percent):
            job["progress"] = percent
            trigger_callback_async(
                f"{req.callback_base_url}/api/internal/cctv/progress", 
                CctvProgressCallback(
                    video_id=video_id, status="IN_PROGRESS",
                    analyzed_seconds=int(current_sec),
                    total_seconds=req.duration_seconds,
                    progress_percent=percent
                )
            )

        def on_detection(det_data):
            result = self.analyzer.analyze_item(det_data['baseline'])
            if result:
                category, color = result
                vector = self.analyzer.extract_vector(det_data['baseline'])
                
                detection_info = DetectionInfo(
                    detection_id=str(uuid.uuid4()),
                    video_id=video_id,
                    detected_at=req.recorded_at + timedelta(seconds=det_data['detected_seconds']),
                    detected_category=category.replace(" ", "_").upper(),
                    detected_color=color.replace(" ", "_").upper(),
                    item_snapshot_filename=det_data['baseline'].split('/')[-1],
                    moment_snapshot_filename=det_data['moment'].split('/')[-1],
                    embedding=vector
                )
                trigger_callback_async(f"{req.callback_base_url}/api/internal/cctv/detection", detection_info)
                job["detection_count"] += 1

        print(f"[INFO]     Starting video processing loop...")
        send_progress(0, 0.0)

        try:
            await asyncio.to_thread(
                self.video_proc.process,
                req.video_path, video_id, 
                on_progress=send_progress, 
                on_detection=on_detection
            )
            
            job["status"] = "COMPLETED"
            job["progress"] = 100.0
            trigger_callback_async(
                f"{req.callback_base_url}/api/internal/cctv/completed",
                CctvCompletedCallback(
                    video_id=video_id,
                    total_seconds=req.duration_seconds,
                    total_detections=job["detection_count"],
                    started_at=job["started_at"],
                    completed_at=datetime.now(),
                    duration_ms=int((datetime.now() - job["started_at"]).total_seconds() * 1000)
                )
            )
                               
        except Exception as e:
            print(f"[ERROR]    Analysis failed for {video_id}: {e}")
            job["status"] = "FAILED"
            trigger_callback_async(
                f"{req.callback_base_url}/api/internal/cctv/failed",
                CctvFailedCallback(
                    video_id=video_id,
                    error_code="ANALYSIS_ERROR",
                    error_message=str(e),
                    analyzed_seconds=int(req.duration_seconds * (job["progress"] / 100)),
                    total_seconds=req.duration_seconds
                )
            )

    def _send_callback_impl(self, url: str, payload: BaseModel):
        """실제 HTTP 전송 (짧은 타임아웃 설정)"""
        try:
            res = requests.post(url, json=payload.model_dump(mode='json'), timeout=2.0)
            return res.status_code == 200
        except Exception as e:
            print(f"[WARN]     Callback failed to {url}: {e}")
            return False

# 싱글톤 객체 노출
cctv_service = CctvService()