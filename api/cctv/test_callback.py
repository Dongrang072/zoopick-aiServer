from fastapi import APIRouter
from .schema import (
    CctvProgressCallback, DetectionInfo, 
    CctvCompletedCallback, CctvFailedCallback,
    DetectionCallbackResponse
)

router = APIRouter(prefix="/api/internal/cctv", tags=["Test Callback"])

@router.post("/progress")
async def test_progress(payload: CctvProgressCallback):
    print(f"[TEST-CALLBACK] Progress: {payload.progress_percent}% (Video: {payload.video_id})")
    return {"ok": True}

@router.post("/detection")
async def test_detection(payload: DetectionInfo):
    print(f"[TEST-CALLBACK] 🚨 DETECTION: {payload.detected_category} / {payload.detected_color}")
    print(f"                ID: {payload.detection_id}")
    return DetectionCallbackResponse(ok=True, detection_db_id=999)

@router.post("/completed")
async def test_completed(payload: CctvCompletedCallback):
    print(f"[TEST-CALLBACK] ✅ COMPLETED: Video {payload.video_id}")
    print(f"                Total Detections: {payload.total_detections}")
    return {"ok": True}

@router.post("/failed")
async def test_failed(payload: CctvFailedCallback):
    print(f"[TEST-CALLBACK] ❌ FAILED: Video {payload.video_id}")
    print(f"                Error: {payload.error_message}")
    return {"ok": True}
