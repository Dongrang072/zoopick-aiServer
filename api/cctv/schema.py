from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# 영상 분석 의뢰 
# /cctv/enqueue
class CctvEnqueueRequest(BaseModel):
    video_id: int # WAS 의 cctv_videos.id. 콜백에서 동일 값 사용
    video_path: str # 절대 경로. /var/mju-lostfound/cctv/videos/ 외 거부
    duration_seconds: int # 영상 총 길이
    recorded_at: datetime # 영상 녹화 시작 시각 (검출 시점 계산용)
    callback_base_url: str # 콜백 보낼 WAS 주소

# 영상 분석 의뢰 response
class CctvEnqueueResponse(BaseModel):
    video_id: int
    queued: bool
    queue_position: Optional[int] = None
    estimated_start_at: Optional[datetime] = None
    reason: Optional[str] = None  # 409 Conflict에서 사용

# 진행률 조회 
# /cctv/status/{video_id}
class CctvStatusResponse(BaseModel):
    video_id: int
    status: str  # PENDING | IN_PROGRESS | COMPLETED | FAILED
    analyzed_seconds: int
    total_seconds: int
    detection_count_so_far: int
    started_at: Optional[datetime] = None
    estimated_completion_at: Optional[datetime] = None


# -------------- 콜백 -----------------
# 진행률 갱신 
# {callback_base_url}/api/internal/cctv/progress
class CctvProgressCallback(BaseModel):
    video_id: int
    status: str  # PENDING | IN_PROGRESS | COMPLETED | FAILED
    analyzed_seconds: int
    total_seconds: int
    detection_count_so_far: int
    estimated_completion_at: Optional[datetime] = None

# 검출 결과 등록 
# {callback_base_url}/api/internal/cctv/detection
class DetectionInfo(BaseModel):
    detection_id: str  # AI 서버 생성 UUID
    video_id: int
    detected_at: datetime
    detected_category: str
    detected_color: str
    item_snapshot_filename: str
    moment_snapshot_filename: str
    embedding: List[float]

# 검출 결과 등록 response 200
class DetectionCallbackResponse(BaseModel):
    ok: bool
    detection_db_id: int
    duplicate: Optional[bool] = False # 중복 처리 여부 response 200

# 영상 분석 완료 
# {callback_base_url}/api/internal/cctv/completed
class CctvCompletedCallback(BaseModel):
    video_id: int
    total_seconds: int
    total_detections: int
    started_at: datetime
    completed_at: datetime
    duration_ms: int

# 영상 분석 완료 response 200
class CommonResponse(BaseModel):
    ok: bool

# 영상 분석 실패
# {callback_base_url}/api/internal/cctv/failed
class CctvFailedCallback(BaseModel):
    video_id: int
    error_code: str
    error_message: str
    analyzed_seconds: int
    total_seconds: int
