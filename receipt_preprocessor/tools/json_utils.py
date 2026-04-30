import json
import re


def extract_json(text: str) -> dict:
    """Extracts the first JSON object from text, stripping markdown fences if needed."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(cleaned)
