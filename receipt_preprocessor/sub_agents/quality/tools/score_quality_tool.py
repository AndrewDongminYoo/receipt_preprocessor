import json

import google.genai as genai
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config
from receipt_preprocessor.tools.gcs_utils import make_image_part
from receipt_preprocessor.tools.json_utils import extract_json

_FALLBACK_RESPONSE = {
    "score": 0,
    "issues": ["parse_error"],
    "reason": "Gemini response could not be parsed",
}


def score_image_quality(tool_context: ToolContext) -> dict:
    """Scores the receipt image quality on a 0-10 scale.

    Reads original_image_uri from session state.
    Writes quality_score and quality_issues to session state.
    """
    image_uri = tool_context.state.get("original_image_uri")
    if not image_uri:
        result = {
            "score": 0,
            "issues": ["no_image"],
            "reason": "이미지 URI가 없습니다.",
        }
        tool_context.state["quality_score"] = 0
        tool_context.state["quality_issues"] = ["no_image"]
        return result

    client = genai.Client()
    response = client.models.generate_content(
        model=config.GENAI_MODEL,
        contents=[
            make_image_part(image_uri),
            """Evaluate this receipt image quality for OCR processing. Score 0-10 (10 = perfect).

Identify issues from this list only: "blur", "overexposed", "underexposed", "occluded", "low_res"

Respond ONLY with valid JSON, no markdown:
{
  "score": 0-10,
  "issues": ["issue1"],
  "reason": "brief explanation in Korean"
}""",
        ],
    )

    try:
        result = extract_json(response.text)
        score = int(result.get("score", 0))
        issues = result.get("issues", [])
    except (json.JSONDecodeError, AttributeError, ValueError):
        result = _FALLBACK_RESPONSE.copy()
        score = 0
        issues = ["parse_error"]

    tool_context.state["quality_score"] = score
    tool_context.state["quality_issues"] = issues
    result["score"] = score
    result["issues"] = issues
    return result
