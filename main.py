import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from api.vision import vision
from api.cctv import cctv, service, test_callback
from models.loader import load_models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 백그라운드 워커 실행 (워커 내부에서 initialize() 호출)
    asyncio.create_task(service.cctv_service.run_worker())
    yield

app = FastAPI(
    title="2026 Myongji Capstone AI Server",
    description="CCTV Theft Detection System - AI Worker Server",
    version="1.0.0",
    lifespan=lifespan
)

# 라우터 등록
app.include_router(vision.router)
app.include_router(cctv.router)
app.include_router(test_callback.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)