import sys


def test_config_uses_env_defaults(monkeypatch):
    monkeypatch.delenv("QUALITY_THRESHOLD", raising=False)
    monkeypatch.delenv("GENAI_MODEL", raising=False)
    monkeypatch.delenv("GCS_IMAGE_TTL_DAYS", raising=False)
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")

    sys.modules.pop("receipt_preprocessor.config", None)
    import receipt_preprocessor.config as config

    assert config.QUALITY_THRESHOLD == 6
    assert config.GENAI_MODEL == "gemini-2.5-flash"
    assert config.GCS_IMAGE_TTL_DAYS == 7
    assert config.GCS_BUCKET_NAME == "test-bucket"


def test_config_missing_bucket_raises(monkeypatch):
    # Set to empty string so load_dotenv (override=False) won't restore from .env
    monkeypatch.setenv("GCS_BUCKET_NAME", "")

    sys.modules.pop("receipt_preprocessor.config", None)
    import pytest

    with pytest.raises(EnvironmentError, match="GCS_BUCKET_NAME"):
        import receipt_preprocessor.config  # noqa: F401


def test_config_invalid_int_raises(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("QUALITY_THRESHOLD", "not-a-number")

    sys.modules.pop("receipt_preprocessor.config", None)
    import pytest

    with pytest.raises(EnvironmentError, match="QUALITY_THRESHOLD"):
        import receipt_preprocessor.config  # noqa: F401
