from google.adk.tools.tool_context import ToolContext


def build_azure_payload(tool_context: ToolContext) -> dict:
    """Assembles the final payload to be sent to Azure OCR.

    Reads corrected_image_uri (falls back to original_image_uri), store_category,
    session_id, quality_score, and geometry_corrected from session state.
    Writes azure_payload to session state.
    """
    corrected_uri = tool_context.state.get(
        "corrected_image_uri"
    ) or tool_context.state.get("original_image_uri")

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
