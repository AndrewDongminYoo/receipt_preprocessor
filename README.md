# multiagent-handson

A multi-agent AI system that iteratively generates lockscreen images from text, scores them against a compliance policy, and retries until the image meets the quality bar — built with **Google ADK**, **Imagen 3**, and **Gemini 2.5 Flash**.

## How it works

```plaintext
Input text
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  receipt_preprocessor  (LoopAgent)                         │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  image_generation_scoring_agent (Sequential) │   │
│  │                                              │   │
│  │  1. image_generation_prompt_agent            │   │
│  │     Reads policy.json → builds Imagen prompt │   │
│  │                                              │   │
│  │  2. image_generation_agent                   │   │
│  │     Calls Imagen 3 → uploads PNG to GCS      │   │
│  │                                              │   │
│  │  3. scoring_images_prompt                    │   │
│  │     Evaluates image against 11 criteria      │   │
│  │     Sets total_score (0–50) in session state │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  checker_agent                                      │
│     score > SCORE_THRESHOLD → escalate (stop)       │
│     OR loop_iteration >= MAX_ITERATIONS → stop      │
│     else → loop again                               │
└─────────────────────────────────────────────────────┘
    │
    ▼
Final image + score
```

Images are stored in GCS under the path `{date}/{unique_id}/{artifact_name}`.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Google Cloud project with these APIs enabled:
  - Vertex AI API
  - Cloud Storage API
  - Imagen API (allowlist required for `imagen-3.0-generate-002`)
- `gcloud` CLI authenticated: `gcloud auth application-default login`

## Setup

```bash
# 1. Install dependencies
uv sync
source .venv/bin/activate

# 2. Create and fill in environment variables
cp receipt_preprocessor/.env.sample receipt_preprocessor/.env
```

Edit `receipt_preprocessor/.env`:

```bash
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_STORAGE_BUCKET=your-gcp-project-id-imagescoring-bucket
GCS_BUCKET_NAME=your-gcp-project-id-imagescoring-bucket
SCORE_THRESHOLD=40
IMAGEN_MODEL=imagen-3.0-generate-002
GENAI_MODEL=gemini-2.5-flash
```

Create the GCS bucket if it does not already exist:

```bash
gcloud storage buckets create gs://$(gcloud config get-value project)-imagescoring-bucket \
  --location=us-central1
```

## Running locally

```bash
# Interactive CLI session
adk run receipt_preprocessor

# Web UI (http://localhost:8000)
adk web
```

Send a message like `"Generate a lockscreen image of a serene mountain at sunrise"` to start the pipeline.

## Configuration reference

| Variable                | Default                   | Description                                   |
| ----------------------- | ------------------------- | --------------------------------------------- |
| `GOOGLE_CLOUD_PROJECT`  | —                         | GCP project used for Vertex AI and GCS        |
| `GOOGLE_CLOUD_LOCATION` | `us-central1`             | Region for Vertex AI inference                |
| `GCS_BUCKET_NAME`       | —                         | Bucket where generated PNGs are stored        |
| `SCORE_THRESHOLD`       | `40`                      | Minimum score (out of 50) to accept the image |
| `MAX_ITERATIONS`        | `1`                       | Hard cap on retry loop iterations             |
| `IMAGEN_MODEL`          | `imagen-3.0-generate-002` | Image generation model                        |
| `GENAI_MODEL`           | `gemini-2.5-flash`        | LLM used for all text-based agents            |

## Scoring criteria (`policy.json`)

Each image is evaluated on 11 criteria, scored 0–5 each (max total: **50**):

| Criterion              | What is checked                                            |
| ---------------------- | ---------------------------------------------------------- |
| General Guidelines     | No restricted content (humans, politics, violence, etc.)   |
| Global Defaults        | Baseline defaults for image/text/video resources           |
| Media Type Definitions | Format, resolution, and encoding conformance               |
| Image Specifications   | High-resolution, photorealistic, distortion-free           |
| Text Specifications    | Concise copy, no clickbait, proper encoding                |
| Clock Visibility       | Adequate spacing and contrast around the clock area        |
| Notification Area      | Top portion clear with high contrast for notifications     |
| Safe Zones             | No important content in top 25%, bottom 15%, left/right 5% |
| Composition Styles     | Visually appealing layout per defined style definitions    |
| Color Scheme           | Sufficient contrast and harmonious color relationships     |

## Deploying to Vertex AI Agent Engine

```bash
# 1. Build the wheel
uv build

# 2. Deploy (reads receipt_preprocessor/.env for project/bucket config)
python deploy/deploy.py
```

The script prints the Vertex AI resource name on success. Save this for A2A wiring.

## A2A server (Agent-to-Agent protocol)

The `receipt_preprocessor_adk_a2a_server/` directory wraps the agent as an A2A-compatible HTTP service.
Another agent can call it remotely using the card at `http://localhost:8001/a2a/receipt_preprocessor/.well-known/agent.json`.

```bash
# Start the A2A server
adk api_server receipt_preprocessor_adk_a2a_server --port 8001

# Run the test client against the live server
python test_client/remote_test.py
```

Supported I/O: input `text/plain` → output `image/png` + `text/plain` (streaming enabled).

## Resources

- [Codelab: Create multi-agents with ADK and A2A](https://codelabs.developers.google.com/codelabs/create-multi-agents-adk-a2a?hl=ja#1)
- [Codelab: InstaVibe ADK multi-agents](https://codelabs.developers.google.com/instavibe-adk-multi-agents/instructions#0)
- [Google ADK documentation](https://google.github.io/adk-docs/)
- [A2A Protocol specification](https://a2a-protocol.org/latest/)
