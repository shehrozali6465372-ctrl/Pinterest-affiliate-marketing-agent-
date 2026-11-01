# _cipher

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-002`
- **Source:** `app/credential_vault.py:18-30`
- **Source blob SHA:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

Constructs the authenticated-encryption cipher from configured key material. Verify key decoding/length validation, AES-GCM usage, failure behavior and that no plaintext key/token is logged.

## Exact isolated source

```python
def _cipher() -> AESGCM:
    encoded = settings.pinterest_token_encryption_key
    if not encoded:
        raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEY is not configured")
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEY must be base64-encoded 32-byte key") from exc
    if len(key) != 32:
        raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return AESGCM(key)


```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current main source blob.
- `VERIFIED — LINE RANGE`: source lines isolated as a single definition.
- `UNVERIFIED — LOGIC`: caller/callee, tests, concurrency and failure behavior remain to be proven.
- `UNVERIFIED — LIVE DATABASE`: no production DB writes or state transitions executed.

## Remaining evidence

Review all call sites, SQL schema/migrations, transaction boundaries, integration tests, race-condition tests, failure injection and production logs without changing data.
