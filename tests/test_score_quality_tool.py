import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    sys.modules.pop("receipt_preprocessor.config", None)


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
    mock_response.text = '{"score": 3, "issues": ["blur", "underexposed"], "reason": "흐릿하고 어두운 이미지"}'

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
