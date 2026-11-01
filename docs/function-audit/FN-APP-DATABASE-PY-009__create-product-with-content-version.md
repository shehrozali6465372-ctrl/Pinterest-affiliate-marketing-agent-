# create_product_with_content_version

- **Unique ID:** `FN-APP-DATABASE-PY-009`
- **Source:** `app/database.py:160-205`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

Creates product and its initial content version together. Verify explicit transaction scope, rollback on any failed insert, uniqueness constraints on idempotency_key, returned row shapes, and whether external media URLs or image_url null values are supported.

## Exact isolated source

```python
def create_product_with_content_version(
    *,
    product_name: str,
    product_details: str,
    image_url: str | None,
    affiliate_url: str,
    idempotency_key: str,
    provider: str,
    model_id: str,
    prompt_version: str,
    pin_idea: str,
    title: str,
    description: str,
    alt_text: str,
) -> tuple[dict, dict]:
    """Atomically persist a product and its first content version.

    Both inserts share one pooled connection/transaction so a failed content
    insert cannot leave an idempotency key attached to a half-created product.
    """
    with connection() as conn:
        product = conn.execute(
            """
            INSERT INTO products (product_name, product_details, image_url, affiliate_url, idempotency_key)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, product_name, product_details, image_url, affiliate_url, created_at, idempotency_key
            """,
            (product_name, product_details, image_url, affiliate_url, idempotency_key),
        ).fetchone()
        content = conn.execute(
            """
            INSERT INTO content_versions
                (product_id, version_number, provider, model_id, prompt_version,
                 pin_idea, title, description, alt_text)
            VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, product_id, version_number, provider, model_id, prompt_version,
                      pin_idea, title, description, alt_text, created_at
            """,
            (
                product["id"], provider, model_id, prompt_version,
                pin_idea, title, description, alt_text,
            ),
        ).fetchone()
        return dict(product), dict(content)


```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current main source blob.
- `VERIFIED — LINE RANGE`: source lines isolated as a single definition.
- `UNVERIFIED — LOGIC`: caller/callee, tests, concurrency and failure behavior remain to be proven.
- `UNVERIFIED — LIVE DATABASE`: no production DB writes or state transitions executed.

## Remaining evidence

Review all call sites, SQL schema/migrations, transaction boundaries, integration tests, race-condition tests, failure injection and production logs without changing data.
