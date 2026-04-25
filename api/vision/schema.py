from pydantic import BaseModel
from typing import List

class VisionRequest(BaseModel):
    """
    비전 이미지 분석 요청 스키마
    """
    image_url: str

class VisionResponse(BaseModel):
    """
    비전 이미지 분석 응답 스키마
    """
    category: str
    color: str
    embedding: List[float]
