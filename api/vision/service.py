from models.loader import load_models
from models.analyzer import ImageAnalyzer

class VisionService:
    def __init__(self):
        # 1. 모델 가져오기
        self.clip_model, self.processor, _ = load_models()

        # 2. 이미지 분석기 초기화
        self.analyzer = ImageAnalyzer(self.clip_model, self.processor)

    
    async def analyze_image(self, image_url: str):
        # 1. 카테고리, 색상 분석
        category, color = self.analyzer.analyze_item(image_url)

        # 2. 벡터 추출 (512차원)
        vector =  self.analyzer.extract_vector(image_url)

        return {
            "category": category,
            "color": color,
            "embedding": vector
        }
# 싱글톤 객체
vision_service = VisionService()