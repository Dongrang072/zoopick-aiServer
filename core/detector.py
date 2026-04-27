from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import cv2
import math
import time
import os
import config
from core.logger import TheftLogger

@dataclass
class TrackedItem:
    """추적 중인 물체의 상태를 관리하는 데이터 클래스"""
    id: int
    class_name: str
    owner_id: Optional[int] = None
    last_pos: Tuple[int, int] = (0, 0)
    stay_count: int = 0
    is_stationary: bool = False
    near_history: int = 0
    missing_count: int = 0
    last_person_id: Optional[int] = None
    baseline_crop: Any = None
    potential_moment_frame: Any = None

class TheftDetector:
    """도난 탐지 로직을 수행하는 메인 클래스"""
    
    def __init__(self, stationary_threshold_frames: int = 50, proximity_pixels: int = 100, 
                 missing_threshold_frames: int = 10, output_dir: str = "output", video_id: int = 0):
        self.stationary_threshold = stationary_threshold_frames
        self.proximity_pixels = proximity_pixels
        self.missing_threshold = missing_threshold_frames
        self.output_dir = output_dir
        self.video_id = video_id
        self.detection_count = 0
        
        self.tracked_items: Dict[int, TrackedItem] = {}
        self.alerts = []
        self.logger = TheftLogger()
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _calculate_distance(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        """두 점 사이의 유클리드 거리를 계산합니다."""
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def _is_touching(self, box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> bool:
        """두 바운딩 박스가 겹치는지 확인합니다."""
        return not (box1[2] < box2[0] or box1[0] > box2[2] or 
                    box1[3] < box2[1] or box1[1] > box2[3])

    def update(self, results, frame, valid_classes: List[str]) -> bool:
        """매 프레임마다 호출되어 물체 상태를 업데이트하고 도난을 탐지합니다."""
        persons, items_in_frame = self._parse_results(results, valid_classes)
        current_frame_ids = [p['id'] for p in persons] + [i['id'] for i in items_in_frame]
        
        for item in items_in_frame:
            self._process_item_state(item, persons, frame)

        return self._handle_disappearances(current_frame_ids, frame)

    def _parse_results(self, results, valid_classes: List[str]) -> Tuple[List[Dict], List[Dict]]:
        """YOLO 탐지 결과를 사람과 유효한 물체로 분류합니다."""
        persons, items = [], []
        
        if results.boxes.id is None:
            return persons, items

        for box in results.boxes:
            if box.id is None: continue
            
            track_id = int(box.id[0])
            class_name = results.names[int(box.cls[0])]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            
            data = {'id': track_id, 'center': center, 'bbox': (x1, y1, x2, y2), 'class_name': class_name}
            
            if class_name == 'person':
                persons.append(data)
            elif class_name in valid_classes:
                items.append(data)
                
        return persons, items

    def _process_item_state(self, item_dict: Dict, persons: List[Dict], frame):
        """탐지된 물체의 상태(정지 여부, 소유권, 근접 이력)를 업데이트합니다."""
        tid = item_dict['id']
        
        # 1. 새 물체 등록
        if tid not in self.tracked_items:
            self._register_new_item(item_dict, persons)

        item = self.tracked_items[tid]
        item.missing_count = 0
        
        # 2. 정지 상태 및 근접성 업데이트
        self._update_stationarity(item, item_dict['center'], item_dict['bbox'], frame)
        self._update_proximity_history(item, item_dict, persons)
        
        item.last_pos = item_dict['center']

    def _register_new_item(self, item_dict: Dict, persons: List[Dict]):
        """새로 발견된 물체를 추적 목록에 추가하고 소유자를 추정합니다."""
        owner_id, _ = self._find_closest_person(item_dict, persons)
        new_item = TrackedItem(
            id=item_dict['id'],
            class_name=item_dict['class_name'],
            owner_id=owner_id,
            last_pos=item_dict['center']
        )
        self.tracked_items[item_dict['id']] = new_item
        status = f"Person {owner_id}" if owner_id else "NO owner"
        print(f"[INFO]     ID {new_item.id}({new_item.class_name}) appeared. Owner: {status}")

    def _update_stationarity(self, item: TrackedItem, current_center: Tuple[int, int], bbox, frame):
        """물체가 움직이지 않고 한 자리에 머물고 있는지 확인합니다."""
        dist_moved = self._calculate_distance(current_center, item.last_pos)
        
        if dist_moved < 50:
            item.stay_count += 1
        else:
            item.stay_count = 0
        
        if not item.is_stationary and item.stay_count >= self.stationary_threshold:
            item.is_stationary = True
            self._save_baseline_crop(item, bbox, frame)
            print(f"[INFO]     ID {item.id}({item.class_name}) is now stationary.")

    def _update_proximity_history(self, item: TrackedItem, item_dict: Dict, persons: List[Dict]):
        """물체 주변에 누가 있었는지 기록을 업데이트합니다."""
        closest_id, is_touching = self._find_closest_person(item_dict, persons)
        
        if closest_id is not None:
            item.near_history = 120 if is_touching else 60
            item.last_person_id = closest_id
        else:
            item.near_history = max(0, item.near_history - 1)

    def _find_closest_person(self, item_dict: Dict, persons: List[Dict]) -> Tuple[Optional[int], bool]:
        """물체와 가장 가까운 사람을 찾고 접촉 여부를 반환합니다."""
        closest_id, min_dist, is_touching = None, float('inf'), False
        
        for p in persons:
            if self._is_touching(item_dict['bbox'], p['bbox']):
                return p['id'], True
            
            dist = self._calculate_distance(item_dict['center'], p['center'])
            if dist < self.proximity_pixels and dist < min_dist:
                min_dist, closest_id = dist, p['id']
                    
        return closest_id, is_touching

    def _handle_disappearances(self, current_frame_ids: List[int], frame) -> bool:
        """사라진 물체들에 대해 도난 여부를 검증합니다."""
        detected_theft = False
        for tid in list(self.tracked_items.keys()):
            if tid in current_frame_ids:
                continue
                
            item = self.tracked_items[tid]
            item.missing_count += 1
            
            if item.missing_count == 1:
                item.potential_moment_frame = frame.copy()
            
            if item.missing_count >= config.VERIFICATION_FRAMES:
                if self._verify_theft(item, frame):
                    detected_theft = True
                del self.tracked_items[tid]
                
        return detected_theft

    def _verify_theft(self, item: TrackedItem, frame) -> bool:
        """특정 물체가 도난당했는지 신뢰도 점수를 기반으로 판단합니다."""
        if not item.is_stationary or item.near_history <= 0:
            return False
            
        score = self._calculate_theft_score(item)
        if score >= config.THEFT_CONFIDENCE_THRESHOLD:
            theft_frame = item.potential_moment_frame if item.potential_moment_frame is not None else frame
            self._trigger_alert(item, theft_frame, score)
            return True
        else:
            print(f"[INFO]     ID {item.id} missing but confidence too low ({score:.2f}).")
            return False

    def _calculate_theft_score(self, item: TrackedItem) -> float:
        """도난 신뢰도 점수를 계산합니다."""
        score = 0.0
        last_p, owner_p = item.last_person_id, item.owner_id

        if last_p is not None and last_p == owner_p:
            return 0.0

        if last_p is not None:
            score += config.CONTACT_WEIGHT
            
        if owner_p is None:
            score += config.NO_OWNER_WEIGHT
        elif last_p != owner_p:
            score += config.OWNER_CLARITY_WEIGHT
            
        # 정지 상태였던 물체인지 확인 (이동 중에는 stay_count가 리셋되므로 플래그 사용)
        if item.is_stationary:
            score += config.STATIONARY_WEIGHT
        
        return min(1.0, score)

    def _save_baseline_crop(self, item: TrackedItem, bbox: Tuple[int, int, int, int], frame):
        """정지된 물체의 기준 이미지를 저장합니다."""
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        y1, y2, x1, x2 = max(0, y1), min(h, y2), max(0, x1), min(w, x2)
        item.baseline_crop = frame[y1:y2, x1:x2].copy()

    def _trigger_alert(self, item: TrackedItem, frame, score: float):
        """도난 경고를 발생시키고 증거 이미지를 저장합니다."""
        self.detection_count += 1
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # 파일명 규칙 적용: {video_id}-{sequence}_{type}.jpg
        moment_file = os.path.join(self.output_dir, f"{self.video_id}-{self.detection_count}_theft_moment.jpg")
        baseline_file = os.path.join(self.output_dir, f"{self.video_id}-{self.detection_count}_stolen_item.jpg")
        
        cv2.imwrite(moment_file, frame)
        if item.baseline_crop is not None:
            cv2.imwrite(baseline_file, item.baseline_crop)
            print(f"[SAVE]     Baseline image saved: {baseline_file}")

        print(f"[ALERT]    Theft suspected! ID: {item.id} (Confidence: {score:.2f})")
        
        alert_data = {
            'id': item.id, 'time': timestamp, 'confidence': score,
            'baseline_file': baseline_file, 'moment_file': moment_file
        }
        self.alerts.append(alert_data)
        self.logger.log_event('theft_suspected', alert_data)