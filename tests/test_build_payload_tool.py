import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    sys.modules.pop("receipt_preprocessor.config", None)


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
