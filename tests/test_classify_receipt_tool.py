import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    sys.modules.pop("receipt_preprocessor.config", None)


def test_classify_domestic_retail_sets_state():
    from receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool import (
        classify_receipt,
    )

    ctx = MagicMock()
    ctx.state = {}

    mock_response = MagicMock()
    mock_response.text = (
        '{"type": "DOMESTIC_RETAIL", "store_category": "MART",'
        ' "confidence": 0.95, "reason": "이마트 영수증"}'
    )

    with patch(
        "receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = classify_receipt("gs://bucket/receipt.jpg", ctx)

    assert result["type"] == "DOMESTIC_RETAIL"
    assert result["store_category"] == "MART"
    assert ctx.state["original_image_uri"] == "gs://bucket/receipt.jpg"
    assert ctx.state["receipt_type"] == "DOMESTIC_RETAIL"
    assert ctx.state["store_category"] == "MART"


def test_classify_returns_non_receipt_when_no_uri():
    from receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool import (
        classify_receipt,
    )

    ctx = MagicMock()
    ctx.state = {}
    result = classify_receipt("", ctx)

    assert result["type"] == "NON_RECEIPT"
    assert result["confidence"] == 0.0


def test_classify_handles_markdown_wrapped_json():
    from receipt_preprocessor.sub_agents.validity.tools.classify_receipt_tool import (
        classify_receipt,
    )

    ctx = MagicMock()
    ctx.state = {}

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
        result = classify_receipt("gs://bucket/receipt.jpg", ctx)

    assert result["type"] == "OVERSEAS"
