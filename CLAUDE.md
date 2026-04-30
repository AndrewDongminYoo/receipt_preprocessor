# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Summary

This repository implements a **Receipt Preprocessor Agent** for Youngkeul receipt uploads.

The agent runs before the existing Azure OCR backend (`v1/receipts/validate`) and performs:

1. receipt validity classification
2. image quality scoring
3. perspective correction
4. Azure-compatible payload packaging

The existing Azure OCR backend must remain unchanged. This repository only adds a pre-processing layer in front of it.

## Common Commands

### Setup

```bash
uv sync
source .venv/bin/activate
cp receipt_preprocessor/.env.sample receipt_preprocessor/.env   # then fill in required values
```

### Run locally (Google ADK)

```bash
adk run receipt_preprocessor   # CLI session against the root SequentialAgent
adk web                        # web UI for interactive testing
```

### Deploy to Vertex AI

```bash
python deploy/deploy.py   # uploads wheel + requirements.txt, prints resource name
```

### Test remote A2A agent

```bash
python test_client/remote_test.py
```

### Run tests

```bash
pytest
```

## Architecture

The system is a **SequentialAgent** that validates and prepares receipt images before they are sent to Azure OCR.

```plaintext
receipt_preprocessor (SequentialAgent)
│
├── before_agent_callback: set_session()
│   └── resets pipeline state and injects session_id + timestamp
│
├── ValidityGateAgent
│   ├── classify_receipt(image_uri)
│   └── rejects unless receipt type is DOMESTIC_RETAIL
│
├── QualityGateAgent
│   ├── score_image_quality(image_uri)
│   └── rejects when quality_score < QUALITY_THRESHOLD
│
├── GeometryAgent
│   ├── detect_corners(image_uri)
│   ├── apply_perspective_correction(image_uri, corners)
│   └── upload_to_gcs(image_bytes, path)
│
└── PackagingAgent
    └── build_azure_payload(...)
```

### Processing Flow

```plaintext
[React Native app]
       │
       │ image selected from camera/gallery
       ▼
[Mobile Pre-flight Layer]
       │
       ├── file type / file size validation
       ├── refund receipt regex detection
       └── fingerprint duplicate detection
       │
       ▼
[Cloud Receipt Preprocessor Agent]
       │
       ├── ValidityGateAgent
       ├── QualityGateAgent
       ├── GeometryAgent
       └── PackagingAgent
       │
       ▼
[Azure OCR: v1/receipts/validate]
```

## Rejection Codes

| Code               | Layer  | Meaning                                 |
| ------------------ | ------ | --------------------------------------- |
| `FILE_INVALID`     | Mobile | Unsupported file type or invalid size   |
| `DUPLICATE`        | Mobile | Duplicate receipt upload                |
| `REFUND_RECEIPT`   | Mobile | Refund or return receipt                |
| `NON_RECEIPT`      | Cloud  | Image is not a receipt                  |
| `OVERSEAS_RECEIPT` | Cloud  | Receipt is not domestic                 |
| `NON_RETAIL`       | Cloud  | Receipt is not from supported retail    |
| `QUALITY_LOW`      | Cloud  | Image quality is below threshold        |
| `GEOMETRY_FAILED`  | Cloud  | Perspective correction failed; log only |

`GEOMETRY_FAILED` is a soft failure. The agent should pass the original image through instead of rejecting the request.

## Session State Keys

| Key                   | Set by                 | Consumed by                      |
| --------------------- | ---------------------- | -------------------------------- |
| `session_id`          | `set_session` callback | GCS path, PackagingAgent         |
| `timestamp`           | `set_session` callback | logging                          |
| `original_image_uri`  | ValidityGateAgent      | QualityGate, GeometryAgent       |
| `receipt_type`        | ValidityGateAgent      | PackagingAgent                   |
| `store_category`      | ValidityGateAgent      | PackagingAgent                   |
| `quality_score`       | QualityGateAgent       | logging, PackagingAgent          |
| `quality_issues`      | QualityGateAgent       | logging                          |
| `corrected_image_uri` | GeometryAgent          | PackagingAgent                   |
| `geometry_corrected`  | GeometryAgent          | PackagingAgent                   |
| `rejection_code`      | `reject_with_code()`   | `skip_if_rejected`, app response |
| `rejection_message`   | `reject_with_code()`   | app response                     |
| `azure_payload`       | PackagingAgent         | app / Azure upload chain         |

## Configuration (`receipt_preprocessor/.env`)

| Variable                | Default            | Purpose                                       |
| ----------------------- | ------------------ | --------------------------------------------- |
| `GOOGLE_CLOUD_PROJECT`  | —                  | GCP project for Vertex AI and GCS             |
| `GOOGLE_CLOUD_LOCATION` | `us-central1`      | Vertex AI location                            |
| `GCS_BUCKET_NAME`       | —                  | Temporary bucket for corrected receipt images |
| `QUALITY_THRESHOLD`     | `6`                | Minimum acceptable quality score, 0–10        |
| `GENAI_MODEL`           | `gemini-2.5-flash` | Common Gemini model for all agents            |
| `GCS_IMAGE_TTL_DAYS`    | `7`                | Retention period for temporary GCS images     |

## Key Files

| Path                                                                         | Role                                                                              |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `receipt_preprocessor/agent.py`                                              | Root `SequentialAgent` definition and session callback                            |
| `receipt_preprocessor/config.py`                                             | Typed config loaded from env vars                                                 |
| `receipt_preprocessor/policy.json`                                           | Retail category and country keyword policy                                        |
| `receipt_preprocessor/.env.sample`                                           | Example environment variables                                                     |
| `receipt_preprocessor/sub_agents/validity/validity_agent.py`                 | Receipt validity classification agent                                             |
| `receipt_preprocessor/sub_agents/validity/prompt.py`                         | Prompt for receipt validity classification                                        |
| `receipt_preprocessor/sub_agents/validity/tools/classify_receipt_tool.py`    | Classifies receipt image as domestic retail, overseas, non-retail, or non-receipt |
| `receipt_preprocessor/sub_agents/validity/tools/reject_tool.py`              | Records rejection code and escalates                                              |
| `receipt_preprocessor/sub_agents/quality/quality_agent.py`                   | Image quality scoring agent                                                       |
| `receipt_preprocessor/sub_agents/quality/prompt.py`                          | Prompt for quality evaluation                                                     |
| `receipt_preprocessor/sub_agents/quality/tools/score_quality_tool.py`        | Scores blur, exposure, occlusion, and resolution issues                           |
| `receipt_preprocessor/sub_agents/quality/tools/reject_tool.py`               | Records quality rejection and escalates                                           |
| `receipt_preprocessor/sub_agents/geometry/geometry_agent.py`                 | Perspective correction agent                                                      |
| `receipt_preprocessor/sub_agents/geometry/prompt.py`                         | Prompt for receipt corner detection and correction decisions                      |
| `receipt_preprocessor/sub_agents/geometry/tools/detect_corners_tool.py`      | Detects receipt corner coordinates                                                |
| `receipt_preprocessor/sub_agents/geometry/tools/correct_perspective_tool.py` | Applies perspective correction using Pillow homography transform                  |
| `receipt_preprocessor/sub_agents/geometry/tools/upload_to_gcs_tool.py`       | Uploads corrected image to GCS                                                    |
| `receipt_preprocessor/sub_agents/packaging/packaging_agent.py`               | Builds Azure-compatible output payload                                            |
| `receipt_preprocessor/sub_agents/packaging/prompt.py`                        | Prompt for final payload packaging                                                |
| `receipt_preprocessor/sub_agents/packaging/tools/build_payload_tool.py`      | Builds final PASS response payload                                                |
| `receipt_preprocessor_a2a_server/remote_a2a/receipt_preprocessor/agent.json` | A2A protocol agent card                                                           |
| `deploy/deploy.py`                                                           | Vertex AI Agent Engine deployment script                                          |
| `test_client/remote_test.py`                                                 | Remote A2A test client                                                            |

## Expected Agent Output

The agent should return one of the following JSON-compatible results.

### PASS

```json
{
  "status": "PASS",
  "correctedImageUrl": "gs://bucket/path/to/corrected.jpg",
  "storeCategory": "MART",
  "preprocessMeta": {
    "sessionId": "generated-session-id",
    "qualityScore": 8,
    "corrected": true
  }
}
```

### REJECT

```json
{
  "status": "REJECT",
  "code": "QUALITY_LOW",
  "userMessage": "영수증 사진이 흐리거나 어두워 인식하기 어렵습니다. 다시 촬영해 주세요."
}
```

## Agent Behavior Rules

### ValidityGateAgent

- Classify the image into exactly one receipt type:
  - `DOMESTIC_RETAIL`
  - `OVERSEAS`
  - `NON_RETAIL`
  - `NON_RECEIPT`

- Only `DOMESTIC_RETAIL` may continue.
- Map non-passing classifications to rejection codes:
  - `OVERSEAS` → `OVERSEAS_RECEIPT`
  - `NON_RETAIL` → `NON_RETAIL`
  - `NON_RECEIPT` → `NON_RECEIPT`

- Store `receipt_type` and `store_category` in session state.

### QualityGateAgent

- Score image quality from `0` to `10`.
- Detect quality issues from:
  - `blur`
  - `overexposed`
  - `underexposed`
  - `occluded`
  - `low_res`

- Reject with `QUALITY_LOW` when `quality_score < QUALITY_THRESHOLD`.
- Store `quality_score` and `quality_issues` in session state.

### GeometryAgent

- Detect receipt corners in this order:
  - top-left
  - top-right
  - bottom-right
  - bottom-left

- If corners are detected, apply perspective correction and upload the corrected image to GCS.
- If corners are not detected, do not reject. Set `corrected_image_uri` to `original_image_uri` or let PackagingAgent fall back to the original.
- Log geometry failure as `GEOMETRY_FAILED`, but treat it as a soft failure.

### PackagingAgent

- Build the final Azure-compatible payload.
- Use `corrected_image_uri` when present.
- Fall back to `original_image_uri` when perspective correction was skipped.
- Include:
  - image URL
  - store category
  - session ID
  - quality score
  - whether correction was applied

## A2A Exposure

The A2A agent card should expose this agent as a non-streaming JSON-returning image preprocessor.

```json
{
  "name": "receipt_preprocessor",
  "description": "Pre-processes receipt images before Azure OCR: validates retail category, scores quality, corrects perspective.",
  "defaultInputModes": ["image/jpeg", "image/png", "image/heic"],
  "defaultOutputModes": ["application/json"],
  "capabilities": {
    "streaming": false
  }
}
```

## Testing Strategy

Use the smallest test level that can verify the behavior.

| Level              | Method                                                           |
| ------------------ | ---------------------------------------------------------------- |
| Unit               | Test each tool with `pytest`; mock Gemini responses where needed |
| Agent integration  | Run `adk run receipt_preprocessor` with real fixture images      |
| End-to-end         | Send fixture images through `test_client/remote_test.py`         |
| Mobile integration | Manually verify app → preprocessor → Azure flow in staging       |

### Required Fixture Categories

- valid domestic mart receipt
- skewed receipt
- blurry receipt
- overseas receipt
- non-receipt image such as business card or menu
- refund receipt

## Development Guidelines

- Keep Azure OCR integration unchanged.
- Do not move mobile pre-flight rules into the cloud agent unless explicitly requested.
- Do not reject when only geometry correction fails.
- Prefer deterministic tool code over prompt-only behavior where possible.
- Keep prompts narrow and schema-oriented.
- Keep rejection responses stable because the React Native app depends on the code values.
- Add tests around every rejection code before changing gate behavior.
- Avoid over-engineering the first version. Ship the baseline pipeline first:
  1. validity gate
  2. quality gate
  3. geometry soft correction
  4. payload packaging
