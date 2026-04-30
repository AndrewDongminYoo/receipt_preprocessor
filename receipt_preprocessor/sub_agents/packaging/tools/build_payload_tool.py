from google.adk.tools.tool_context import ToolContext


def build_azure_payload(tool_context: ToolContext) -> dict:
    """Assembles the final payload for Azure OCR.

    Returns a REJECT payload if rejection_code is set in state (upstream gate
    already rejected), otherwise returns a PASS payload.
    Writes azure_payload to session state in both cases.
    """
    rejection_code = tool_context.state.get("rejection_code")
    if rejection_code:
        payload = {
            "status": "REJECT",
            "code": rejection_code,
            "userMessage": tool_context.state.get("rejection_message", ""),
        }
        tool_context.state["azure_payload"] = payload
        return payload

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
