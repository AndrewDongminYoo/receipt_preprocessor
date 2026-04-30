import os

import vertexai
from dotenv import load_dotenv

from receipt_preprocessor.agent import root_agent

# Load environment variables from receipt_preprocessor/.env
env_path = os.path.join(os.path.dirname(__file__), "..", "receipt_preprocessor", ".env")
load_dotenv(env_path)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = f"gs://{os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}"


client = vertexai.Client(
    project=PROJECT_ID,
    location=LOCATION,
)


remote_app = client.agent_engines.create(
    agent=root_agent,
    config={
        "display_name": "image-scoring",
        "staging_bucket": STAGING_BUCKET,
        "requirements": open(os.path.join(os.getcwd(), "requirements.txt")).readlines()
        + ["./dist/receipt_preprocessor-0.1.0-py3-none-any.whl"],
        "extra_packages": [
            "./dist/receipt_preprocessor-0.1.0-py3-none-any.whl",
        ],
        "env_vars": {"GCS_BUCKET_NAME": os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")},
    },
)

print(f"DEBUG: AgentEngine attributes: {dir(remote_app)}")
try:
    print(remote_app.api_resource.name)
except AttributeError:
    print("Could not find resource_name, check DEBUG output above.")
