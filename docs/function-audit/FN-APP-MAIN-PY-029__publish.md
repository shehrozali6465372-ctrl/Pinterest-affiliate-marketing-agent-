# publish

- **Unique ID:** `FN-APP-MAIN-PY-029`
- **Source:** `app/main.py:681-685`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Thin API route/handler for publishing. Trace its exact delegation and authentication/idempotency contract; do not infer safety from wrapper size. It may reach the live Pinterest publishing implementation.

## Exact isolated source

```python
def publish(payload: PublishRequest) -> dict[str, object]:
    return publish_product_content(payload.product_id, payload.content_version_id)


@app.post("/learning-loop", dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob retrieved.
- `VERIFIED — LINE RANGE`: isolated by Python definition boundary.
- `UNVERIFIED — LOGIC`: complete call graph, edge cases and tests not yet proven.
- `UNVERIFIED — LIVE BEHAVIOR`: no live endpoint or Pinterest operation invoked.

## Required checks

Trace all callees and route dependencies; inspect associated tests; verify request validation, authorization, idempotency, DB transaction outcomes, Pinterest response parsing, uncertainty handling and affiliate-link preservation. Any publish-capable call must remain unexecuted in this read-only task.
