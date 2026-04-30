"""
Remote test client for the deployed receipt_preprocessor A2A agent.

Usage:
  export AGENT_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  python test_client/remote_test.py
"""

import os

import vertexai
from dotenv import load_dotenv

load_dotenv("receipt_preprocessor/.env")

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
RESOURCE_NAME = os.environ["AGENT_RESOURCE_NAME"]

vertexai.init(project=PROJECT_ID, location=LOCATION)

from vertexai.preview import reasoning_engines  # noqa: E402

agent = reasoning_engines.ReasoningEngine(RESOURCE_NAME)
session = agent.create_session(user_id="test-user")
print(f"Session: {session['id']}")

TEST_CASES = [
    ("valid domestic mart receipt", "gs://YOUR_BUCKET/fixtures/mart_receipt.jpg"),
    (
        "overseas receipt → OVERSEAS_RECEIPT",
        "gs://YOUR_BUCKET/fixtures/overseas_receipt.jpg",
    ),
    ("blurry image → QUALITY_LOW", "gs://YOUR_BUCKET/fixtures/blurry_receipt.jpg"),
    ("non-receipt → NON_RECEIPT", "gs://YOUR_BUCKET/fixtures/business_card.jpg"),
]

for label, gcs_uri in TEST_CASES:
    print(f"\n--- {label} ---")
    for event in agent.stream_query(
        user_id="test-user",
        session_id=session["id"],
        message=gcs_uri,
    ):
        print(event)
