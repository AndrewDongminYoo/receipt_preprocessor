import json
import mimetypes
import os
import re

import google.genai as genai
from google.adk.tools.tool_context import ToolContext
from google.genai import types as genai_types

from receipt_preprocessor import config

_FALLBACK_RESPONSE = {
    "type": "NON_RECEIPT",
    "store_category": "OTHER",
    "confidence": 0.0,
    "reason": "Gemini response could not be parsed",
}


def _extract_json(text: str) -> dict:
    # First try to locate a JSON object directly (handles preamble text and single backticks)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    # Fall back to stripping triple-backtick fences
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

    policy_path = os.path.join(os.path.dirname(__file__), "../../../policy.json")
    with open(policy_path) as f:
        policy = json.load(f)

    mime_type = mimetypes.guess_type(image_uri)[0] or "image/jpeg"

    client = genai.Client()
    response = client.models.generate_content(
        model=config.GENAI_MODEL,
        contents=[
            genai_types.Part.from_uri(file_uri=image_uri, mime_type=mime_type),
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

    try:
        result = _extract_json(response.text)
        receipt_type = result.get("type", "NON_RECEIPT")
        store_category = result.get("store_category", "OTHER")
    except (json.JSONDecodeError, AttributeError):
        result = _FALLBACK_RESPONSE.copy()
        receipt_type = "NON_RECEIPT"
        store_category = "OTHER"

    tool_context.state["receipt_type"] = receipt_type
    tool_context.state["store_category"] = store_category
    result["type"] = receipt_type
    result["store_category"] = store_category
    return result
