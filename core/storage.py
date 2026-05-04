import cv2
import os
import time
from config import config

class EvidenceManager:
    """도난 증거 이미지(스냅샷)의 저장 및 경로 관리를 담당하는 클래스"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or config.SNAPSHOT_DIR
        self.snapshots_dir = self.output_dir
        self._ensure_directories()

    def _ensure_directories(self):
        """필요한 저장 디렉토리가 없으면 생성합니다."""
        if self.snapshots_dir and not os.path.exists(self.snapshots_dir):
            os.makedirs(self.snapshots_dir)

    def save_evidence(self, video_id: int, detection_count: int, 
                      frame, baseline_crop=None) -> tuple:
        """도난 시점과 물체 스냅샷을 저장하고 파일 경로를 반환합니다."""
        # 파일명 규칙: {video_id}-{count}_{type}.jpg
        moment_path = os.path.join(self.snapshots_dir, f"{video_id}-{detection_count}_theft_moment.jpg")
        baseline_path = os.path.join(self.snapshots_dir, f"{video_id}-{detection_count}_stolen_item.jpg")
        
        # 도난 시점 프레임 저장
        cv2.imwrite(moment_path, frame)
        
        # 정지 상태 기준 이미지(물체) 저장
        if baseline_crop is not None:
            cv2.imwrite(baseline_path, baseline_crop)
            print(f"[SAVE]     Evidence images saved: {baseline_path}")
            
        return moment_path, baseline_path