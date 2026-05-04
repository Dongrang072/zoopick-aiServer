import sys
import os

class Settings:
    """프로젝트 전반에서 사용하는 설정 클래스"""
    
    # --- 모델 관련 설정 ---
    MODEL_ID = "openai/clip-vit-base-patch32"
    YOLO_MODEL_PATH = "yolo11s.pt"
    
    # --- 실행 환경 설정 ---
    VIDEO_PATH = "video/test.mp4" # 테스트용 기본 비디오 경로
    # 실행 파일 이름이 main.py인지 확인하여 서버 환경 감지
    _exec_file = os.path.basename(sys.argv[0])
    IS_SERVER = (_exec_file == 'main.py')
    SHOW_UI = False if IS_SERVER else True
    
    # --- 탐지 대상 및 분석 카테고리 ---
    VALID_LOST_ITEMS = {
        'backpack', 'umbrella', 'handbag', 
        'bottle', 'cup', 'cell phone', 'book'
    }
    
    ANALYSIS_CATEGORIES = [
        "smartphone", "earphones", "bag", "wallet", 
        "credit card", "student ID card", "textbook", "notebook", 
        "umbrella", "water bottle", "pencil case", "plush toy"
    ]
    
    ANALYSIS_COLORS = [
        "black", "white", "gray", "red", "blue", "green", 
        "yellow", "brown", "pink", "purple", "orange", "beige"
    ]
    
    # --- 도난 탐지 임계값 (초 단위 기준) ---
    STATIONARY_DURATION = 1.6      # 정지 상태 판단 시간 (초)
    VERIFICATION_DURATION = 1.0    # 사라짐 확인 대기 시간 (초)
    STATIONARY_DISTANCE_LIMIT = 50 # 정지 상태로 간주할 최대 이동 거리 (픽셀)
    PROXIMITY_LIMIT = 100          # 인접성 판단 기준 (픽셀)
    
    # --- 근접 이력 유효 시간 (초 단위) ---
    NEAR_HISTORY_TOUCH_DURATION = 4.0      # 접촉 시 이력 유지 시간
    NEAR_HISTORY_PROXIMITY_DURATION = 2.0  # 근접 시 이력 유지 시간
    
    # --- 분석 속도 및 시간 예측 ---
    ANALYSIS_SPEED_FACTOR = 0.7    # 분석 속도 계수 (실제 영상 시간 대비 처리 속도)

    # --- 도난 신뢰도 점수 가중치 ---
    THEFT_CONFIDENCE_THRESHOLD = 0.7
    CONTACT_WEIGHT = 0.3           # 비소유자 접촉
    OWNER_CLARITY_WEIGHT = 0.5     # 소유자 불일치
    NO_OWNER_WEIGHT = 0.2          # 초기 소유자 없음
    STATIONARY_WEIGHT = 0.2        # 정지 상태 확실성

    # --- CCTV 영상 검증 설정 ---
    ALLOWED_VIDEO_EXTENSIONS = ('.mp4', '.avi')  # 허용 영상 확장자
    ALLOWED_VIDEO_PREFIX = "/var/mju-lostfound/cctv/videos/"  # 운영 경로
    DEV_VIDEO_PREFIX = "ai/video/"  # 개발 경로
    SNAPSHOT_DIR = "storage/cctv/snapshots"  # 스냅샷 저장 경로
    LOG_DIR = "storage/cctv" # 로그 저장 경로

    # --- CCTV 타임아웃 설정 ---
    ANALYSIS_TIMEOUT_SEC = 1800.0  # 영상 분석 최대 시간 (초)
    CALLBACK_TIMEOUT_SEC = 2.0     # 콜백 HTTP 요청 타임아웃 (초)

    # --- CCTV 콜백 경로 ---
    CALLBACK_PATH_PROGRESS = "/api/internal/cctv/progress"
    CALLBACK_PATH_DETECTION = "/api/internal/cctv/detection"
    CALLBACK_PATH_COMPLETED = "/api/internal/cctv/completed"
    CALLBACK_PATH_FAILED = "/api/internal/cctv/failed"

# 싱글톤처럼 사용하기 위해 인스턴스화
config = Settings()