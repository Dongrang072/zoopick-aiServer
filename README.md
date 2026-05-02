## 엔드포인트 #1: 영상 분석 의뢰 (WAS → AI)
 
### POST `/cctv/enqueue`
 
WAS 가 새 영상을 등록할 때마다 호출. AI 서버는 즉시 큐에 적재하고 202 응답.
 
**Request**
```json
{
  "video_id": 101,
  "video_path": "/var/mju-lostfound/cctv/videos/1_Y5407_20260427_1300.mp4",
  "duration_seconds": 600,
  "recorded_at": "2026-04-27T13:00:00",
  "callback_base_url": "http://localhost:8080"
}
```
 
| 필드 | 타입 | 설명 |
|------|------|------|
| `video_id` | int | WAS 의 `cctv_videos.id`. 콜백에서 동일 값 사용 |
| `video_path` | string | 절대 경로. `/var/mju-lostfound/cctv/videos/` 외 거부 |
| `duration_seconds` | int | 영상 총 길이 |
| `recorded_at` | datetime | 영상 녹화 시작 시각 (검출 시점 계산용) |
| `callback_base_url` | string | 콜백 보낼 WAS 주소 |
 
**Response 202 Accepted**
```json
{
  "video_id": 101,
  "queued": true,
  "queue_position": 3,
  "estimated_start_at": "2026-04-27T14:05:00"
}
```
 
**Response 409 Conflict** (이미 큐에 있거나 분석 중)
```json
{
  "video_id": 101,
  "queued": false,
  "reason": "ALREADY_QUEUED"
}
```
> WAS 가 중복 enqueue 해도 **에러로 처리하지 않음**. 그냥 무시하고 기존 진행 상태 유지.
 
**에러 응답**
| HTTP | error_code | 발생 조건 |
|------|-----------|---------|
| 400 | `INVALID_PATH` | video_path 가 허용 prefix 밖 |
| 401 | `UNAUTHORIZED` | 토큰 불일치 |
| 404 | `VIDEO_NOT_FOUND` | 파일 없음 |
| 415 | `UNSUPPORTED_FORMAT` | mp4/avi 외 |
 
---
 
## 엔드포인트 #2: 진행률 조회 (WAS → AI, 선택)
 
### GET `/cctv/status/{video_id}`
 
WAS 가 폴링이 필요한 경우 사용. 주된 업데이트는 콜백으로 처리하므로 **선택적 디버깅용**.
 
**Response 200**
```json
{
  "video_id": 101,
  "status": "IN_PROGRESS",
  "analyzed_seconds": 270,
  "total_seconds": 600,
  "progress_percent": 45.0,
  "detection_count_so_far": 12,
  "started_at": "2026-04-27T14:05:00",
  "estimated_completion_at": "2026-04-27T14:08:30"
}
```
 
`status` 값: `PENDING | IN_PROGRESS | COMPLETED | FAILED`
 
---
 
##  콜백 #1: 진행률 갱신 (AI → WAS)
 
### POST `{callback_base_url}/api/internal/cctv/progress`
 
**호출 빈도**:
- 영상 분석 시작 시 1회 (`status: IN_PROGRESS`)
- 매 30초 또는 10% 진행마다 1회 (둘 중 빠른 쪽)
- 완료 시점은 별도 콜백 (콜백3번) 사용 (이건 진행률만)
**Request**
```json
{
  "video_id": 101,
  "status": "IN_PROGRESS",
  "analyzed_seconds": 270,
  "total_seconds": 600,
  "progress_percent": 45.0,
  "estimated_completion_at": "2026-04-27T14:08:30"
}
```
 
**Response 200**
```json
{ "ok": true }
```
 
> WAS 가 5XX 응답하면 AI 서버는 다음 콜백 시점까지 대기 (재시도 하지 않기)
 
---
 
##  콜백 #2: 검출 결과 등록 (AI → WAS)
 
### POST `{callback_base_url}/api/internal/cctv/detection`
 
**호출 시점**: 영상 분석 중 객체를 검출할 때마다 1건씩.
> 한 영상에서 수십~수백 건의 검출이 나올 수 있음. **단건 호출** 원칙 (배치 X).
 
**Request**
```json
{
  "detection_id": "ai-uuid-v4-string",
  "video_id": 101,
  "detected_at": "2026-04-27T13:24:18",
  "detected_category": "BAG",
  "detected_color": "BLACK",
  "item_snapshot_filename": "abc-uuid_item.jpg",
  "moment_snapshot_filename": "abc-uuid_moment.jpg",
  "embedding": [0.123, -0.456, ...]
}
```
 
| 필드 | 타입 | 설명 |
|------|------|------|
| `detection_id` | string (UUID) | AI 서버가 생성. 멱등성 키 |
| `video_id` | int | 어느 영상에서 검출됐는지 |
| `detected_at` | datetime | `recorded_at + 영상 내 timestamp` 로 계산 |
| `detected_category` | string | 12종 enum 중 1개 (이전 이슈와 동일) |
| `detected_color` | string | 12종 enum 중 1개 |
| `item_snapshot_filename` | string | 객체만 크롭한 이미지 파일명 (디렉토리 prefix 제외) |
| `moment_snapshot_filename` | string | 검출 순간 전체 프레임 파일명 |
| `embedding` | float[512] | CLIP 임베딩 (L2 정규화) |
 
**Response 200** (정상 등록)
```json
{ "ok": true, "detection_db_id": 12345 }
```
 
**Response 200** (중복으로 무시됨 — 멱등성)
```json
{ "ok": true, "detection_db_id": 12345, "duplicate": true }
```
 
> WAS 는 `detection_id` 를 5분간 Redis 에 캐싱하여 중복 처리. 같은 ID 두 번 보내도 한 번만 INSERT.
 
**스냅샷 처리**:
- AI 서버가 먼저 스냅샷을 `/var/mju-lostfound/cctv/snapshots/` 에 저장
- 그 다음 콜백 호출 (파일명만 전달)
- WAS 는 파일명을 받아 절대경로 조립 후 `cctv_detections` 에 INSERT
---
 
##  콜백 #3: 영상 분석 완료 (AI → WAS)
 
### POST `{callback_base_url}/api/internal/cctv/completed`
 
**호출 시점**: 영상 1개의 모든 프레임 분석이 끝났을 때 1회.
 
**Request**
```json
{
  "video_id": 101,
  "total_seconds": 600,
  "total_detections": 23,
  "started_at": "2026-04-27T14:05:00",
  "completed_at": "2026-04-27T14:08:42",
  "duration_ms": 222000
}
```
 
**Response 200**
```json
{ "ok": true }
```
 
WAS 동작:
- `cctv_video_progress.status = COMPLETED`
- 이 영상이 최근 신고된 LOST item 후보에 해당하면 매칭 트리거
- 사용자 알림 발송 (선택)
---
 
##  콜백 #4: 영상 분석 실패 (AI → WAS)
 
### POST `{callback_base_url}/api/internal/cctv/failed`
 
**호출 시점**: 분석 도중 회복 불가능한 에러 발생.
 
**Request**
```json
{
  "video_id": 101,
  "error_code": "VIDEO_DECODE_ERROR",
  "error_message": "Codec not supported",
  "analyzed_seconds": 120,
  "total_seconds": 600
}
```
 
`error_code` 값:
- `VIDEO_DECODE_ERROR` — FFmpeg 디코딩 실패
- `MODEL_INFERENCE_ERROR` — YOLO/CLIP 추론 실패
- `STORAGE_ERROR` — 스냅샷 저장 실패
- `TIMEOUT` — 단일 영상 처리가 30분 초과
- `UNKNOWN` — 기타
WAS 동작:
- `cctv_video_progress.status = FAILED`
- 부분적으로 검출된 결과는 `cctv_detections` 에 그대로 남김 (이미 INSERT 된 것)
- 운영자 대시보드에서 재처리 가능

