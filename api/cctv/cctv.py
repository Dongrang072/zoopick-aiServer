from fastapi import APIRouter, status
from .schema import CctvAnalyzeRequest, CctvAnalyzeResponse

router = APIRouter(
    prefix="/cctv",
    tags=["cctv"],
)

@router.post("/analyze", response_model=CctvAnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_cctv(request: CctvAnalyzeRequest):
    """
    CCTV 영상 분석 요청 접수 (비동기 처리)
    """
    # TODO: cctv_service.py로 영상 분석 작업 등록 예정
    
    # 202 Accepted와 함께 현재 상태 PROCESSING 반환 (명세서 기준)
    return CctvAnalyzeResponse(
        job_id=request.job_id,
        status="PROCESSING"
    )
