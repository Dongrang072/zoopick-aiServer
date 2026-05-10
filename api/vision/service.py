from models.loader import load_models
from models.analyzer import ImageAnalyzer
from config import config
import os

class VisionService:
    def __init__(self):
        # 1. 모델 가져오기
        self.clip_model, self.processor, _ = load_models()

        # 2. 이미지 분석기 초기화
        self.analyzer = ImageAnalyzer(self.clip_model, self.processor)

    
    async def analyze_image(self, image_url: str):
        # 1. 카테고리, 색상 분석
        result_item = self.analyzer.analyze_item(os.path.join(config.VISION_IMAGE_PRE_DIR, image_url.lstrip("/")))
        if result_item is None:
            # pyrefly: ignore [missing-import]
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="이미지를 분석할 수 없습니다. 경로를 확인해주세요.")
            
        category, color = result_item

        # 2. 벡터 추출 (512차원)
        vector = self.analyzer.extract_vector(os.path.join(config.VISION_IMAGE_PRE_DIR, image_url.lstrip("/")))
        if vector is None:
            vector = [0.0] * 512 # 실패 시 빈 벡터라도 반환

        return {
            "category": category.replace(" ", "_").upper(),
            "color": color.replace(" ", "_").upper(),
            "embedding": vector
        }
# 싱글톤 객체
vision_service = VisionService()