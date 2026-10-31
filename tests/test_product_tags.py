from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "product-tag-test-key"}
PUBLICATION = {
    "id": 7,
    "status": "succeeded",
    "account_id": "pinterest:123",
    "board_id": "board-1",
    "pinterest_pin_id": "hero-1",
}


def _patch_tag_dependencies(monkeypatch, *, tags=None):
    import app.database
    import app.credential_vault
    import app.pinterest

    state = {"tags": list(tags or []), "added": []}
    monkeypatch.setattr(app.database, "get_publication", lambda _id: dict(PUBLICATION))
    monkeypatch.setattr(app.credential_vault, "get_pinterest_credential", lambda _id: {"access_token": "test-token"})
    monkeypatch.setattr(app.pinterest, "get_pin_read_only", lambda **_kwargs: {"id": "hero-1", "board_id": "board-1"})

    def read_tags(**_kwargs):
        return list(state["tags"])

    def add_tags(*, product_pin_ids, **_kwargs):
        state["added"].extend(product_pin_ids)
        state["tags"].extend(product_pin_ids)
        return {"product_tags": [{"pin_id": item} for item in product_pin_ids]}

    monkeypatch.setattr(app.pinterest, "list_product_tags_read_only", read_tags)
    monkeypatch.setattr(app.pinterest, "add_product_tags_to_pin", add_tags)
    return state


def test_attach_product_tags_only_writes_missing_ids(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "product-tag-test-key")
    state = _patch_tag_dependencies(monkeypatch, tags=["product-existing"])

    response = client.post(
        "/publications/7/product-tags",
        headers=HEADERS,
        json={"product_pin_ids": ["product-existing", "product-new"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tagged"] is True
    assert body["newly_attached_product_pin_ids"] == ["product-new"]
    assert body["already_attached_product_pin_ids"] == ["product-existing"]
    assert body["verified_product_pin_ids"] == ["product-existing", "product-new"]
    assert state["added"] == ["product-new"]


def test_attach_product_tags_rejects_duplicate_ids_before_provider_calls(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "product-tag-test-key")
    state = _patch_tag_dependencies(monkeypatch)

    response = client.post(
        "/publications/7/product-tags",
        headers=HEADERS,
        json={"product_pin_ids": ["same", "same"]},
    )

    assert response.status_code == 422
    assert state["added"] == []


def test_attach_product_tags_rejects_unpublished_publication(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "product-tag-test-key")
    import app.database
    import app.credential_vault

    unpublished = dict(PUBLICATION, status="pending")
    monkeypatch.setattr(app.database, "get_publication", lambda _id: unpublished)
    credential_calls = []
    monkeypatch.setattr(
        app.credential_vault,
        "get_pinterest_credential",
        lambda _id: credential_calls.append(_id),
    )

    response = client.post(
        "/publications/7/product-tags",
        headers=HEADERS,
        json={"product_pin_ids": ["product-1"]},
    )

    assert response.status_code == 409
    assert credential_calls == []


def test_product_tag_verification_is_read_only(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "product-tag-test-key")
    state = _patch_tag_dependencies(monkeypatch, tags=["product-1"])

    response = client.get("/publications/7/product-tags", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["product_pin_ids"] == ["product-1"]
    assert response.json()["read_only"] is True
    assert state["added"] == []
