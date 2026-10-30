"""Sanitized error-context coverage for provider diagnostic failure paths."""


def test_deepseek_diagnostic_failure_summary_is_sanitized(monkeypatch):
    from app import diagnostics
    from app.config import settings

    monkeypatch.setattr(settings, "app_api_key", "test-api-key")
    monkeypatch.setattr(settings, "database_url", "postgresql://unused")
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", "unused")
    monkeypatch.setattr(settings, "llm_api_key", "configured-test-key")

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, query):
            assert query == "SELECT 1"
            return self
        def fetchone(self): return (1,)

    monkeypatch.setattr("app.database.connection", lambda: FakeConnection())
    monkeypatch.setattr("app.credential_vault.get_pinterest_credential", lambda account_id: {"access_token": "private-test-token"})

    class FakeResponse:
        is_success = True
        status_code = 200

    class FakeHttpClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def get(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setattr(diagnostics.httpx, "Client", FakeHttpClient)
    monkeypatch.setattr("app.media_generation.generate_and_host_pin_image", lambda **kwargs: {"image_url": "data:image/png;base64,abc", "model": "safe-test-model"})
    monkeypatch.setattr("app.pinterest.image_media_source", lambda url: {"source_type": "image_base64"})

    def fail_generation(**kwargs):
        raise RuntimeError("DO_NOT_LOG-this-secret prompt or key")

    monkeypatch.setattr("app.content_generation.generate_pin_content", fail_generation)

    result = diagnostics.run_live_diagnostics(diagnostics.DiagnosticRunInput(account_id="pinterest:test-account"))
    serialized = str(result)
    assert result["checks"]["deepseek_multimodal_generation"] == {"ok": False, "error": "deepseek_multimodal_completion_failed"}
    assert "DO_NOT_LOG" not in serialized
    assert "private-test-token" not in serialized
    assert "configured-test-key" not in serialized
    assert result["side_effects"]["pinterest_pin_created"] is False
