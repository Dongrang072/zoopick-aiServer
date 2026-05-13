# AI 서버 (FastAPI)

CCTV 영상 분석 워커 및 비전 분석 API를 제공합니다. Spring Boot **`back`** 서버와 HTTP로 연동합니다.

---

## 프로젝트 디렉터리 구조 (루트 기준)

로컬/데모 환경에서는 **한 상위 폴더**(캡스톤 프로젝트 루트) 아래에 아래처럼 두는 것을 권장합니다.

```
<프로젝트_루트>/
├── ai/                    # 본 레포지토리 (FastAPI)
├── front/                 # 프론트
└── backend/               # Spring Boot
    └── storage/
        └── cctv/
            ├── videos/        # 분석 대상 CCTV 영상
            └── snapshots/     # 검출 시 저장하는 스냅샷(크롭/프레임)
```

### 경로와 `config.py`

`config.py`의 기본값은 **프로세스 현재 작업 디렉터리(CWD) 기준 상대 경로**입니다.

| 설정 | 값(기본) | 의미 |
|------|-----------|------|
| `VIDEO_DIR` | `storage/cctv/videos/` | enqueue 시 `video_path`가 이 prefix로 시작해야 함 |
| `SNAPSHOT_DIR` | `storage/cctv/snapshots/` | 검출 이미지 저장 후 WAS 콜백에는 **파일명만** 전달 |
| `LOG_DIR` | `storage/cctv/` | 로그 등 |

즉 **`storage/`는 `ai/`와 형제 디렉터리**가 되도록 두고, 아래 실행 방법처럼 **CWD를 프로젝트 루트**로 두는 것이 경로 검증과 파일 입출력에 맞습니다.

동일 디스크 경로를 **back(WAS)** 의 `ZOOPICK_CCTV_SNAPSHOT_DIR` 등과 맞추면, WAS가 스냅샷 파일명으로 경로를 조립할 때 한 곳만 보면 됩니다.

---

## 실행 방법

### 1. Python 환경

```bash
cd <프로젝트_루트>          # ai, back, front, storage 가 보이는 폴더
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r ai/requirements.txt
```

YOLO 가중치 `yolo11s.pt`는 Ultralytics 기본 로딩 또는 프로젝트 정책에 맞게 `ai/` 등에 두면 됩니다.

### 2. 서버 기동 (**CWD = 프로젝트 루트** 권장)

```bash
cd <프로젝트_루트>
python ai/main.py
```

- 바인드: `0.0.0.0:8000` (`main.py` 기준)
- 헬스: `GET http://localhost:8000/health`

`back` 과 맞추려면 환경에 따라 `FASTAPI_BASE_URL=http://localhost:8000` 을 두면 됩니다.

---

## 환경변수

현재 AI 서버는 **대부분의 동작값이 `ai/config.py`의 `Settings` 상수**로 정해져 있습니다. 별도 `.env` 로딩 로직은 기본 포함되어 있지 않습니다.

운영 시 편하게 쓰려면 이후 **`VIDEO_DIR`, `SNAPSHOT_DIR`, 포트 등을 `os.environ`으로 읽도록 확장**하는 것을 권장합니다.

### 코드에서 참고되는 주요 설정 (`config.py`)

| 항목 | 설명 |
|------|------|
| `MODEL_ID`, `YOLO_MODEL_PATH` | CLIP / YOLO 모델 |
| `VIDEO_DIR`, `SNAPSHOT_DIR`, `LOG_DIR` | CCTV 저장 경로 |
| `ALLOWED_VIDEO_EXTENSIONS` | 허용 영상 확장자 (예: `.mp4`, `.avi`) |
| `ANALYSIS_TIMEOUT_SEC`, `CALLBACK_TIMEOUT_SEC` | 분석·콜백 타임아웃 |
| `CALLBACK_PATH_*` | WAS 내부 콜백 경로 (`/api/internal/cctv/...`) |

### OS/실행 환경에서 자주 쓰는 변수 (선택)

Python·PyTorch·Hugging Face 쪽 캐시/프록시 예시입니다. AI 레포 코드가 직접 읽는 것은 아니지만 로컬에서 문제 날 때 유용합니다.

| 변수 | 용도 |
|------|------|
| `HF_HOME`, `TRANSFORMERS_CACHE` | transformers 모델 캐시 위치 |
| `TORCH_HOME` | torch 관련 캐시 |

---

## API 목록

| Method | 경로                             | 설명                          |
| ------ | ------------------------------ | --------------------------- |
| `GET`  | `/health`                      | 서버 상태 확인                    |
| `POST` | `/vision/analyze`              | 단일 이미지 분석 (동기)              |
| `POST` | `/cctv/enqueue`                | CCTV 영상 분석 작업 등록 (WAS → AI) |
| `GET`  | `/cctv/status/{video_id}`      | 영상 분석 작업 상태 조회              |
| `POST` | `/api/internal/cctv/progress`  | 분석 진행률 및 현재 처리 시간(초) 전달       |
| `POST` | `/api/internal/cctv/detection` | 객체 탐지 결과 전달                 |
| `POST` | `/api/internal/cctv/completed` | 영상 분석 완료 결과 전달              |
| `POST` | `/api/internal/cctv/failed`    | 영상 분석 실패 상태 전달              |


Swagger(UI)는 서버 기동 후 브라우저에서 접속합니다.  
예: `http://localhost:8000/docs`

---

## AI 동작 요약

1. **요청 수신**: `POST /cctv/enqueue` 로 들어온 영상(job)은 내부 **비동기 큐**에 넣고 즉시 202로 응답합니다.
2. **백그라운드 워커**: `main.py`의 lifespan 에서 시작되는 워커가 큐에서 `video_id`를 꺼내 한 건씩 처리합니다.
3. **모델 초기화**: 워커가 최초로 돌 때 `models.loader`에서 YOLO·CLIP 로딩 후 `VideoProcessor`·`ImageAnalyzer` 에 연결합니다.
4. **영상 처리**: `core.processor` 가 프레임을 돌며 검출 파이프라인을 실행하고, 검출 시 `models.analyzer` 로 카테고리·색·임베딩을 계산합니다.
5. **WAS 콜백**: 진행 중 `progress`, 검출마다 `detection`, 종료 시 `completed` 또는 `failed` 로 **HTTP POST**합니다. 성공 여부는 주로 상태 코드 200 여부와 응답 본문(예: detection `duplicate`)을 로그로 남깁니다.

`/vision/analyze` 는 위 큐와 별개로, **단일 이미지 URL** 에 대해 동기 분석합니다.

---

## 모델·파이프라인 (개요)

| 구분 | 역할 |
|------|------|
| **YOLO** (`config.YOLO_MODEL_PATH`, 예: `yolo11s.pt`) | 영상 프레임에서 객체 검출 영역 제공 |
| **CLIP** (`config.MODEL_ID`) | 검출된 이미지에 대해 카테고리·색 라벨 및 임베딩 벡터 계산 |

자세한 임계값·후보 카테고리 목록은 `config.py`의 `VALID_LOST_ITEMS`, `ANALYSIS_CATEGORIES`, `ANALYSIS_COLORS`, 도난 관련 시간/거리 설정 등을 참고하면 됩니다.

---

## 모듈 구조 (코드 어디를 보나)

| 경로 | 설명 |
|------|------|
| `main.py` | FastAPI 앱·라우터 등록·워커 시작 |
| `config.py` | 경로·타임아웃·모델 ID·카테고리 등 전역 설정 |
| `api/cctv/` | CCTV enqueue/status API, 워커·콜백 로직 (`service.py`), 스키마 |
| `api/vision/` | `/vision/analyze` 요청 스키마·서비스 |
| `core/` | 영상 처리(`processor`), 검출(`detector`), 스냅샷 저장(`storage`), 로그(`logger`) 등 |
| `models/` | `loader`(모델 로딩), `analyzer`(CLIP 기반 분석·벡터) |

---

## 제한·운영 시 주의

- **단일 워커·큐**: 한 번에 하나의 긴 분석 작업이 돌아가므로, 큐 길이에 따라 다음 작업 시작이 늦어질 수 있습니다.
- **CWD 의존**: `VIDEO_DIR`, `SNAPSHOT_DIR` 등이 **실행 시점의 현재 디렉터리** 기준 상대경로입니다. 반드시 위 README의 디렉터리 구조·실행 명령을 지키세요.
- **스냅샷 경로 WAS와 일치**: AI가 저장한 파일을 WAS가 읽거나 경로를 조립합니다. 디렉터리를 맞추지 않으면 콜백만 성공하고 DB/파일 접근에서 어긋날 수 있습니다.
- **콜백 재시도**: WAS 5XX 등에 대한 세밀한 재시도 정책은 제한적일 수 있습니다. 장애 시 로그와 `back` 상태를 함께 확인하세요.
- **`/api/internal/cctv/*` (test_callback)**: 로컬에서 콜백 페이로드를 찍어보는 용도로 등록된 라우트입니다. 운영 배포에서는 보안 정책에 따라 비활성화·분리 검토 대상입니다.

---

아래부터는 **CCTV ↔ WAS 계약**(요청·응답·콜백) 상세 명세입니다.

---

## 엔드포인트 #1: 영상 분석 의뢰 (WAS → AI)

### POST `/cctv/enqueue`

WAS가 새 영상을 등록할 때마다 호출. AI 서버는 즉시 큐에 적재하고 202 응답.

**Request**

```json
{
  "video_id": 101,
  "video_path": "storage/cctv/videos/1_Y5407_20260427_1300.mp4",
  "duration_seconds": 600,
  "recorded_at": "2026-04-27T13:00:00",
  "callback_base_url": "http://localhost:8080"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `video_id` | int | WAS의 `cctv_videos.id`. 콜백에서 동일 값 사용 |
| `video_path` | string | **CWD 기준**으로 `config.VIDEO_DIR` prefix 하에 있어야 함 |
| `duration_seconds` | int | 영상 총 길이(초) |
| `recorded_at` | datetime | 영상 녹화 시작 시각 (검출 시점 계산용) |
| `callback_base_url` | string | 콜백을 보낼 WAS 베이스 URL |

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

> WAS가 중복 enqueue를 보내도 **에러로 두지 않고** 기존 진행을 유지하는 정책과 맞출 수 있음.

**에러 응답**

| HTTP | error_code | 발생 조건 |
|------|------------|-----------|
| 400 | `INVALID_PATH` | `video_path`가 허용 prefix 밖 |
| 404 | `VIDEO_NOT_FOUND` | 파일 없음 |
| 415 | `UNSUPPORTED_FORMAT` | 허용 확장자 외 |

---

## 엔드포인트 #2: 진행률 조회 (WAS → AI, 선택)

### GET `/cctv/status/{video_id}`

주된 업데이트는 콜백으로 처리하므로 **선택적 디버깅용**.

**Response 200** (스키마 기준, `progress_percent` 필드 없음)

```json
{
  "video_id": 101,
  "status": "IN_PROGRESS",
  "analyzed_seconds": 270,
  "total_seconds": 600,
  "detection_count_so_far": 12,
  "started_at": "2026-04-27T14:05:00",
  "estimated_completion_at": "2026-04-27T14:08:30"
}
```

`status` 값: `PENDING | IN_PROGRESS | COMPLETED | FAILED`

---

## 콜백 #1: 진행률 갱신 (AI → WAS)

### POST `{callback_base_url}/api/internal/cctv/progress`

**호출 빈도 (정책 예시)**:

- 영상 분석 시작 시 1회 (`status: IN_PROGRESS`)
- 매 30초 또는 10% 진행마다 1회 (둘 중 빠른 쪽) — 구현에 따름
- 완료는 별도 콜백 사용

**Request**

```json
{
  "video_id": 101,
  "status": "IN_PROGRESS",
  "analyzed_seconds": 270,
  "total_seconds": 600,
  "estimated_completion_at": "2026-04-27T14:08:30"
}
```

**Response 200**

```json
{ "ok": true }
```

> WAS가 5XX 응답하면 AI 서버는 다음 콜백 시점까지 대기 (재시도 없음 등 정책은 구현 참고)

---

## 콜백 #2: 검출 결과 등록 (AI → WAS)

### POST `{callback_base_url}/api/internal/cctv/detection`

**호출 시점**: 영상 분석 중 객체를 검출할 때마다 1건씩. **단건 호출** 원칙 (배치 X).

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
  "embedding": [0.123, -0.456]
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `detection_id` | string (UUID) | AI 서버 생성. 멱등성 키 |
| `video_id` | int | 어느 영상에서 검출됐는지 |
| `detected_at` | datetime | `recorded_at + 영상 내 timestamp` 로 계산 |
| `detected_category` | string | enum에 맞는 문자열 |
| `detected_color` | string | enum에 맞는 문자열 |
| `item_snapshot_filename` | string | 객체만 크롭한 이미지 **파일명** |
| `moment_snapshot_filename` | string | 검출 순간 전체 프레임 **파일명** |
| `embedding` | float[] | CLIP 임베딩 (차원은 WAS/DB 스키마와 일치) |

**Response 200** (정상 등록)

```json
{ "ok": true, "detection_db_id": 12345 }
```

**Response 200** (중복 — 멱등)

```json
{ "ok": true, "detection_db_id": 12345, "duplicate": true }
```

**스냅샷 처리**:

- AI 서버가 먼저 스냅샷을 `SNAPSHOT_DIR` (기본 `storage/cctv/snapshots/`)에 저장
- 그 다음 콜백 호출 (파일명만 전달)
- WAS는 파일명을 받아 `zoopick.cctv.snapshot-dir` 등과 조립해 DB에 반영

---

## 콜백 #3: 영상 분석 완료 (AI → WAS)

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

WAS 동작 예:

- `cctv_video_progress.status = COMPLETED`
- 이후 매칭·알림 등은 WAS 비즈니스 로직에서 처리

---

## 콜백 #4: 영상 분석 실패 (AI → WAS)

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

- `VIDEO_DECODE_ERROR` — 디코딩 실패
- `MODEL_INFERENCE_ERROR` — YOLO/CLIP 추론 실패
- `STORAGE_ERROR` — 스냅샷 저장 실패
- `TIMEOUT` — 단일 영상 처리 시간 초과
- `UNKNOWN` — 기타

WAS 동작 예:

- `cctv_video_progress.status = FAILED`
- 이미 INSERT된 검출은 유지
