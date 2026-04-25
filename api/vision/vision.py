from fastapi import APIRouter
from .schema import VisionRequest, VisionResponse

router = APIRouter(
    prefix="/vision",
    tags=["vision"],
)

@router.post("/analyze", response_model=VisionResponse)
async def analyze_vision(request: VisionRequest):
    """
    단일 비전 이미지 분석 (동기 처리)
    """
    # TODO: vision_service.py를 통해 AI 모델에 이미지 분석 요청 로직 구현 예정
    
    # 임시 목업 응답 반환
    return VisionResponse(
        category="BOOK",
        color="BLUE",
        embedding=[0.0] * 512
    )
