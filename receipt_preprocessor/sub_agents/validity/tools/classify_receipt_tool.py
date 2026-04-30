import json
import os

import google.genai as genai
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config
from receipt_preprocessor.tools.gcs_utils import make_image_part
from receipt_preprocessor.tools.json_utils import extract_json

_POLICY_PATH = os.path.join(os.path.dirname(__file__), "../../../policy.json")
with open(_POLICY_PATH) as _f:
    _POLICY = json.load(_f)

_FALLBACK_RESPONSE = {
    "type": "NON_RECEIPT",
    "store_category": "OTHER",
    "confidence": 0.0,
    "reason": "Gemini response could not be parsed",
}


def classify_receipt(image_uri: str, tool_context: ToolContext) -> dict:
    """Classifies the receipt image as DOMESTIC_RETAIL, OVERSEAS, NON_RETAIL, or NON_RECEIPT.

    Accepts the image URI from the agent (GCS gs:// or local path).
    Writes original_image_uri, receipt_type, and store_category to session state.
    """
    if not image_uri:
        return {
            "type": "NON_RECEIPT",
            "store_category": "OTHER",
            "confidence": 0.0,
            "reason": "No image URI provided",
        }
    tool_context.state["original_image_uri"] = image_uri

    client = genai.Client()
    response = client.models.generate_content(
        model=config.GENAI_MODEL,
        contents=[
            make_image_part(image_uri),
            f"""Classify this image as a receipt for the 영끌 Korean retail reward app.

Domestic retail keywords (DOMESTIC_RETAIL): {_POLICY['retail_keywords_ko']}
Overseas indicators (OVERSEAS): {_POLICY['overseas_indicators']}

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
        result = extract_json(response.text)
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
