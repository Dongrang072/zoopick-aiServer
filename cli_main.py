import config
from models.loader import load_models
from models.analyzer import ImageAnalyzer
from core.processor import VideoProcessor
from PIL import Image
import sys

def main():
    """도난 탐지 시스템의 메인 실행 루틴"""
    print("="*50)
    print("      Cappy: Theft Detection System Starting")
    print("="*50)

    try:
        # 1. 모델 로드
        clip_model, processor, yolo_model = load_models()
        
        # 2. 컴포넌트 초기화
        video_proc = VideoProcessor(yolo_model)
        analyzer = ImageAnalyzer(clip_model, processor)
    
        # 3. 비디오 처리 (도난 탐지 단계)
        print(f"\n[STEP 1]   Monitoring Video: {config.VIDEO_PATH}")
        snapshots = video_proc.process(config.VIDEO_PATH)
    
        # 4. 결과 분석 (도난 탐지 시)
        if snapshots:
            _process_theft_result(snapshots, analyzer)
        else:
            print("\n[RESULT]   No theft events detected during monitoring.")

    except KeyboardInterrupt:
        print("\n[INFO]     System stopped by user.")
    except Exception as e:
        print(f"\n[CRITICAL] Unexpected error: {e}")
        sys.exit(1)

def _process_theft_result(snapshots, analyzer):
    """도난 탐지 결과를 화면에 표시하고 상세 분석을 수행합니다."""
    baseline_img = snapshots['baseline']
    moment_img = snapshots['moment']
    
    print(f"\n[STEP 2]   Theft Alert Triggered!")
    print(f"[RESULT]   Baseline image: {baseline_img}")
    print(f"[RESULT]   Moment image:   {moment_img}")
    
    # 이미지 표시 (오류 방지를 위한 예외 처리)
    try:
        Image.open(moment_img).show(title="THEFT MOMENT")
        Image.open(baseline_img).show(title="STOLEN ITEM (BEFORE)")
    except Exception as e:
        print(f"[WARN]     Could not display images: {e}")

    # 상세 이미지 분석 (카테고리, 색상 등)
    analyzer.analyze_item(baseline_img)
    
    # 특징 벡터 추출
    vector = analyzer.extract_vector(baseline_img)
    if vector:
        print(f"\n[STEP 3]   Vector Extraction Completed.")
        print(f"[RESULT]   Vector Dim: {len(vector)}")
        print(f"[RESULT]   Vector sample: {vector[:5]}...")

if __name__ == '__main__':
    main()