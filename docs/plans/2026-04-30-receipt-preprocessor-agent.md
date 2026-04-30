# Receipt Preprocessor Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Google ADK SequentialAgent that pre-processes receipt images (validity gate → quality gate → perspective correction → packaging) before they are sent to Azure OCR.

**Architecture:** Four ADK `Agent` sub-agents wired into a `SequentialAgent`. Each gate agent owns tools that call Gemini Vision internally; the root agent's `before_agent_callback` injects a `session_id`. A shared `reject_tool.py` sets `tool_context.actions.escalate = True` to short-circuit the pipeline on failure. The system is exposed via ADK's A2A protocol server.

**Tech Stack:** Python 3.10+, google-adk 1.19.0, google-genai, google-cloud-storage, opencv-python-headless, numpy, Pillow, pytest

**Spec:** `docs/specs/2026-04-30-receipt-preprocessor-agent-design.md`

> **Note:** All paths are relative to a **new repository** forked from `multiagent-handson`. The fork root becomes the project root (`receipt-preprocessor/`).
>
> **Spec deviation:** The spec shows a separate `upload_to_gcs_tool.py` in `geometry/tools/`. This plan merges that functionality into `correct_perspective_tool.py` (which imports `upload_to_gcs` from the shared `gcs_utils.py`). The behavior is identical.

---

## File Map

```
receipt_preprocessor/
├── __init__.py
├── agent.py                                  Task 7
├── config.py                                 Task 1
├── policy.json                               Task 1
├── .env.sample                               Task 1
├── tools/
│   ├── __init__.py                           Task 1
│   ├── gcs_utils.py                          Task 2
│   └── reject_tool.py                        Task 2
└── sub_agents/
    ├── __init__.py                           Task 1
    ├── validity/
    │   ├── __init__.py                       Task 1
    │   ├── prompt.py                         Task 3
    │   ├── validity_agent.py                 Task 3
    │   └── tools/
    │       ├── __init__.py                   Task 1
    │       └── classify_receipt_tool.py      Task 3
    ├── quality/
    │   ├── __init__.py                       Task 1
    │   ├── prompt.py                         Task 4
    │   ├── quality_agent.py                  Task 4
    │   └── tools/
    │       ├── __init__.py                   Task 1
    │       └── score_quality_tool.py         Task 4
    ├── geometry/
    │   ├── __init__.py                       Task 1
    │   ├── prompt.py                         Task 5
    │   ├── geometry_agent.py                 Task 5
    │   └── tools/
    │       ├── __init__.py                   Task 1
    │       ├── detect_corners_tool.py        Task 5
    │       └── correct_perspective_tool.py   Task 5
    └── packaging/
        ├── __init__.py                       Task 1
        ├── prompt.py                         Task 6
        ├── packaging_agent.py                Task 6
        └── tools/
            ├── __init__.py                   Task 1
            └── build_payload_tool.py         Task 6

receipt_preprocessor_a2a_server/
├── __init__.py                               Task 8
├── a2a_agent.py                              Task 8
└── remote_a2a/receipt_preprocessor/
    └── agent.json                            Task 8

deploy/deploy.py                              Task 8
testclient/remote_test.py                     Task 8
tests/
├── __init__.py                               Task 1
├── test_shared_tools.py                      Task 2
├── test_classify_receipt_tool.py             Task 3
├── test_score_quality_tool.py                Task 4
├── test_geometry_tools.py                    Task 5
└── test_build_payload_tool.py                Task 6
pyproject.toml                                Task 1
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `receipt_preprocessor/config.py`
- Create: `receipt_preprocessor/policy.json`
- Create: `receipt_preprocessor/.env.sample`
- Create: all `__init__.py` files (empty) listed in File Map above
- Create: `tests/__init__.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "receipt-preprocessor"
version = "0.1.0"
description = "Pre-processes receipt images before Azure OCR: validates retail category, scores quality, corrects perspective."
license = "Apache License 2.0"
readme = "README.md"
requires-python = ">=3.10"

[tool.poetry]
packages = [{ include = "receipt_preprocessor" }]
include = ["receipt_preprocessor/.env"]

[tool.poetry.dependencies]
python = ">=3.10"
google-adk = { version = "==1.19.0", extras = ["eval"] }
a2a-sdk = "^0.2.16"
google-cloud-aiplatform = { extras = ["adk", "agent-engines"], version = "^1.128.0" }
google-cloud-storage = "^2.18.0"
google-genai = "^1.52.0"
pydantic = "^2.10.6"
python-dotenv = "^1.0.1"
opencv-python-headless = "^4.9.0"
numpy = "^1.26.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.5"
pytest-asyncio = "^0.26.0"

[tool.poetry.group.deployment.dependencies]
absl-py = "^2.2.1"

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
```

- [ ] **Step 2: Create `receipt_preprocessor/config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

GCS_BUCKET_NAME: str = os.environ.get("GCS_BUCKET_NAME", "")
QUALITY_THRESHOLD: int = int(os.getenv("QUALITY_THRESHOLD", "6"))
GENAI_MODEL: str = os.getenv("GENAI_MODEL", "gemini-2.5-flash")
GCS_IMAGE_TTL_DAYS: int = int(os.getenv("GCS_IMAGE_TTL_DAYS", "7"))
```

- [ ] **Step 3: Create `receipt_preprocessor/policy.json`**

```json
{
  "allowed_store_categories": ["MART", "CONVENIENCE", "SUPERMARKET"],
  "retail_keywords_ko": [
    "이마트", "홈플러스", "롯데마트", "코스트코", "메가마트", "킴스클럽",
    "GS25", "CU", "세븐일레븐", "미니스톱", "이마트24",
    "편의점", "수퍼마켓", "슈퍼마켓", "마트", "할인점"
  ],
  "overseas_indicators": [
    "USD", "EUR", "JPY", "CNY", "GBP", "AUD", "CAD",
    "SUBTOTAL", "CHANGE DUE", "AMOUNT DUE", "RECEIPT NO",
    "STORE NO", "GST", "TOTAL TAX"
  ],
  "non_receipt_indicators": [
    "business card", "menu", "invoice", "contract",
    "license", "passport", "id card", "certificate"
  ]
}
```

- [ ] **Step 4: Create `receipt_preprocessor/.env.sample`**

```bash
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
GOOGLE_CLOUD_LOCATION=us-central1
GCS_BUCKET_NAME=$(gcloud config get-value project)-receiptpreprocessor-bucket
QUALITY_THRESHOLD=6
GENAI_MODEL=gemini-2.5-flash
GCS_IMAGE_TTL_DAYS=7
```

- [ ] **Step 5: Create all empty `__init__.py` files**

```bash
touch receipt_preprocessor/__init__.py
touch receipt_preprocessor/tools/__init__.py
touch receipt_preprocessor/sub_agents/__init__.py
touch receipt_preprocessor/sub_agents/validity/__init__.py
touch receipt_preprocessor/sub_agents/validity/tools/__init__.py
touch receipt_preprocessor/sub_agents/quality/__init__.py
touch receipt_preprocessor/sub_agents/quality/tools/__init__.py
touch receipt_preprocessor/sub_agents/geometry/__init__.py
touch receipt_preprocessor/sub_agents/geometry/tools/__init__.py
touch receipt_preprocessor/sub_agents/packaging/__init__.py
touch receipt_preprocessor/sub_agents/packaging/tools/__init__.py
touch receipt_preprocessor_a2a_server/__init__.py
mkdir -p receipt_preprocessor_a2a_server/remote_a2a/receipt_preprocessor
touch tests/__init__.py
```

- [ ] **Step 6: Write the failing test**

`tests/test_config.py`:
```python
import os

def test_config_quality_threshold_default():
    os.environ.setdefault("GCS_BUCKET_NAME", "test-bucket")
    from receipt_preprocessor import config
    assert config.QUALITY_THRESHOLD == int(os.getenv("QUALITY_THRESHOLD", "6"))
    assert config.GENAI_MODEL == os.getenv("GENAI_MODEL", "gemini-2.5-flash")
    assert config.GCS_IMAGE_TTL_DAYS == 7
```

- [ ] **Step 7: Install dependencies and run test**

```bash
uv sync
source .venv/bin/activate
pytest tests/test_config.py -v
```

Expected: `PASSED`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml receipt_preprocessor/ tests/__init__.py tests/test_config.py
git commit -m "feat: scaffold receipt-preprocessor project"
```

---

## Task 2: Shared Infrastructure (GCS Utils + Reject Tool)

**Files:**
- Create: `receipt_preprocessor/tools/gcs_utils.py`
- Create: `receipt_preprocessor/tools/reject_tool.py`
- Test: `tests/test_shared_tools.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_shared_tools.py`:
```python
from unittest.mock import patch, MagicMock


# --- reject_tool ---

def test_reject_with_code_sets_state_and_escalates():
    from receipt_preprocessor.tools.reject_tool import reject_with_code

    ctx = MagicMock()
    ctx.state = {}
    ctx.actions = MagicMock()

    result = reject_with_code("NON_RECEIPT", "영수증 이미지를 다시 촬영해 주세요.", ctx)

    assert result == {
        "rejected": True,
        "code": "NON_RECEIPT",
        "message": "영수증 이미지를 다시 촬영해 주세요.",
    }
    assert ctx.state["rejection_code"] == "NON_RECEIPT"
    assert ctx.state["rejection_message"] == "영수증 이미지를 다시 촬영해 주세요."
    assert ctx.actions.escalate is True


# --- gcs_utils ---

def test_download_from_gcs():
    from receipt_preprocessor.tools.gcs_utils import download_from_gcs

    with patch("receipt_preprocessor.tools.gcs_utils.storage.Client") as mock_cls:
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"image_data"
        mock_cls.return_value.bucket.return_value.blob.return_value = mock_blob

        result = download_from_gcs("gs://my-bucket/path/to/img.jpg")

    assert result == b"image_data"
    mock_cls.return_value.bucket.assert_called_with("my-bucket")
    mock_cls.return_value.bucket.return_value.blob.assert_called_with("path/to/img.jpg")


def test_upload_to_gcs():
    from receipt_preprocessor.tools.gcs_utils import upload_to_gcs

    with patch("receipt_preprocessor.tools.gcs_utils.storage.Client") as mock_cls:
        mock_blob = MagicMock()
        mock_cls.return_value.bucket.return_value.blob.return_value = mock_blob

        result = upload_to_gcs(b"image_data", "my-bucket", "20260430/abc/corrected.jpg")

    assert result == "gs://my-bucket/20260430/abc/corrected.jpg"
    mock_blob.upload_from_string.assert_called_once_with(
        b"image_data", content_type="image/jpeg"
    )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_shared_tools.py -v
```

Expected: `ImportError` (modules not created yet)

- [ ] **Step 3: Create `receipt_preprocessor/tools/reject_tool.py`**

```python
from google.adk.tools.tool_context import ToolContext


def reject_with_code(code: str, user_message: str, tool_context: ToolContext) -> dict:
    """Records rejection in session state and escalates to stop the pipeline."""
    tool_context.state["rejection_code"] = code
    tool_context.state["rejection_message"] = user_message
    tool_context.actions.escalate = True
    return {"rejected": True, "code": code, "message": user_message}
```

- [ ] **Step 4: Create `receipt_preprocessor/tools/gcs_utils.py`**

```python
from google.cloud import storage


def download_from_gcs(gcs_uri: str) -> bytes:
    """Downloads bytes from a GCS URI (gs://bucket/path)."""
    path = gcs_uri.replace("gs://", "")
    bucket_name, blob_path = path.split("/", 1)
    client = storage.Client()
    return client.bucket(bucket_name).blob(blob_path).download_as_bytes()


def upload_to_gcs(image_bytes: bytes, bucket_name: str, blob_path: str) -> str:
    """Uploads bytes to GCS and returns the gs:// URI."""
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(blob_path)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    return f"gs://{bucket_name}/{blob_path}"
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_shared_tools.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add receipt_preprocessor/tools/ tests/test_shared_tools.py
git commit -m "feat: add shared GCS utils and reject tool"
```

---

## Task 3: ValidityGateAgent

**Files:**
- Create: `receipt_preprocessor/sub_agents/validity/tools/classify_receipt_tool.py`
- Create: `receipt_preprocessor/sub_agents/validity/prompt.py`
- Create: `receipt_preprocessor/sub_agents/validity/validity_agent.py`
- Test: `tests/test_classify_receipt_tool.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_classify_receipt_tool.py`:
```python
from unittest.mock import patch, MagicMock


def test_classify_domestic_retail_sets_state():
    from receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool import (
        classify_receipt,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/receipt.jpg"}

    mock_response = MagicMock()
    mock_response.text = (
        '{"type": "DOMESTIC_RETAIL", "store_category": "MART",'
        ' "confidence": 0.95, "reason": "이마트 영수증"}'
    )

    with patch(
        "receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = classify_receipt(ctx)

    assert result["type"] == "DOMESTIC_RETAIL"
    assert result["store_category"] == "MART"
    assert ctx.state["receipt_type"] == "DOMESTIC_RETAIL"
    assert ctx.state["store_category"] == "MART"


def test_classify_returns_non_receipt_when_no_uri():
    from receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool import (
        classify_receipt,
    )

    ctx = MagicMock()
    ctx.state = {}
    result = classify_receipt(ctx)

    assert result["type"] == "NON_RECEIPT"
    assert result["confidence"] == 0.0


def test_classify_handles_markdown_wrapped_json():
    from receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool import (
        classify_receipt,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/receipt.jpg"}

    mock_response = MagicMock()
    mock_response.text = (
        "```json\n"
        '{"type": "OVERSEAS", "store_category": "OTHER",'
        ' "confidence": 0.8, "reason": "USD 표기"}\n'
        "```"
    )

    with patch(
        "receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = classify_receipt(ctx)

    assert result["type"] == "OVERSEAS"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_classify_receipt_tool.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `receipt_preprocessor/sub_agents/validity/tools/classify_receipt_tool.py`**

```python
import json
import os
import re

import google.genai as genai
from google.genai import types as genai_types
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(text)


def classify_receipt(tool_context: ToolContext) -> dict:
    """Classifies the receipt image as DOMESTIC_RETAIL, OVERSEAS, NON_RETAIL, or NON_RECEIPT.

    Reads original_image_uri from session state.
    Writes receipt_type and store_category to session state.
    """
    image_uri = tool_context.state.get("original_image_uri")
    if not image_uri:
        return {
            "type": "NON_RECEIPT",
            "store_category": "OTHER",
            "confidence": 0.0,
            "reason": "No image URI in session state",
        }

    policy_path = os.path.join(os.path.dirname(__file__), "../../../../policy.json")
    with open(policy_path) as f:
        policy = json.load(f)

    client = genai.Client()
    response = client.models.generate_content(
        model=config.GENAI_MODEL,
        contents=[
            genai_types.Part.from_uri(file_uri=image_uri, mime_type="image/jpeg"),
            f"""Classify this image as a receipt for the 영끌 Korean retail reward app.

Domestic retail keywords (DOMESTIC_RETAIL): {policy['retail_keywords_ko']}
Overseas indicators (OVERSEAS): {policy['overseas_indicators']}

Classify as:
- DOMESTIC_RETAIL: Korean mart, convenience store, or supermarket receipt
- OVERSEAS: Receipt with foreign currency or overseas store indicators
- NON_RETAIL: Korean receipt but not from mart/convenience/supermarket (restaurant, cafe, etc.)
- NON_RECEIPT: Not a receipt at all (photo, business card, menu, etc.)

Respond ONLY with valid JSON, no markdown:
{{
  "type": "DOMESTIC_RETAIL" | "OVERSEAS" | "NON_RETAIL" | "NON_RECEIPT",
  "store_category": "MART" | "CONVENIENCE" | "SUPERMARKET" | "OTHER",
  "confidence": 0.0-1.0,
  "reason": "brief explanation in Korean"
}}""",
        ],
    )

    result = _extract_json(response.text)
    tool_context.state["receipt_type"] = result["type"]
    tool_context.state["store_category"] = result["store_category"]
    return result
```

- [ ] **Step 4: Create `receipt_preprocessor/sub_agents/validity/prompt.py`**

```python
VALIDITY_PROMPT = """You are a receipt classification gate for the 영끌 app.

Steps:
1. Call classify_receipt() to analyze the image in session state.
2. Check the returned "type" field:
   - If "OVERSEAS": call reject_with_code("OVERSEAS_RECEIPT", "해외 영수증은 등록할 수 없습니다. 국내 영수증을 촬영해 주세요.")
   - If "NON_RETAIL": call reject_with_code("NON_RETAIL", "마트·편의점·수퍼마켓 영수증만 등록 가능합니다.")
   - If "NON_RECEIPT": call reject_with_code("NON_RECEIPT", "영수증 이미지를 인식할 수 없습니다. 영수증을 다시 촬영해 주세요.")
   - If "DOMESTIC_RETAIL": your task is complete. Do not call any other tool.

Always call classify_receipt() first before making any decision."""
```

- [ ] **Step 5: Create `receipt_preprocessor/sub_agents/validity/validity_agent.py`**

```python
from google.adk.agents import Agent

from receipt_preprocessor import config
from receipt_preprocessor.tools.reject_tool import reject_with_code

from .prompt import VALIDITY_PROMPT
from .tools.classify_receipt_tool import classify_receipt

validity_gate_agent = Agent(
    name="validity_gate_agent",
    model=config.GENAI_MODEL,
    description="Validates that the uploaded image is a domestic Korean retail receipt.",
    instruction=VALIDITY_PROMPT,
    tools=[classify_receipt, reject_with_code],
)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_classify_receipt_tool.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add receipt_preprocessor/sub_agents/validity/ tests/test_classify_receipt_tool.py
git commit -m "feat: add ValidityGateAgent with classify_receipt tool"
```

---

## Task 4: QualityGateAgent

**Files:**
- Create: `receipt_preprocessor/sub_agents/quality/tools/score_quality_tool.py`
- Create: `receipt_preprocessor/sub_agents/quality/prompt.py`
- Create: `receipt_preprocessor/sub_agents/quality/quality_agent.py`
- Test: `tests/test_score_quality_tool.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_score_quality_tool.py`:
```python
from unittest.mock import patch, MagicMock


def test_score_high_quality_sets_state():
    from receipt_preprocessor.sub_agents.quality.tools.score_quality_tool import (
        score_image_quality,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/clear.jpg"}

    mock_response = MagicMock()
    mock_response.text = '{"score": 8, "issues": [], "reason": "선명한 영수증"}'

    with patch(
        "receipt_preprocessor.sub_agents.quality.tools.score_quality_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = score_image_quality(ctx)

    assert result["score"] == 8
    assert result["issues"] == []
    assert ctx.state["quality_score"] == 8
    assert ctx.state["quality_issues"] == []


def test_score_blurry_image():
    from receipt_preprocessor.sub_agents.quality.tools.score_quality_tool import (
        score_image_quality,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/blurry.jpg"}

    mock_response = MagicMock()
    mock_response.text = (
        '{"score": 3, "issues": ["blur", "underexposed"], "reason": "흐릿하고 어두운 이미지"}'
    )

    with patch(
        "receipt_preprocessor.sub_agents.quality.tools.score_quality_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = score_image_quality(ctx)

    assert result["score"] == 3
    assert "blur" in result["issues"]
    assert ctx.state["quality_score"] == 3


def test_score_returns_zero_when_no_uri():
    from receipt_preprocessor.sub_agents.quality.tools.score_quality_tool import (
        score_image_quality,
    )

    ctx = MagicMock()
    ctx.state = {}
    result = score_image_quality(ctx)

    assert result["score"] == 0
    assert "no_image" in result["issues"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_score_quality_tool.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `receipt_preprocessor/sub_agents/quality/tools/score_quality_tool.py`**

```python
import json
import re

import google.genai as genai
from google.genai import types as genai_types
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(text)


def score_image_quality(tool_context: ToolContext) -> dict:
    """Scores the receipt image quality on a 0-10 scale.

    Reads original_image_uri from session state.
    Writes quality_score and quality_issues to session state.
    """
    image_uri = tool_context.state.get("original_image_uri")
    if not image_uri:
        result = {"score": 0, "issues": ["no_image"], "reason": "이미지 URI가 없습니다."}
        tool_context.state["quality_score"] = 0
        tool_context.state["quality_issues"] = ["no_image"]
        return result

    client = genai.Client()
    response = client.models.generate_content(
        model=config.GENAI_MODEL,
        contents=[
            genai_types.Part.from_uri(file_uri=image_uri, mime_type="image/jpeg"),
            """Evaluate this receipt image quality for OCR processing. Score 0-10 (10 = perfect).

Identify issues from this list only: "blur", "overexposed", "underexposed", "occluded", "low_res", "wrinkled"

Respond ONLY with valid JSON, no markdown:
{
  "score": 0-10,
  "issues": ["issue1"],
  "reason": "brief explanation in Korean"
}""",
        ],
    )

    result = _extract_json(response.text)
    tool_context.state["quality_score"] = result["score"]
    tool_context.state["quality_issues"] = result.get("issues", [])
    return result
```

- [ ] **Step 4: Create `receipt_preprocessor/sub_agents/quality/prompt.py`**

```python
from receipt_preprocessor import config

QUALITY_PROMPT = f"""You are a receipt image quality inspector for the 영끌 app.

Steps:
1. Call score_image_quality() to evaluate the image in session state.
2. Check the returned "score" field:
   - If score < {config.QUALITY_THRESHOLD}: build a specific user_message based on the "issues" field,
     then call reject_with_code("QUALITY_LOW", user_message).
     Examples:
       - "blur" → "영수증이 흐릿합니다. 카메라를 고정하고 다시 촬영해 주세요."
       - "overexposed" → "영수증이 너무 밝습니다. 빛을 피해 다시 촬영해 주세요."
       - "underexposed" → "영수증이 너무 어둡습니다. 밝은 곳에서 다시 촬영해 주세요."
       - multiple issues → "영수증 이미지 품질이 낮습니다. 선명하게 다시 촬영해 주세요."
   - If score >= {config.QUALITY_THRESHOLD}: your task is complete. Do not call any other tool.

Always call score_image_quality() first."""
```

- [ ] **Step 5: Create `receipt_preprocessor/sub_agents/quality/quality_agent.py`**

```python
from google.adk.agents import Agent

from receipt_preprocessor import config
from receipt_preprocessor.tools.reject_tool import reject_with_code

from .prompt import QUALITY_PROMPT
from .tools.score_quality_tool import score_image_quality

quality_gate_agent = Agent(
    name="quality_gate_agent",
    model=config.GENAI_MODEL,
    description="Scores receipt image quality and rejects images below the quality threshold.",
    instruction=QUALITY_PROMPT,
    tools=[score_image_quality, reject_with_code],
)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_score_quality_tool.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add receipt_preprocessor/sub_agents/quality/ tests/test_score_quality_tool.py
git commit -m "feat: add QualityGateAgent with score_image_quality tool"
```

---

## Task 5: GeometryAgent

**Files:**
- Create: `receipt_preprocessor/sub_agents/geometry/tools/detect_corners_tool.py`
- Create: `receipt_preprocessor/sub_agents/geometry/tools/correct_perspective_tool.py`
- Create: `receipt_preprocessor/sub_agents/geometry/prompt.py`
- Create: `receipt_preprocessor/sub_agents/geometry/geometry_agent.py`
- Test: `tests/test_geometry_tools.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_geometry_tools.py`:
```python
import io
from unittest.mock import patch, MagicMock

from PIL import Image


def _make_jpeg_bytes(width: int = 200, height: int = 300) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# --- detect_corners_tool ---

def test_detect_corners_returns_four_points():
    from receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool import (
        detect_corners,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/tilted.jpg"}

    mock_response = MagicMock()
    mock_response.text = (
        '{"corners": [[10, 10], [190, 5], [195, 295], [8, 290]]}'
    )

    with patch(
        "receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = detect_corners(ctx)

    assert result["corners"] is not None
    assert len(result["corners"]) == 4


def test_detect_corners_returns_null_when_undetermined():
    from receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool import (
        detect_corners,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/fullframe.jpg"}

    mock_response = MagicMock()
    mock_response.text = '{"corners": null}'

    with patch(
        "receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = detect_corners(ctx)

    assert result["corners"] is None


# --- correct_perspective_tool ---

def test_correct_and_upload_with_valid_corners():
    from receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool import (
        correct_and_upload,
    )

    ctx = MagicMock()
    ctx.state = {
        "original_image_uri": "gs://bucket/tilted.jpg",
        "session_id": "test-session-abc",
    }
    image_bytes = _make_jpeg_bytes()
    corners = [[10, 10], [190, 10], [190, 290], [10, 290]]

    with patch(
        "receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool.download_from_gcs",
        return_value=image_bytes,
    ):
        with patch(
            "receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool.upload_to_gcs",
            return_value="gs://bucket/20260430/test-session-abc/corrected.jpg",
        ):
            result = correct_and_upload(corners, ctx)

    assert result["corrected"] is True
    assert result["corrected_image_uri"] == "gs://bucket/20260430/test-session-abc/corrected.jpg"
    assert ctx.state["corrected_image_uri"] == "gs://bucket/20260430/test-session-abc/corrected.jpg"
    assert ctx.state["geometry_corrected"] is True


def test_correct_and_upload_passes_original_when_no_corners():
    from receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool import (
        correct_and_upload,
    )

    ctx = MagicMock()
    ctx.state = {
        "original_image_uri": "gs://bucket/fullframe.jpg",
        "session_id": "test-session-xyz",
    }

    result = correct_and_upload(None, ctx)

    assert result["corrected"] is False
    assert result["corrected_image_uri"] == "gs://bucket/fullframe.jpg"
    assert ctx.state["corrected_image_uri"] == "gs://bucket/fullframe.jpg"
    assert ctx.state["geometry_corrected"] is False


def test_apply_perspective_produces_valid_jpeg():
    from receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool import (
        _apply_perspective,
    )

    image_bytes = _make_jpeg_bytes(200, 300)
    corners = [[10, 10], [190, 10], [190, 290], [10, 290]]
    result = _apply_perspective(image_bytes, corners)

    assert isinstance(result, bytes)
    reopened = Image.open(io.BytesIO(result))
    assert reopened.format == "JPEG"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_geometry_tools.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `receipt_preprocessor/sub_agents/geometry/tools/detect_corners_tool.py`**

```python
import json
import re

import google.genai as genai
from google.genai import types as genai_types
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(text)


def detect_corners(tool_context: ToolContext) -> dict:
    """Detects the 4 corner coordinates of the receipt in the image.

    Reads original_image_uri from session state.
    Returns {"corners": [[x,y]×4]} or {"corners": null}.
    """
    image_uri = tool_context.state.get("original_image_uri")
    if not image_uri:
        return {"corners": None}

    client = genai.Client()
    response = client.models.generate_content(
        model=config.GENAI_MODEL,
        contents=[
            genai_types.Part.from_uri(file_uri=image_uri, mime_type="image/jpeg"),
            """Identify the 4 corner pixel coordinates of the receipt document in this image.

Coordinate origin (0,0) is at the top-left of the image.

Respond ONLY with valid JSON, no markdown:
{"corners": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]}
Order: top-left, top-right, bottom-right, bottom-left.

If the receipt fills the entire frame OR corners cannot be reliably determined, respond:
{"corners": null}""",
        ],
    )

    return _extract_json(response.text)
```

- [ ] **Step 4: Create `receipt_preprocessor/sub_agents/geometry/tools/correct_perspective_tool.py`**

```python
from datetime import date
from typing import Optional

import cv2
import numpy as np
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config
from receipt_preprocessor.tools.gcs_utils import download_from_gcs, upload_to_gcs


def _apply_perspective(image_bytes: bytes, corners: list) -> bytes:
    """Applies a 4-point perspective transform (TL, TR, BR, BL) using OpenCV."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")

    h, w = img.shape[:2]
    src = np.float32(corners)
    dst = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])

    M = cv2.getPerspectiveTransform(src, dst)
    corrected = cv2.warpPerspective(img, M, (w, h))

    success, buffer = cv2.imencode(".jpg", corrected, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        raise ValueError("Could not encode corrected image")
    return buffer.tobytes()


def correct_and_upload(corners: Optional[list], tool_context: ToolContext) -> dict:
    """Applies perspective correction and uploads the result to GCS.

    If corners is None, passes original_image_uri through without modification.
    Writes corrected_image_uri and geometry_corrected to session state.
    """
    image_uri = tool_context.state.get("original_image_uri")
    session_id = tool_context.state.get("session_id")

    if not corners:
        tool_context.state["corrected_image_uri"] = image_uri
        tool_context.state["geometry_corrected"] = False
        return {"corrected_image_uri": image_uri, "corrected": False}

    image_bytes = download_from_gcs(image_uri)
    corrected_bytes = _apply_perspective(image_bytes, corners)

    date_str = date.today().strftime("%Y%m%d")
    blob_path = f"{date_str}/{session_id}/corrected.jpg"
    corrected_uri = upload_to_gcs(corrected_bytes, config.GCS_BUCKET_NAME, blob_path)

    tool_context.state["corrected_image_uri"] = corrected_uri
    tool_context.state["geometry_corrected"] = True
    return {"corrected_image_uri": corrected_uri, "corrected": True}
```

- [ ] **Step 5: Create `receipt_preprocessor/sub_agents/geometry/prompt.py`**

```python
GEOMETRY_PROMPT = """You are a receipt image geometry correction specialist for the 영끌 app.

Steps:
1. Call detect_corners() to find the 4 corner coordinates of the receipt.
2. Call correct_and_upload() passing the detected corners (or null if detect_corners returned null).
3. Your task is complete when correct_and_upload() returns.

This step always succeeds — if no corners are found, the original image is preserved automatically."""
```

- [ ] **Step 6: Create `receipt_preprocessor/sub_agents/geometry/geometry_agent.py`**

```python
from google.adk.agents import Agent

from receipt_preprocessor import config

from .prompt import GEOMETRY_PROMPT
from .tools.correct_perspective_tool import correct_and_upload
from .tools.detect_corners_tool import detect_corners

geometry_agent = Agent(
    name="geometry_agent",
    model=config.GENAI_MODEL,
    description="Detects and corrects perspective distortion in receipt images.",
    instruction=GEOMETRY_PROMPT,
    tools=[detect_corners, correct_and_upload],
)
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_geometry_tools.py -v
```

Expected: `5 passed`

- [ ] **Step 8: Commit**

```bash
git add receipt_preprocessor/sub_agents/geometry/ tests/test_geometry_tools.py
git commit -m "feat: add GeometryAgent with perspective correction tools"
```

---

## Task 6: PackagingAgent

**Files:**
- Create: `receipt_preprocessor/sub_agents/packaging/tools/build_payload_tool.py`
- Create: `receipt_preprocessor/sub_agents/packaging/prompt.py`
- Create: `receipt_preprocessor/sub_agents/packaging/packaging_agent.py`
- Test: `tests/test_build_payload_tool.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_build_payload_tool.py`:
```python
from unittest.mock import MagicMock


def test_build_payload_with_corrected_image():
    from receipt_preprocessor.sub_agents.packaging.tools.build_payload_tool import (
        build_azure_payload,
    )

    ctx = MagicMock()
    ctx.state = {
        "corrected_image_uri": "gs://bucket/corrected.jpg",
        "original_image_uri": "gs://bucket/original.jpg",
        "store_category": "MART",
        "session_id": "session-001",
        "quality_score": 8,
        "geometry_corrected": True,
    }

    result = build_azure_payload(ctx)

    assert result["status"] == "PASS"
    assert result["correctedImageUrl"] == "gs://bucket/corrected.jpg"
    assert result["storeCategory"] == "MART"
    assert result["preprocessMeta"]["sessionId"] == "session-001"
    assert result["preprocessMeta"]["qualityScore"] == 8
    assert result["preprocessMeta"]["corrected"] is True
    assert ctx.state["azure_payload"] == result


def test_build_payload_falls_back_to_original_when_no_corrected_uri():
    from receipt_preprocessor.sub_agents.packaging.tools.build_payload_tool import (
        build_azure_payload,
    )

    ctx = MagicMock()
    ctx.state = {
        "corrected_image_uri": None,
        "original_image_uri": "gs://bucket/original.jpg",
        "store_category": "CONVENIENCE",
        "session_id": "session-002",
        "quality_score": 7,
        "geometry_corrected": False,
    }

    result = build_azure_payload(ctx)

    assert result["correctedImageUrl"] == "gs://bucket/original.jpg"
    assert result["preprocessMeta"]["corrected"] is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_build_payload_tool.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `receipt_preprocessor/sub_agents/packaging/tools/build_payload_tool.py`**

```python
from google.adk.tools.tool_context import ToolContext


def build_azure_payload(tool_context: ToolContext) -> dict:
    """Assembles the final payload to be sent to Azure OCR.

    Reads corrected_image_uri (falls back to original_image_uri), store_category,
    session_id, quality_score, and geometry_corrected from session state.
    Writes azure_payload to session state.
    """
    corrected_uri = tool_context.state.get("corrected_image_uri") or tool_context.state.get(
        "original_image_uri"
    )

    payload = {
        "status": "PASS",
        "correctedImageUrl": corrected_uri,
        "storeCategory": tool_context.state.get("store_category"),
        "preprocessMeta": {
            "sessionId": tool_context.state.get("session_id"),
            "qualityScore": tool_context.state.get("quality_score"),
            "corrected": bool(tool_context.state.get("geometry_corrected", False)),
        },
    }
    tool_context.state["azure_payload"] = payload
    return payload
```

- [ ] **Step 4: Create `receipt_preprocessor/sub_agents/packaging/prompt.py`**

```python
PACKAGING_PROMPT = """You are the final packaging step of the 영끌 receipt preprocessor pipeline.

Steps:
1. Call build_azure_payload() to assemble the final result.
2. Your task is complete when build_azure_payload() returns.

This is the last step. The returned payload will be sent to Azure OCR."""
```

- [ ] **Step 5: Create `receipt_preprocessor/sub_agents/packaging/packaging_agent.py`**

```python
from google.adk.agents import Agent

from receipt_preprocessor import config

from .prompt import PACKAGING_PROMPT
from .tools.build_payload_tool import build_azure_payload

packaging_agent = Agent(
    name="packaging_agent",
    model=config.GENAI_MODEL,
    description="Assembles the final preprocessed payload for Azure OCR.",
    instruction=PACKAGING_PROMPT,
    output_key="azure_payload",
    tools=[build_azure_payload],
)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_build_payload_tool.py -v
```

Expected: `2 passed`

- [ ] **Step 7: Run all unit tests**

```bash
pytest tests/ -v
```

Expected: `all passed` (13 tests total across Tasks 1–6)

- [ ] **Step 8: Commit**

```bash
git add receipt_preprocessor/sub_agents/packaging/ tests/test_build_payload_tool.py
git commit -m "feat: add PackagingAgent with build_azure_payload tool"
```

---

## Task 7: Root Agent

**Files:**
- Create: `receipt_preprocessor/agent.py`
- Modify: `receipt_preprocessor/sub_agents/__init__.py` (add exports)

- [ ] **Step 1: Create `receipt_preprocessor/agent.py`**

```python
import datetime
import uuid
from zoneinfo import ZoneInfo

from google.adk.agents import SequentialAgent
from google.adk.agents.callback_context import CallbackContext

from .sub_agents.geometry.geometry_agent import geometry_agent
from .sub_agents.packaging.packaging_agent import packaging_agent
from .sub_agents.quality.quality_agent import quality_gate_agent
from .sub_agents.validity.validity_agent import validity_gate_agent


def set_session(callback_context: CallbackContext) -> None:
    """Injects a unique session_id and UTC timestamp before the pipeline runs."""
    callback_context.state["session_id"] = str(uuid.uuid4())
    callback_context.state["timestamp"] = datetime.datetime.now(ZoneInfo("UTC")).isoformat()


receipt_preprocessor = SequentialAgent(
    name="receipt_preprocessor",
    description=(
        "Pre-processes receipt images before Azure OCR: validates retail category, "
        "scores quality, corrects perspective distortion, and packages the result."
    ),
    sub_agents=[
        validity_gate_agent,
        quality_gate_agent,
        geometry_agent,
        packaging_agent,
    ],
    before_agent_callback=set_session,
)

root_agent = receipt_preprocessor
```

- [ ] **Step 2: Verify imports resolve**

```bash
python -c "from receipt_preprocessor.agent import root_agent; print(root_agent.name)"
```

Expected output:
```
receipt_preprocessor
```

- [ ] **Step 3: Run local integration test**

```bash
cp receipt_preprocessor/.env.sample receipt_preprocessor/.env
# Fill in GOOGLE_CLOUD_PROJECT and GCS_BUCKET_NAME in receipt_preprocessor/.env
adk run receipt_preprocessor
```

Send message: `gs://your-bucket/test-receipt.jpg`  
Expected: The agent runs through all 4 sub-agents. Session state should contain `azure_payload` with `status: "PASS"` for a valid domestic receipt.

- [ ] **Step 4: Commit**

```bash
git add receipt_preprocessor/agent.py
git commit -m "feat: wire root SequentialAgent with all four sub-agents"
```

---

## Task 8: A2A Server, Deploy Script, and Test Client

**Files:**
- Create: `receipt_preprocessor_a2a_server/a2a_agent.py`
- Create: `receipt_preprocessor_a2a_server/remote_a2a/receipt_preprocessor/agent.json`
- Create: `deploy/deploy.py`
- Create: `testclient/remote_test.py`

- [ ] **Step 1: Create `receipt_preprocessor_a2a_server/remote_a2a/receipt_preprocessor/agent.json`**

```json
{
  "name": "receipt_preprocessor",
  "description": "Pre-processes receipt images before Azure OCR: validates retail category, scores quality, corrects perspective.",
  "url": "http://localhost:8001/a2a/receipt_preprocessor",
  "version": "1.0.0",
  "defaultInputModes": ["image/jpeg", "image/png", "image/heic"],
  "defaultOutputModes": ["application/json"],
  "capabilities": {
    "streaming": false,
    "functions": true
  },
  "skills": [
    {
      "id": "preprocess_receipt",
      "name": "Preprocess Receipt",
      "description": "Validates, scores, and corrects a receipt image before Azure OCR processing.",
      "tags": ["receipt", "ocr", "preprocessing", "validation"],
      "examples": [
        "gs://my-bucket/receipts/img001.jpg",
        "Preprocess this receipt image before OCR"
      ]
    }
  ]
}
```

- [ ] **Step 2: Create `receipt_preprocessor_a2a_server/a2a_agent.py`**

```python
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

root_agent = RemoteA2aAgent(
    name="receipt_preprocessor",
    description="Pre-processes receipt images before Azure OCR.",
    agent_card="http://localhost:8001/a2a/receipt_preprocessor/.well-known/agent.json",
    timeout=120.0,
    httpx_client=None,
)
```

- [ ] **Step 3: Create `deploy/deploy.py`**

```python
import os

import vertexai
from dotenv import load_dotenv

from receipt_preprocessor.agent import root_agent

env_path = os.path.join(os.path.dirname(__file__), "..", "receipt_preprocessor", ".env")
load_dotenv(env_path)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = f"gs://{os.getenv('GCS_BUCKET_NAME')}"

client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

remote_app = client.agent_engines.create(
    agent=root_agent,
    config={
        "display_name": "receipt-preprocessor",
        "staging_bucket": STAGING_BUCKET,
        "requirements": open(os.path.join(os.getcwd(), "requirements.txt")).readlines()
            + ["./dist/receipt_preprocessor-0.1.0-py3-none-any.whl"],
        "extra_packages": ["./dist/receipt_preprocessor-0.1.0-py3-none-any.whl"],
        "env_vars": {
            "GCS_BUCKET_NAME": os.getenv("GCS_BUCKET_NAME"),
            "QUALITY_THRESHOLD": os.getenv("QUALITY_THRESHOLD", "6"),
            "GENAI_MODEL": os.getenv("GENAI_MODEL", "gemini-2.5-flash"),
        },
    },
)

try:
    print(remote_app.api_resource.name)
except AttributeError:
    print(f"Deployed. Check attributes: {dir(remote_app)}")
```

- [ ] **Step 4: Create `testclient/remote_test.py`**

```python
"""
Remote test client for the deployed receipt_preprocessor A2A agent.

Usage:
  export AGENT_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  python testclient/remote_test.py
"""
import os

import vertexai
from dotenv import load_dotenv

load_dotenv("receipt_preprocessor/.env")

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
RESOURCE_NAME = os.environ["AGENT_RESOURCE_NAME"]

vertexai.init(project=PROJECT_ID, location=LOCATION)

from vertexai.preview import reasoning_engines  # noqa: E402

agent = reasoning_engines.ReasoningEngine(RESOURCE_NAME)
session = agent.create_session(user_id="test-user")
print(f"Session: {session['id']}")

TEST_CASES = [
    ("valid domestic mart receipt", "gs://YOUR_BUCKET/fixtures/mart_receipt.jpg"),
    ("overseas receipt → OVERSEAS_RECEIPT", "gs://YOUR_BUCKET/fixtures/overseas_receipt.jpg"),
    ("blurry image → QUALITY_LOW", "gs://YOUR_BUCKET/fixtures/blurry_receipt.jpg"),
    ("non-receipt → NON_RECEIPT", "gs://YOUR_BUCKET/fixtures/business_card.jpg"),
]

for label, gcs_uri in TEST_CASES:
    print(f"\n--- {label} ---")
    for event in agent.stream_query(
        user_id="test-user",
        session_id=session["id"],
        message=gcs_uri,
    ):
        print(event)
```

- [ ] **Step 5: Start A2A server and verify locally**

```bash
adk api_server receipt_preprocessor_a2a_server --port 8001
```

In a second terminal:
```bash
curl http://localhost:8001/a2a/receipt_preprocessor/.well-known/agent.json
```

Expected: the `agent.json` content returned as JSON.

- [ ] **Step 6: Deploy to Vertex AI**

```bash
uv build
python deploy/deploy.py
```

Expected: prints the Vertex AI resource name. Save it as `AGENT_RESOURCE_NAME`.

- [ ] **Step 7: Commit**

```bash
git add receipt_preprocessor_a2a_server/ deploy/ testclient/
git commit -m "feat: add A2A server, deploy script, and remote test client"
```

---

## Verification Checklist

After all tasks are complete:

- [ ] `pytest tests/ -v` → all 13 unit tests pass
- [ ] `adk run receipt_preprocessor` with a valid domestic receipt GCS URI → session state contains `azure_payload.status == "PASS"`
- [ ] `adk run receipt_preprocessor` with an overseas receipt → `rejection_code == "OVERSEAS_RECEIPT"`
- [ ] `adk run receipt_preprocessor` with a blurry image → `rejection_code == "QUALITY_LOW"`
- [ ] `adk run receipt_preprocessor` with a non-receipt image → `rejection_code == "NON_RECEIPT"`
- [ ] `adk run receipt_preprocessor` with a tilted receipt → `geometry_corrected == True` in session state
- [ ] A2A server responds to `curl /.well-known/agent.json`
- [ ] Deployed agent on Vertex AI responds via `testclient/remote_test.py`
