import os

import vertexai
from dotenv import load_dotenv

from receipt_preprocessor.agent import root_agent

env_path = os.path.join(os.path.dirname(__file__), "..", "receipt_preprocessor", ".env")
load_dotenv(env_path)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = f"gs://{os.getenv('GCS_BUCKET_NAME')}"

client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

_req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
with open(_req_path) as f:
    _base_requirements = f.readlines()

remote_app = client.agent_engines.create(
    agent=root_agent,
    config={
        "display_name": "receipt-preprocessor",
        "staging_bucket": STAGING_BUCKET,
        "requirements": _base_requirements
        + ["./dist/receipt_preprocessor-0.1.0-py3-none-any.whl"],
        "extra_packages": ["./dist/receipt_preprocessor-0.1.0-py3-none-any.whl"],
        "env_vars": {
            "GCS_BUCKET_NAME": os.getenv("GCS_BUCKET_NAME"),
            "QUALITY_THRESHOLD": os.getenv("QUALITY_THRESHOLD", "6"),
            "GENAI_MODEL": os.getenv("GENAI_MODEL", "gemini-2.5-flash"),
        },
    },
)

try:
    print(remote_app.api_resource.name)
except AttributeError:
    print(f"Deployed. Check attributes: {dir(remote_app)}")
