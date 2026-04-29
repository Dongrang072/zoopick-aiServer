# AI Server API 명세

> FastAPI 서버 API 명세

---

## CCTV 도메인

### 1. CCTV 비디오 분석 요청 (비동기)

| 항목 | 내용 |
|------|------|
| **Method** | `POST` |
| **Path** | `/cctv/analyze` |
| **방향** | Spring Boot → FastAPI |
| **Status Code** | `202 Accepted` |

> CCTV 영상 리스트를 전달하여 도난 탐지 분석을 요청합니다.

**Request Body**
```json
{
  "job_id": "Long",
  "callback_url": "String",
  "videos": [
    {
      "video_id": "Long",
      "url": "String",
      "recorded_at": "String"
    }
  ]
}
```

**Response Body**
```json
{
  "job_id": "Long",
  "status": "String"
}
```

---

### 2. CCTV 분석 결과 콜백

| 항목 | 내용 |
|------|------|
| **Method** | `POST` |
| **Path** | `{callback_url}` |
| **방향** | FastAPI → Spring Boot |
| **Status Code** | `200 OK` |

> 분석이 완료되거나 실패했을 때 백엔드로 결과를 전달합니다.

**Request Body**
```json
{
  "job_id": "Long",
  "status": "String",
  "detections": [
    {
      "video_id": "Long",
      "detected_at": "String",
      "confidence": "Float",
      "category": "String",
      "color": "String",
      "embedding": "List<Float>",
      "item_snapshot_url": "String",
      "item_theft_url": "String"
    }
  ],
  "error_message": "String"
}
```

**Response Body**
```json
{
  "success": true
}
```

---

## Vision 도메인

### 1. 단일 이미지 분석 (동기)

| 항목 | 내용 |
|------|------|
| **Method** | `POST` |
| **Path** | `/vision/analyze` |
| **방향** | Spring Boot → FastAPI |
| **Status Code** | `200 OK` |

> 이미지 URL을 전달하여 카테고리, 색상, 특징 벡터를 즉시 반환받습니다.

**Request Body**
```json
{
  "image_url": "String"
}
```

**Response Body**
```json
{
  "category": "String",
  "color": "String",
  "embedding": "List<Float>"
}
```
