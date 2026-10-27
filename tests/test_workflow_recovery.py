"""Focused regression tests for Pinterest request failures in the E2E workflow."""

import httpx
import pytest
from fastapi import HTTPException

from app import workflow
from app.config import settings


def test_workflow_pinterest_timeout_is_reported_as_gateway_error(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def request(self, *args, **kwargs):
            raise httpx.ReadTimeout("simulated timeout")

    monkeypatch.setattr(workflow.httpx, "Client", FakeClient)
    with pytest.raises(HTTPException) as exc:
        workflow._pinterest_request("POST", "/pins", "test-token", body={"title": "test"})

    assert exc.value.status_code == 502
    assert "verify the account before retrying" in exc.value.detail


def test_workflow_pinterest_5xx_is_normalized_to_gateway_error(monkeypatch):
    class FakeResponse:
        status_code = 503
        content = b'{"message":"temporary error"}'
        is_success = False

        def json(self):
            return {"message": "temporary error"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def request(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(workflow.httpx, "Client", FakeClient)
    with pytest.raises(HTTPException) as exc:
        workflow._pinterest_request("POST", "/pins", "test-token", body={"title": "test"})

    assert exc.value.status_code == 502
    assert "HTTP 503" in exc.value.detail
