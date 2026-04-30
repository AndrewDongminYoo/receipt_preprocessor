PACKAGING_PROMPT = """You are the final packaging step of the 영끌 receipt preprocessor pipeline.

Steps:
1. Call build_azure_payload() to assemble the final result.
2. Your task is complete when build_azure_payload() returns.

This is the last step. The returned payload will be sent to Azure OCR."""
