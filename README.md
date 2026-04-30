# receipt_preprocessor

A **SequentialAgent** pipeline built with [Google ADK](https://google.github.io/adk-docs/) that pre-processes receipt images before they reach the Youngkeul Azure OCR backend.

## How it works

```plaintext
receipt_preprocessor  (SequentialAgent)
│
├── before_agent_callback: set_session()
│   └── injects session_id and UTC timestamp
│
├── ValidityGateAgent           [hard gate]
│   └── classify_receipt()      → DOMESTIC_RETAIL / OVERSEAS / NON_RETAIL / NON_RECEIPT
│       rejects unless DOMESTIC_RETAIL
│
├── QualityGateAgent            [hard gate]
│   └── score_image_quality()   → score 0–10, issues list
│       rejects when score < QUALITY_THRESHOLD (default 6)
│
├── GeometryAgent               [soft gate]
│   ├── detect_corners()        → 4 corner pixel coordinates
│   └── correct_and_upload()    → perspective-corrected JPEG in GCS
│       on failure: passes original image through (GEOMETRY_FAILED, logged only)
│
└── PackagingAgent
    └── build_azure_payload()   → PASS JSON with corrected URI + metadata
```

### End-to-end flow

```plaintext
[React Native app]
      │  image selected from camera/gallery
      ▼
[Mobile Pre-flight]  file type · file size · refund regex · fingerprint dedup
      │
      ▼
[receipt_preprocessor]  (this agent)
      │
      ▼
[Azure OCR: v1/receipts/validate]
```

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Google Cloud project with these APIs enabled:
  - Vertex AI API
  - Cloud Storage API
- `gcloud` CLI authenticated: `gcloud auth application-default login`

## Setup

```bash
uv sync
source .venv/bin/activate
cp receipt_preprocessor/.env.sample receipt_preprocessor/.env
```

Edit `receipt_preprocessor/.env`:

```bash
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_BUCKET_NAME=your-gcp-project-id-receipt-preprocessor-bucket
QUALITY_THRESHOLD=6
GENAI_MODEL=gemini-2.5-flash
GCS_IMAGE_TTL_DAYS=7
```

Create the GCS bucket if it does not already exist:

```bash
gcloud storage buckets create gs://$(gcloud config get-value project)-receipt-preprocessor-bucket \
  --location=us-central1
```

## Running locally

```bash
# Interactive CLI session
adk run receipt_preprocessor

# Web UI (http://localhost:8000)
adk web
```

Send the GCS URI of a receipt image to start the pipeline:

```plaintext
gs://your-bucket/receipts/img001.jpg
```

## Running in Cloud Shell Editor

[Cloud Shell Editor](https://ide.cloud.google.com/) is the quickest way to run this project without
any local setup. ADC (Application Default Credentials) is pre-configured for your GCP account, so
`GOOGLE_GENAI_USE_VERTEXAI=1` is all that is needed — no API key management required.

### 1. Open Cloud Shell Editor

Go to `https://ide.cloud.google.com/` and open a terminal via **Terminal > New Terminal**.

### 2. Configure your project

```bash
gcloud auth list                        # verify the active account
gcloud config set project <YOUR_PROJECT_ID>

# Enable required APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
```

### 3. Install dependencies

```bash
pip install uv
uv sync
source .venv/bin/activate
```

### 4. Create `.env`

In Cloud Shell, `$(gcloud ...)` expressions are evaluated by bash, so you can use this shortcut:

```bash
PROJECT_ID=$(gcloud config get-value project)

cat > receipt_preprocessor/.env <<EOF
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=us-central1
GCS_BUCKET_NAME=${PROJECT_ID}-receipt-preprocessor-bucket
QUALITY_THRESHOLD=6
GENAI_MODEL=gemini-2.5-flash
GCS_IMAGE_TTL_DAYS=7
EOF
```

### 5. Create the GCS bucket and grant access

```bash
gcloud storage buckets create gs://${PROJECT_ID}-receipt-preprocessor-bucket \
  --location=us-central1

# Grant the Vertex AI service account write access to the bucket
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
SA_EMAIL="service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"
gcloud beta services identity create \
  --service=aiplatform.googleapis.com --project=${PROJECT_NUMBER}
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectUser" \
  --condition=None
```

### 6. Run

```bash
adk web    # Cloud Shell automatically proxies the port — click the URL it prints
```

## Agent output

### PASS

```json
{
  "status": "PASS",
  "correctedImageUrl": "gs://bucket/20260430/session-id/corrected.jpg",
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

## Rejection codes

| Code               | Layer | Meaning                                                          |
| ------------------ | ----- | ---------------------------------------------------------------- |
| `NON_RECEIPT`      | Cloud | Image is not a receipt                                           |
| `OVERSEAS_RECEIPT` | Cloud | Receipt is not domestic                                          |
| `NON_RETAIL`       | Cloud | Receipt is not from supported retail                             |
| `QUALITY_LOW`      | Cloud | Image quality is below threshold                                 |
| `GEOMETRY_FAILED`  | Cloud | Perspective correction failed (soft — logged only, not returned) |

## Configuration reference (`receipt_preprocessor/.env`)

| Variable                | Default            | Required | Purpose                                       |
| ----------------------- | ------------------ | :------: | --------------------------------------------- |
| `GOOGLE_CLOUD_PROJECT`  | —                  |    ✓     | GCP project for Vertex AI and GCS             |
| `GOOGLE_CLOUD_LOCATION` | `us-central1`      |          | Vertex AI region                              |
| `GCS_BUCKET_NAME`       | —                  |    ✓     | Temporary bucket for corrected receipt images |
| `QUALITY_THRESHOLD`     | `6`                |          | Minimum acceptable quality score (0–10)       |
| `GENAI_MODEL`           | `gemini-2.5-flash` |          | Gemini model used by all vision tools         |
| `GCS_IMAGE_TTL_DAYS`    | `7`                |          | Retention period for temporary GCS images     |

## Tests

```bash
pytest
```

22 unit tests cover all tools, config validation, and the geometry soft-gate fallback.

## Deploying to Vertex AI Agent Engine

```bash
# 1. Build the wheel
uv build

# 2. Deploy (reads receipt_preprocessor/.env for project/bucket config)
python deploy/deploy.py
```

The script prints the Vertex AI resource name on success.

## A2A server (Agent-to-Agent protocol)

```bash
# Start the A2A server
adk api_server receipt_preprocessor_a2a_server --port 8001

# Run the test client against the live server
python test_client/remote_test.py
```

Agent card: `http://localhost:8001/a2a/receipt_preprocessor/.well-known/agent.json`

Supported I/O: `image/jpeg`, `image/png`, `image/heic` → `application/json` (non-streaming).

## Resources

- [Codelab: Create multi-agents with ADK and A2A](https://codelabs.developers.google.com/codelabs/create-multi-agents-adk-a2a?hl=ko#7)
- [Google ADK documentation](https://google.github.io/adk-docs/)
- [A2A Protocol specification](https://a2a-protocol.org/latest/)
