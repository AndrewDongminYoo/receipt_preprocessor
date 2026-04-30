# Receipt Preprocessor Agent — Design Spec

**Date:** 2026-04-30  
**Status:** Approved  
**Project:** multiagent-handson fork → `receipt-preprocessor`

---

## Context

영끌(Youngkeul)은 마트·편의점·수퍼마켓 영수증을 업로드하는 앱테크 앱이다. 현재 영수증 이미지는 Azure OCR 백엔드(`v1/receipts/validate`)로 직접 전송되는데, 다음 두 가지 문제가 주요 실패 원인이다.

1. **기하학적 왜곡** — 비스듬한 각도, 원근 왜곡, 구겨진 영수증으로 인한 OCR 정확도 저하
2. **유효성 문제** — 환불 영수증, 중복 업로드, 해외 영수증, 비유통 영수증이 Azure에 그대로 전달

이 스펙은 Azure 앞단에서 동작하는 **하이브리드 전처리 파이프라인**을 정의한다. 모바일에서 가벼운 검사를 수행하고, 클라우드에서 Gemini Vision 기반 분류·품질 평가·원근 보정을 담당한다. Azure 기존 코드는 변경하지 않는다.

---

## Architecture Overview

```plaintext
[영끌 React Native 앱]
       │
       │ 이미지 선택 (카메라 / 갤러리)
       ▼
┌─────────────────────────────────────┐
│  Mobile Pre-flight Layer            │
│  (기존 코드 확장, 로컬 처리)          │
│  ① 파일 형식/크기 검사               │
│  ② 환불 영수증 정규식 감지            │
│  ③ Fingerprint 중복 감지             │
└────────────────┬────────────────────┘
                 │ 통과 시
                 ▼
┌──────────────────────────────────────────────────┐
│  Cloud Pre-processing Agent  (Google ADK)         │
│  SequentialAgent: receipt_preprocessor            │
│                                                   │
│  1. ValidityGateAgent                             │
│     Gemini Vision → DOMESTIC_RETAIL / OVERSEAS /  │
│                     NON_RETAIL / NON_RECEIPT       │
│     Gate: DOMESTIC_RETAIL 아니면 즉시 중단         │
│                                                   │
│  2. QualityGateAgent                              │
│     흐림·노출·해상도 점수 (0–10)                    │
│     Gate: score < QUALITY_THRESHOLD 시 중단        │
│                                                   │
│  3. GeometryAgent                                 │
│     꼭짓점 감지 → 원근 보정 → GCS 저장             │
│     Soft gate: 감지 실패 시 원본 이미지로 통과      │
│                                                   │
│  4. PackagingAgent                                │
│     보정 이미지 + 분류 메타데이터 → JSON payload   │
└────────────────┬─────────────────────────────────┘
                 │ PASS: { correctedImageUrl, storeCategory, preprocessMeta }
                 │ REJECT: { code, userMessage }
                 ▼
      [Azure OCR: v1/receipts/validate]  ← 기존 그대로
```

---

## Rejection Codes

| 코드               | 발생 레이어 | 의미                    | 사용자 안내 방향            |
| ------------------ | ----------- | ----------------------- | --------------------------- |
| `FILE_INVALID`     | 모바일      | 형식·크기 미달          | 다른 이미지 선택 요청       |
| `DUPLICATE`        | 모바일      | 동일 영수증 재업로드    | 이미 등록된 영수증임을 안내 |
| `REFUND_RECEIPT`   | 모바일      | 환불/반품 영수증        | 환불 영수증은 미지원 안내   |
| `NON_RECEIPT`      | 클라우드    | 영수증이 아닌 이미지    | 영수증 사진 재촬영 요청     |
| `OVERSEAS_RECEIPT` | 클라우드    | 해외 영수증             | 국내 영수증만 지원 안내     |
| `NON_RETAIL`       | 클라우드    | 마트·편의점·수퍼마켓 외 | 지원 업종 안내              |
| `QUALITY_LOW`      | 클라우드    | 흐림·노출 기준 미달     | 재촬영 가이드 표시          |
| `GEOMETRY_FAILED`  | 클라우드    | 원근 보정 불가 (soft)   | 원본 이미지로 통과, 로깅만  |

---

## Agent Internals

### ValidityGateAgent

```
Model: gemini-2.5-flash
Tools:
  classify_receipt(image_uri)
    → { type: DOMESTIC_RETAIL | OVERSEAS | NON_RETAIL | NON_RECEIPT,
        store_category: MART | CONVENIENCE | SUPERMARKET | OTHER,
        confidence: float }
  reject_with_code(code, user_message)
    → 세션 상태에 rejection_code 기록 후 escalate

Output keys: receipt_type, store_category
Gate condition: type != DOMESTIC_RETAIL → reject
```

분류 기준은 `policy.json`에 정의된 허용 유통 카테고리 목록과 국가 코드 키워드를 참조한다.

### QualityGateAgent

```
Model: gemini-2.5-flash
Tools:
  score_image_quality(image_uri)
    → { score: 0–10, issues: ["blur" | "overexposed" | "underexposed" | "occluded" | "low_res"] }
  reject_with_code(code, user_message)

Output keys: quality_score, quality_issues
Gate condition: score < QUALITY_THRESHOLD (default: 6) → reject
```

### GeometryAgent

```
Model: gemini-2.5-flash
Tools:
  detect_corners(image_uri)
    → { corners: [top_left, top_right, bottom_right, bottom_left] | null }
  apply_perspective_correction(image_uri, corners)
    → corrected image bytes (Pillow homography transform)
  upload_to_gcs(image_bytes, path)
    → gcs_uri  (path: {date}/{session_id}/corrected.jpg)

Output key: corrected_image_uri
Soft gate: corners == null → skip correction, pass original_image_uri through
```

### PackagingAgent

```
Model: gemini-2.5-flash
Tools:
  build_azure_payload(corrected_image_uri, receipt_type, store_category, session_id)
    → { imageUrl, storeCategory, preprocessMeta: { sessionId, qualityScore, corrected: bool } }
    Note: corrected_image_uri falls back to original_image_uri when GeometryAgent skips correction

Output key: azure_payload
```

---

## Session State Keys

| 키                    | 설정 주체               | 소비 주체                                |
| --------------------- | ----------------------- | ---------------------------------------- |
| `session_id`          | `before_agent_callback` | GCS 경로, PackagingAgent                 |
| `original_image_uri`  | 입력                    | ValidityGate, QualityGate, GeometryAgent |
| `receipt_type`        | ValidityGateAgent       | PackagingAgent                           |
| `store_category`      | ValidityGateAgent       | PackagingAgent                           |
| `quality_score`       | QualityGateAgent        | 로깅                                     |
| `quality_issues`      | QualityGateAgent        | 로깅                                     |
| `corrected_image_uri` | GeometryAgent           | PackagingAgent                           |
| `rejection_code`      | `reject_with_code()`    | 앱 응답                                  |
| `azure_payload`       | PackagingAgent          | 앱 (Azure 전달)                          |

---

## Directory Structure

```plaintext
receipt-preprocessor/
├── receipt_preprocessor/
│   ├── __init__.py
│   ├── agent.py                    ← root_agent (SequentialAgent)
│   ├── config.py                   ← 환경변수 타입 정의
│   ├── policy.json                 ← 허용 유통 카테고리, 국가 코드 키워드
│   ├── .env.sample
│   └── sub_agents/
│       ├── validity/
│       │   ├── validity_agent.py
│       │   ├── prompt.py
│       │   └── tools/
│       │       ├── classify_receipt_tool.py
│       │       └── reject_tool.py
│       ├── quality/
│       │   ├── quality_agent.py
│       │   ├── prompt.py
│       │   └── tools/
│       │       ├── score_quality_tool.py
│       │       └── reject_tool.py
│       ├── geometry/
│       │   ├── geometry_agent.py
│       │   ├── prompt.py
│       │   └── tools/
│       │       ├── detect_corners_tool.py
│       │       ├── correct_perspective_tool.py
│       │       └── upload_to_gcs_tool.py
│       └── packaging/
│           ├── packaging_agent.py
│           ├── prompt.py
│           └── tools/
│               └── build_payload_tool.py
├── receipt_preprocessor_a2a_server/
│   └── remote_a2a/receipt_preprocessor/
│       └── agent.json
├── deploy/
│   └── deploy.py
├── test_client/
│   └── remote_test.py
└── pyproject.toml
```

---

## Configuration (`.env.sample`)

| 변수                    | 기본값             | 설명                       |
| ----------------------- | ------------------ | -------------------------- |
| `GOOGLE_CLOUD_PROJECT`  | —                  | GCP 프로젝트 ID            |
| `GOOGLE_CLOUD_LOCATION` | `us-central1`      | Vertex AI 리전             |
| `GCS_BUCKET_NAME`       | —                  | 보정 이미지 임시 저장 버킷 |
| `QUALITY_THRESHOLD`     | `6`                | 품질 점수 최솟값 (0–10)    |
| `GENAI_MODEL`           | `gemini-2.5-flash` | 전 에이전트 공통 모델      |
| `GCS_IMAGE_TTL_DAYS`    | `7`                | GCS 임시 이미지 보존 기간  |

---

## Exposure (A2A Protocol)

기존 `image_scoring_adk_a2a_server` 패턴을 재사용한다.

```json
{
  "name": "receipt_preprocessor",
  "description": "Pre-processes receipt images before Azure OCR: validates retail category, scores quality, corrects perspective.",
  "defaultInputModes": ["image/jpeg", "image/png", "image/heic"],
  "defaultOutputModes": ["application/json"],
  "capabilities": { "streaming": false }
}
```

React Native 앱은 `multipart/form-data`로 이미지를 전송하고 JSON 응답을 수신한다.

```typescript
// 앱 측 응답 타입
type PreprocessMeta = {
  sessionId: string;
  qualityScore: number;
  corrected: boolean; // true = perspective correction applied, false = original passed through
};

type PreprocessResult =
  | {
      status: "PASS";
      correctedImageUrl: string;
      storeCategory: string;
      preprocessMeta: PreprocessMeta;
    }
  | { status: "REJECT"; code: RejectionCode; userMessage: string };
```

---

## Mobile Layer Integration

기존 `azureUploadReceiptBatch()`를 교체하지 않고 앞에 체이닝한다.

```typescript
async function preprocessAndUpload(images: ImageInput[]) {
  // 1. 모바일 게이트 (기존 로직 재사용: fingerprint, refund regex, format check)
  const mobileResult = runMobilePreFlight(images);
  if (mobileResult.rejected) return { code: mobileResult.code };

  // 2. 클라우드 에이전트 (신규)
  const preprocess = await callReceiptPreprocessorAgent(images);
  if (preprocess.status === "REJECT") return preprocess;

  // 3. 기존 Azure 업로드 (변경 없음)
  return azureUploadReceiptBatch({
    ...images,
    imageUri: preprocess.correctedImageUrl,
    metadata: { ...existingMeta, storeCategory: preprocess.storeCategory },
  });
}
```

모바일 pre-flight 함수(`runMobilePreFlight`)는 `receipt-scraper`의 `receiptValidation.ts`에 있는 fingerprint·환불 감지 로직을 그대로 이식한다.

---

## Testing Strategy

| 레벨          | 방법                                                                |
| ------------- | ------------------------------------------------------------------- |
| 단위          | 각 tool 함수 `pytest` 독립 테스트 (Gemini 응답 mock 사용)           |
| 에이전트 통합 | `adk run receipt_preprocessor`로 실제 이미지 입력 후 세션 상태 검증 |
| 엔드투엔드    | `test_client/remote_test.py`로 A2A 서버에 거절 케이스별 이미지 전송 |
| 모바일 연동   | Staging 환경에서 앱 → 에이전트 → Azure 전체 체인 수동 검증          |

**테스트 픽스처 이미지 카테고리:**

- 정상 마트 영수증 (기준 케이스)
- 기울어진 영수증 (GeometryAgent 검증)
- 흐린 영수증 (QualityGateAgent 검증)
- 해외 영수증 (ValidityGateAgent → OVERSEAS_RECEIPT)
- 비영수증 이미지 — 명함, 메뉴판 (ValidityGateAgent → NON_RECEIPT)
- 환불 영수증 (모바일 pre-flight 검증)
