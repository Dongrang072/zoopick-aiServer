import asyncio
import uuid
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from pydantic import BaseModel

from models.loader import load_models
from core.processor import VideoProcessor
from models.analyzer import ImageAnalyzer
from core.logger import TheftLogger
from .schema import (
    CctvEnqueueRequest, CctvEnqueueResponse, 
    CctvProgressCallback, DetectionInfo,
    CctvCompletedCallback, CctvFailedCallback,
    CctvStatusResponse
)

class CctvService:
    def __init__(self):
        # 모델 및 도구 초기화
        self.clip_model, self.processor, self.yolo_model = load_models()
        self.analyzer = ImageAnalyzer(self.clip_model, self.processor)
        self.video_proc = VideoProcessor(self.yolo_model)
        self.logger = TheftLogger()
        
        # 큐 및 작업 관리
        self.queue = asyncio.Queue()
        self.active_jobs: Dict[int, Dict[str, Any]] = {} # video_id -> status_info

    async def enqueue_video(self, request: CctvEnqueueRequest) -> CctvEnqueueResponse:
        """분석 요청을 큐에 적재"""
        if request.video_id in self.active_jobs:
            status = self.active_jobs[request.video_id]['status']
            if status in ["PENDING", "IN_PROGRESS"]:
                #이미 적재돼있다면 ALREADY QUEUED 반환
                return CctvEnqueueResponse(video_id=request.video_id, queued=False, reason="ALREADY_QUEUED")

        # 작업 상태 초기화
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
        
        # 큐 위치 계산
        pos = self.queue.qsize()
        return CctvEnqueueResponse(video_id=request.video_id, queued=True, queue_position=pos)

    def get_job_status(self, video_id: int) -> CctvStatusResponse:
        """현재 작업의 진행 상태 반환"""
        if video_id not in self.active_jobs:
            # 메모리 기준
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
        """백그라운드에서 큐를 감시하며 작업을 하나씩 처리"""
        print("[INFO] Worker started and waiting for jobs...")
        while True:
            video_id = await self.queue.get()
            try:
                await self._process_video(video_id)
            except Exception as e:
                print(f"[ERROR] Worker failed for video {video_id}: {e}")
            finally:
                self.queue.task_done()

    async def _process_video(self, video_id: int):
        """실제 영상 분석 및 콜백 전송 로직"""
        job = self.active_jobs[video_id]
        req: CctvEnqueueRequest = job["request"]
        job["status"] = "IN_PROGRESS"
        job["started_at"] = datetime.now()
        
        # 콜백 전송용 내부 함수
        def send_progress(current_sec, percent):
            job["progress"] = percent
            self._send_callback(f"{req.callback_base_url}/api/internal/cctv/progress", 
                               CctvProgressCallback(
                                   video_id=video_id, status="IN_PROGRESS",
                                   analyzed_seconds=int(current_sec),
                                   total_seconds=req.duration_seconds,
                                   progress_percent=percent
                               ))

        def on_detection(det_data):
            # 이미지 상세 분석 (카테고리, 벡터)
            result = self.analyzer.analyze_item(det_data['baseline'])
            if result:
                category, color = result
                vector = self.analyzer.extract_vector(det_data['baseline'])
                
                # 검출 콜백 발송
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
                self._send_callback(f"{req.callback_base_url}/api/internal/cctv/detection", detection_info)
                job["detection_count"] += 1

        # 1. 시작 콜백
        send_progress(0, 0.0)

        try:
            # 실시간 콜백을 인자로 넘겨 분석 시작
            self.video_proc.process(
                req.video_path, video_id, 
                on_progress=send_progress, 
                on_detection=on_detection
            )
            
            # 4. 완료 콜백
            job["status"] = "COMPLETED"
            job["progress"] = 100.0
            self._send_callback(f"{req.callback_base_url}/api/internal/cctv/completed",
                               CctvCompletedCallback(
                                   video_id=video_id,
                                   total_seconds=req.duration_seconds,
                                   total_detections=job["detection_count"],
                                   started_at=job["started_at"],
                                   completed_at=datetime.now(),
                                   duration_ms=int((datetime.now() - job["started_at"]).total_seconds() * 1000)
                               ))
                               
        except Exception as e:
            print(f"[ERROR] Analysis failed for {video_id}: {e}")
            job["status"] = "FAILED"
            self._send_callback(f"{req.callback_base_url}/api/internal/cctv/failed",
                               CctvFailedCallback(
                                   video_id=video_id,
                                   error_code="ANALYSIS_ERROR",
                                   error_message=str(e),
                                   analyzed_seconds=int(req.duration_seconds * (job["progress"] / 100)),
                                   total_seconds=req.duration_seconds
                               ))

    def _send_callback(self, url: str, payload: BaseModel):
        """HTTP POST 콜백 전송 (에러 핸들링 포함)"""
        try:
            res = requests.post(url, json=payload.model_dump(mode='json'))
            return res.status_code == 200
        except Exception as e:
            print(f"[WARN] Callback failed: {e}")
            return False

# 싱글톤 객체
cctv_service = CctvService()