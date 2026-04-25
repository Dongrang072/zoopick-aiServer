from fastapi import FastAPI
import uvicorn

from api.vision import vision
from api.cctv import cctv

app = FastAPI(
    title="2026 Myongji Capstone AI Server",
    description="CCTV 도난 탐지 및 이미지 분석",
    version="1.0.0"
)

# 라우터 등록
app.include_router(vision.router)
app.include_router(cctv.router)

@app.get("/health")
async def health_check():
    """
    서버 상태 확인용 엔드포인트
    """
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)