from fastapi import APIRouter, status, HTTPException
from api.cctv.schema import CctvEnqueueRequest, CctvEnqueueResponse, CctvStatusResponse
from api.cctv.service import cctv_service

router = APIRouter(
    prefix="/cctv",
    tags=["cctv"],
)

@router.post("/enqueue", response_model=CctvEnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_cctv(request: CctvEnqueueRequest):
    """
    CCTV 영상 분석 요청을 큐에 등록
    """
    import os
    
    # 1. 파일 확장자 검사 (415 UNSUPPORTED_FORMAT)
    if not request.video_path.lower().endswith(('.mp4', '.avi', '.mkv')):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error_code": "UNSUPPORTED_FORMAT", "message": "Only mp4, avi, mkv are supported"}
        )

    # 2. 허용된 경로 prefix 검사 (400 INVALID_PATH)
    # 명세서 기준 prefix
    allowed_prefix = "/var/mju-lostfound/cctv/videos/"
    # 로컬 개발 환경용 prefix (필요시 활성화)
    dev_prefix = "/Users/keonwoo/Documents/capstone_project/ai/video/"

    if not request.video_path.startswith(dev_prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_PATH", "message": f"Path must start with {allowed_prefix}"}
        )

    # 3. 파일 존재 여부 검사 (404 VIDEO_NOT_FOUND)
    if not os.path.exists(request.video_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "VIDEO_NOT_FOUND", "message": "Video file not found at given path"}
        )

    response = await cctv_service.enqueue_video(request)
    
    # 이미 큐에 있거나 분석 중인 경우 409 Conflict 반환
    if not response.queued:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=response.reason)
        
    return response
    
@router.get("/status/{video_id}", response_model=CctvStatusResponse)
async def get_cctv_status(video_id: int):
    """
    특정 영상의 분석 진행 상태 조회
    """
    status_info = cctv_service.get_job_status(video_id)
    if status_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        
    return status_info