import os


def test_config_quality_threshold_default():
    os.environ.setdefault("GCS_BUCKET_NAME", "test-bucket")
    from receipt_preprocessor import config

    assert config.QUALITY_THRESHOLD == int(os.getenv("QUALITY_THRESHOLD", "6"))
    assert config.GENAI_MODEL == os.getenv("GENAI_MODEL", "gemini-2.5-flash")
    assert config.GCS_IMAGE_TTL_DAYS == 7
