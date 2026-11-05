"""Manual draft persistence keeps the image and content in one transaction."""

from app import database


def test_manual_draft_persists_supplied_image_url_and_content(monkeypatch):
    calls = []

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            calls.append((query, params))
            if "INSERT INTO products" in query:
                return type("Result", (), {"fetchone": lambda self: {
                    "id": 10, "product_name": params[0], "product_details": params[1],
                    "image_url": params[2], "affiliate_url": params[3],
                    "idempotency_key": params[4], "request_fingerprint": params[5],
                }})()
            return type("Result", (), {"fetchone": lambda self: {
                "id": 20, "product_id": params[0], "title": params[2],
                "description": params[3], "alt_text": params[4],
            }})()

    monkeypatch.setattr(database, "connection", lambda: Connection())
    product, content, created = database.persist_manual_publish_draft(
        title="Kitchen organizer", description="Tidy spice storage",
        image_url="https://cdn.example.test/pin.png",
        affiliate_url="https://example.test/item?tag=home-20",
        idempotency_key="manual-draft-key-0001", request_fingerprint="a" * 64,
    )
    assert created is True
    assert product["image_url"] == "https://cdn.example.test/pin.png"
    assert content["title"] == "Kitchen organizer"
    assert len(calls) == 2
    assert calls[0][1][2] == "https://cdn.example.test/pin.png"
