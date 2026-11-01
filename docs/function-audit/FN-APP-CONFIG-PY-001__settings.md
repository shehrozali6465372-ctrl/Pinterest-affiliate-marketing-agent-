# Settings

- **Unique ID:** `FN-APP-CONFIG-PY-001`
- **Definition type:** `class`
- **Source:** `app/config.py:7-33`
- **Source blob SHA:** `71805b65766c198a428f5418bd2eec5b7f74953f`
- **Repository snapshot:** `main@336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic overview

Defines a model, settings container, or exception type. Inspect inheritance, fields, defaults, constraints and configuration. Each nested method/validator is separately recorded.

## Inputs, outputs and failure paths

The exact signature, annotations, defaults, validators, return statements, and raises are shown in the source below. Caller-side assumptions and undocumented provider behavior are not treated as facts.

## Exact isolated source

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_api_key: str | None = None
    database_url: str | None = None
    pinterest_access_token: str | None = None
    pinterest_board_id: str | None = None
    pinterest_api_base_url: str = "https://api.pinterest.com/v5"
    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_image_model: str = "@cf/black-forest-labs/flux-1-schnell"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    pinterest_credential_ingest_key: str | None = None
    pinterest_token_encryption_key: str | None = None

    @field_validator("llm_api_key", "cloudflare_api_token", "app_api_key", mode="before")
    @classmethod
    def clean_secret_values(cls, value: str | None) -> str | None:
        """Remove invisible Unicode formatting characters accidentally pasted into secrets."""
        if value is None:
            return None
        return "".join(ch for ch in value if unicodedata.category(ch) != "Cf").strip()


settings = Settings()
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed against the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: adjacent/nested definitions are separated by indentation boundary.
- `UNVERIFIED — LOGIC CORRECTNESS`: not yet proven.
- `UNVERIFIED — TEST COVERAGE`: tests and assertions still require mapping/review.
- `UNVERIFIED — LIVE BEHAVIOR`: no runtime or provider claim is made.

## Required next checks

1. Trace direct callers and relevant dependencies.
2. Explain every statement, branch, loop, return and exception path.
3. Inspect tests and map assertions to behavior, including failure and boundary cases.
4. Review concurrency, retries, database transactions and security invariants where relevant.
5. Check the actual external API contract and side effects.
6. No production writes, credential changes, deployments or Pinterest publishing during this audit.
