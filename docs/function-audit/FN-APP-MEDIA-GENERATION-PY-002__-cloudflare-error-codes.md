# _cloudflare_error_codes

- **Unique ID:** `FN-APP-MEDIA-GENERATION-PY-002`
- **Source:** `app/media_generation.py:20-33`
- **Source blob SHA:** `e4a62e8ca628ee906bc59915810edc20e3c8f8e7`
- **Snapshot:** `main source snapshot 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Extracts Cloudflare API error codes from provider responses. Verify malformed JSON/list structures, absent codes and type conversion do not cause secondary exceptions.

## Exact isolated source

```python
def _cloudflare_error_codes(response: httpx.Response) -> list[int | str]:
    codes: list[int | str] = []
    try:
        body = response.json()
        errors = body.get("errors", []) if isinstance(body, dict) else []
        if isinstance(errors, list):
            for item in errors[:3]:
                if isinstance(item, dict) and isinstance(item.get("code"), (int, str)):
                    codes.append(item["code"])
    except ValueError:
        pass
    return codes
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION RANGE`: single definition isolated.
- `UNVERIFIED — LOGIC CORRECTNESS`: tests and call graph still require verification.
- `UNVERIFIED — LIVE BEHAVIOR`: no external provider call was executed.

## Required checks

Review all call sites, test cases, input boundaries, exception behavior, provider contracts, retry safety and secret redaction.
