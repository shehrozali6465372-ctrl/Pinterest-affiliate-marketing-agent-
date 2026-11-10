from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import database, publishing_gateway, workflow
from app.content_generation import GeneratedContent
from app.model2_repository import Model2ConflictError


ACCOUNT_ID = "pinterest:123456789"
PRODUCT_PAYLOAD = {
    "product_name": "Wooden spice rack",
    "product_details": "Wall-mounted rack with six jars",
    "affiliate_url": "https://example.com/affiliate-product",
    "account_id": ACCOUNT_ID,
}


def _install_workflow_mocks(monkeypatch, *, niche_row=None):
    calls = {
        "generation": [],
        "product": [],
        "publish": [],
        "reservation": [],
    }
    if niche_row is None:
        monkeypatch.setattr(
            workflow,
            "get_active_account_niche_context",
            lambda *args: (_ for _ in ()).throw(AssertionError("no niche lookup expected")),
        )
    else:
        monkeypatch.setattr(
            workflow,
            "get_active_account_niche_context",
            lambda account_id, niche_id: dict(niche_row),
        )

    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    monkeypatch.setattr(
        workflow,
        "get_pinterest_credential",
        lambda account_id: {"access_token": "unit-test-token", "pinterest_user_id": "123456789"},
    )
    monkeypatch.setattr(
        workflow,
        "_pinterest_request",
        lambda method, path, token: (200, {"id": "123456789"}),
    )
    monkeypatch.setattr(workflow, "_ensure_board", lambda token, name, description: "board-unit-test")
    monkeypatch.setattr(
        workflow,
        "reserve_workflow_generation",
        lambda **kwargs: calls["reservation"].append(kwargs) or {
            "acquired": True,
            "status": "generating",
        },
    )
    monkeypatch.setattr(
        workflow,
        "generate_pin_image",
        lambda **kwargs: {
            "image_url": "data:image/png;base64," + base64.b64encode(b"x" * 1024).decode("ascii"),
            "model": "image-model-test",
        },
    )
    monkeypatch.setattr(workflow, "save_workflow_generation_image", lambda **kwargs: None)
    monkeypatch.setattr(workflow, "save_workflow_generation_content", lambda **kwargs: None)

    def generate(**kwargs):
        calls["generation"].append(kwargs)
        return (
            GeneratedContent(
                pin_idea="Organize spices on a wall rack",
                title="Organized Spice Rack",
                description="A useful kitchen organizer. Affiliate disclosure: This post contains affiliate links; I may earn a commission at no extra cost to you.",
                alt_text="A wooden spice rack holding jars on a kitchen wall.",
            ),
            "deepseek-flash-test",
        )

    monkeypatch.setattr(workflow, "generate_pin_content", generate)

    content = {
        "id": 88,
        "title": "Organized Spice Rack",
        "description": "A useful kitchen organizer. Affiliate disclosure: This post contains affiliate links; I may earn a commission at no extra cost to you.",
        "alt_text": "A wooden spice rack holding jars on a kitchen wall.",
    }

    def persist(**kwargs):
        calls["product"].append(kwargs)
        return {"id": 77}, content

    monkeypatch.setattr(workflow, "create_product_with_content_version", persist)

    def publish(**kwargs):
        calls["publish"].append(kwargs)
        return {
            "published": True,
            "already_published": False,
            "pin_id": "pin-unit-test",
            "http_status": 201,
        }

    monkeypatch.setattr(workflow, "publish_pin", publish)
    return calls


def test_model1_workflow_without_niche_keeps_original_fingerprint_and_call_shape(monkeypatch):
    calls = _install_workflow_mocks(monkeypatch)
    payload = workflow.ProductWorkflowInput(**PRODUCT_PAYLOAD)

    result = workflow.publish_product_end_to_end(
        payload,
        idempotency_key="model1-no-niche-001",
    )

    old_fingerprint_payload = {
        "product_name": payload.product_name,
        "product_details": payload.product_details,
        "affiliate_url": payload.affiliate_url,
        "account_id": payload.account_id,
        "board_name": payload.board_name,
        "board_description": payload.board_description,
    }
    expected_fingerprint = hashlib.sha256(
        json.dumps(
            old_fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert result["pin_id"] == "pin-unit-test"
    assert calls["generation"] == [{
        "product_name": payload.product_name,
        "product_details": payload.product_details,
        "image_url": "data:image/png;base64," + base64.b64encode(b"x" * 1024).decode("ascii"),
    }]
    assert calls["product"][0]["prompt_version"] == "pin-content-v1"
    assert calls["product"][0]["request_fingerprint"] == expected_fingerprint
    assert "niche_id" not in calls["publish"][0]


def test_model2_workflow_passes_validated_niche_context_and_gateway_attribution(monkeypatch):
    niche_row = {
        "niche_id": 19,
        "slug": "bathroom-storage",
        "display_name": "Bathroom Storage",
        "description": "Small-space storage and organization",
        "default_region": "GB+IE",
    }
    calls = _install_workflow_mocks(monkeypatch, niche_row=niche_row)
    payload = workflow.ProductWorkflowInput(**PRODUCT_PAYLOAD, niche_id=19)

    result = workflow.publish_product_end_to_end(
        payload,
        idempotency_key="model2-with-niche-001",
    )

    context = calls["generation"][0]["niche_context"]
    assert context.niche_id == 19
    assert context.display_name == "Bathroom Storage"
    assert calls["product"][0]["prompt_version"] == "pin-content-v2-niche-context"
    assert calls["publish"][0]["niche_id"] == 19
    assert calls["product"][0]["request_fingerprint"] != ""
    assert result["pin_id"] == "pin-unit-test"


def test_model2_workflow_rejects_inactive_assignment_before_any_provider_or_pinterest_call(monkeypatch):
    calls = _install_workflow_mocks(monkeypatch, niche_row=None)
    monkeypatch.setattr(
        workflow,
        "get_active_account_niche_context",
        lambda account_id, niche_id: (_ for _ in ()).throw(
            Model2ConflictError("Account niche assignment is inactive")
        ),
    )
    payload = workflow.ProductWorkflowInput(**PRODUCT_PAYLOAD, niche_id=19)

    with pytest.raises(HTTPException) as exc:
        workflow.publish_product_end_to_end(
            payload,
            idempotency_key="model2-inactive-niche-001",
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "niche_assignment_inactive"
    assert calls["generation"] == []
    assert calls["product"] == []
    assert calls["publish"] == []
    assert calls["reservation"] == []


def _gateway_args():
    return {
        "product_id": 1,
        "content_version_id": 2,
        "board_id": "board-unit-test",
        "account_id": ACCOUNT_ID,
        "access_token": "unit-test-token",
        "title": "Organized Spice Rack",
        "description": "Useful kitchen organization.",
        "alt_text": "A wooden spice rack holding jars.",
        "media_source": {"source_type": "image_base64", "data": "ZmFrZQ=="},
        "destination_url": "https://example.com/product",
    }


@pytest.mark.parametrize(
    ("blocked_flag", "expected_code"),
    [
        ("niche_assignment_inactive", "niche_assignment_inactive"),
        ("niche_account_not_connected", "niche_account_not_connected"),
        ("niche_attribution_mismatch", "publication_niche_attribution_mismatch"),
        ("niche_attribution_missing", "publication_niche_attribution_missing"),
    ],
)
def test_gateway_blocks_niche_attribution_errors_before_pinterest_post(
    monkeypatch, blocked_flag, expected_code
):
    captured = {}
    monkeypatch.setattr(
        database,
        "begin_publish_attempt",
        lambda **kwargs: captured.update(kwargs) or {"blocked": True, blocked_flag: True},
    )

    class NeverPostClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Pinterest HTTP client must not be constructed")

    monkeypatch.setattr(publishing_gateway.httpx, "Client", NeverPostClient)
    args = _gateway_args()
    args["niche_id"] = 19

    with pytest.raises(HTTPException) as exc:
        publishing_gateway.publish_pin(**args)

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == expected_code
    assert captured["niche_id"] == 19


def test_gateway_preserves_legacy_no_niche_reservation_call(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        database,
        "begin_publish_attempt",
        lambda **kwargs: captured.update(kwargs) or {
            "blocked": True,
            "status": "succeeded",
            "pinterest_pin_id": "already-published-pin",
            "id": 55,
        },
    )

    result = publishing_gateway.publish_pin(**_gateway_args())

    assert result["already_published"] is True
    assert result["pin_id"] == "already-published-pin"
    assert "niche_id" not in captured


def test_gateway_rejects_invalid_niche_id_before_reservation(monkeypatch):
    called = []
    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kwargs: called.append(kwargs))

    args = _gateway_args()
    args["niche_id"] = True
    with pytest.raises(HTTPException) as exc:
        publishing_gateway.publish_pin(**args)

    assert exc.value.status_code == 422
    assert called == []
