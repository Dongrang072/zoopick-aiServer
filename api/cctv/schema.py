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
    building_id: int
    room_number: str

class TargetTraits(BaseModel):
    """
    탐지할 대상의 특징 스키마
    """
    category: Optional[str] = None
    color: Optional[str] = None

class CctvAnalyzeRequest(BaseModel):
    """
    CCTV 분석 요청 스키마
    """
    job_id: int
    callback_url: str
    videos: List[VideoInfo]
    target_traits: TargetTraits

class CctvAnalyzeResponse(BaseModel):
    """
    CCTV 분석 요청 접수 응답 스키마
    """
    job_id: int
    status: str
