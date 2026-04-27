from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class VideoInfo(BaseModel):
    """
    CCTV 영상 정보 스키마
    """
    video_id: int
    url: str
    recorded_at: datetime

class CctvAnalyzeRequest(BaseModel):
    """
    CCTV 분석 요청 스키마
    """
    job_id: int
    callback_url: str
    videos: List[VideoInfo]


class CctvAnalyzeResponse(BaseModel):
    """
    CCTV 분석 요청 접수 응답 스키마
    """
    job_id: int
    status: str 


class DetectionInfo(BaseModel):
    """
    탐지 항목에 대한 스키마
    """
    video_id: int
    detected_at: str
    confidence: float
    category: str
    color: Optional[str] = None
    item_snapshot_url: str
    moment_snapshot_url: str

class CctvCallbackRequest(BaseModel):
    """
    CCTV 분석 요청 콜백 스키마
    """
    job_id: int
    status: str
    detections: List[DetectionInfo]
    error_message: Optional[str] = None