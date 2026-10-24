"""Pinterest Affiliate Model 1 API.

External integrations only report success after real operations complete.
"""
import hmac
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.config import settings
from app.content_generation import ContentGenerationError, PROMPT_VERSION, generate_pin_content
from app.pinterest import PinterestPublishError, publish_image_pin


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    try:
        from app.database import close_pool
        close_pool()
    except Exception:
        pass


app = FastAPI(
    title="Pinterest Affiliate Marketing Agent",
    version="1.4.1",
    description="Model 1: USA Home Decor & Kitchen affiliate Pin workflow.",
)

from app.workflow import router as workflow_router
app.include_router(workflow_router)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Protect operational endpoints when APP_API_KEY is configured."""
    if not settings.app_api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


class ProductInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    product_details: str = Field(min_length=1, max_length=10000)
    image_url: HttpUrl
    # Keep affiliate URL as raw text so validation does not rewrite tracking parameters.
    affiliate_url: str = Field(min_length=8, max_length=4096)

    @field_validator("product_name", "product_details")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("affiliate_url")
    @classmethod
    def validate_affiliate_url_without_rewriting(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("affiliate_url must not contain leading or trailing whitespace")
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            raise ValueError("affiliate_url must be an absolute HTTP(S) URL")
        if parts.username or parts.password:
            raise ValueError("affiliate_url must not contain embedded credentials")
        return value


class PinterestCredentialInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    pinterest_user_id: str = Field(min_length=1, max_length=200)
    username: str = Field(default="", max_length=200)
    access_token: str = Field(min_length=1, max_length=10000)
    refresh_token: str = Field(default="", max_length=10000)
    token_type: str = Field(default="bearer", max_length=100)
    scope: str = Field(default="", max_length=2000)
    expires_at: str | None = None
    refresh_token_expires_at: str | None = None


class PublishRequest(BaseModel):
    product_id: int = Field(gt=0)
    content_version_id: int = Field(gt=0)


def _serialize_row(row: dict) -> dict[str, object]:
    result = dict(row)
    created_at = result.get("created_at")
    if created_at:
        result["created_at"] = created_at.isoformat()
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pinterest-affiliate-model-1"}


@app.get("/readiness", dependencies=[Depends(require_api_key)])
def readiness() -> dict[str, object]:
    return {
        "database_configured": bool(settings.database_url),
        "pinterest_configured": bool(settings.pinterest_access_token and settings.pinterest_board_id),
        "image_generation_configured": bool(settings.cloudflare_api_token and settings.cloudflare_account_id),
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model if settings.llm_api_key else None,
        "api_key_configured": bool(settings.app_api_key),
        "note": "Configuration presence does not prove credentials, access, or permissions are valid.",
    }


@app.get("/diagnostics/providers", dependencies=[Depends(require_api_key)])
def provider_diagnostics() -> dict[str, object]:
    """Check provider credentials with non-generation requests; never return secrets."""
    import httpx

    result: dict[str, object] = {
        "deepseek": {"configured": bool(settings.llm_api_key), "verified": False},
        "cloudflare": {
            "token_configured": bool(settings.cloudflare_api_token),
            "account_id_configured": bool(settings.cloudflare_account_id),
            "verified": False,
        },
        "note": "Credential/API access check only. This endpoint does not generate an image or billable LLM completion.",
    }
    timeout = httpx.Timeout(12.0, connect=5.0)

    if settings.llm_api_key:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(
                    f"{settings.llm_base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                )
            result["deepseek"] = {
                "configured": True,
                "verified": response.is_success,
                "http_status": response.status_code,
                "check": "models_endpoint",
            }
        except httpx.HTTPError:
            result["deepseek"] = {
                "configured": True,
                "verified": False,
                "error": "provider_unreachable_or_request_failed",
            }

    if settings.cloudflare_api_token and settings.cloudflare_account_id:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(
                    "https://api.cloudflare.com/client/v4/accounts/"
                    f"{settings.cloudflare_account_id}/ai/models/search",
                    headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
                    params={"per_page": 1},
                )
            result["cloudflare"] = {
                "token_configured": True,
                "account_id_configured": True,
                "verified": response.is_success,
                "http_status": response.status_code,
                "check": "workers_ai_models_endpoint",
            }
        except httpx.HTTPError:
            result["cloudflare"] = {
                "token_configured": True,
                "account_id_configured": True,
                "verified": False,
                "error": "provider_unreachable_or_request_failed",
            }

    return result


@app.post("/integrations/pinterest/credentials", status_code=status.HTTP_201_CREATED)
def ingest_pinterest_credential(
    payload: PinterestCredentialInput,
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> dict[str, object]:
    """Accept Pinterest OAuth credentials from the trusted Modern Living Hub backend only."""
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")
    if not settings.pinterest_token_encryption_key:
        raise HTTPException(status_code=503, detail="Pinterest credential encryption is not configured.")
    try:
        from app.credential_vault import store_pinterest_credential
        saved = store_pinterest_credential(payload.model_dump())
        return {
            "stored": True,
            "account_id": saved["account_id"],
            "pinterest_user_id": saved["pinterest_user_id"],
            "status": saved["status"],
            "updated_at": saved["updated_at"].isoformat() if saved.get("updated_at") else None,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Credential storage failed; no token values were returned.") from exc


class PinterestOperationInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    operation: str = Field(min_length=1, max_length=50)
    payload: dict[str, object] = Field(default_factory=dict)


@app.post("/integrations/pinterest/operation")
def pinterest_account_operation(
    payload: PinterestOperationInput,
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> dict[str, object]:
    """Execute a bounded Pinterest API operation using an encrypted Neon credential."""
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")
    from app.credential_vault import get_pinterest_credential, revoke_pinterest_credential
    import httpx
    try:
        credential = get_pinterest_credential(payload.account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected.") from exc
    operation = payload.operation
    data = payload.payload
    base = settings.pinterest_api_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {credential['access_token']}", "Content-Type": "application/json"}
    allowed = {
        "account": ("GET", "/user_account", None),
        "boards": ("GET", "/boards?page_size=100", None),
        "create_board": ("POST", "/boards", {"name": str(data.get("name") or ""), "description": str(data.get("description") or "")}),
        "create_pin": ("POST", "/pins", {"board_id": str(data.get("board_id") or ""), "title": str(data.get("title") or ""), "description": str(data.get("description") or ""), "alt_text": str(data.get("alt_text") or ""), "media_source": {"source_type": "image_url", "url": str(data.get("image_url") or ""), "is_standard": True}, "link": str(data.get("destination_url") or "")}),
    }
    if operation == "disconnect":
        revoke_pinterest_credential(payload.account_id)
        return {"disconnected": True}
    if operation not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported Pinterest operation.")
    method, path, body = allowed[operation]
    if operation == "create_board" and not body["name"]:
        raise HTTPException(status_code=400, detail="Board name is required.")
    if operation == "create_pin" and not all(body.get(k) for k in ("board_id", "title", "link", "media_source")):
        raise HTTPException(status_code=400, detail="Board, title, image URL, and destination URL are required.")
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.request(method, f"{base}{path}", headers=headers, json=body)
        result = response.json() if response.content else {}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Pinterest API request failed.") from exc
    if not response.is_success:
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail="Pinterest API rejected or could not complete the operation.")
    return {"data": result}


@app.post("/products/validate", dependencies=[Depends(require_api_key)])
def validate_product(product: ProductInput) -> dict[str, object]:
    return {
        "valid": True,
        "product_name": product.product_name,
        "image_url": str(product.image_url),
        "affiliate_url": product.affiliate_url,
        "next_step": "Validation only; this endpoint does not persist the product.",
    }


@app.post("/products", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_product(product: ProductInput) -> dict[str, object]:
    try:
        from app.database import create_product as save_product
        row = save_product(
            product_name=product.product_name,
            product_details=product.product_details,
            image_url=str(product.image_url),
            affiliate_url=product.affiliate_url,
        )
        return _serialize_row(row)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Product persistence is unavailable. Apply database migrations and check database connectivity.") from exc


@app.get("/products/{product_id}", dependencies=[Depends(require_api_key)])
def read_product(product_id: int) -> dict[str, object]:
    if product_id <= 0:
        raise HTTPException(status_code=422, detail="product_id must be a positive integer")
    try:
        from app.database import get_product as fetch_product
        row = fetch_product(product_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Product persistence is unavailable. Check database connectivity and schema setup.") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_row(row)


@app.post("/products/{product_id}/content", dependencies=[Depends(require_api_key)])
def generate_product_content(product_id: int) -> dict[str, object]:
    if product_id <= 0:
        raise HTTPException(status_code=422, detail="product_id must be a positive integer")
    try:
        from app.database import create_content_version, get_product as fetch_product
        product = fetch_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        generated, model_id = generate_pin_content(
            product_name=product["product_name"],
            product_details=product["product_details"],
            image_url=product["image_url"],
        )
        row = create_content_version(
            product_id=product_id,
            provider="deepseek",
            model_id=model_id,
            prompt_version=PROMPT_VERSION,
            pin_idea=generated.pin_idea,
            title=generated.title,
            description=generated.description,
            alt_text=generated.alt_text,
        )
        return _serialize_row(row)
    except HTTPException:
        raise
    except ContentGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Content generation or persistence failed. Check database and provider configuration.") from exc


@app.get("/products/{product_id}/content", dependencies=[Depends(require_api_key)])
def list_product_content(product_id: int) -> dict[str, object]:
    if product_id <= 0:
        raise HTTPException(status_code=422, detail="product_id must be a positive integer")
    try:
        from app.database import get_product as fetch_product, list_content_versions
        if fetch_product(product_id) is None:
            raise HTTPException(status_code=404, detail="Product not found")
        rows = list_content_versions(product_id)
        return {"product_id": product_id, "versions": [_serialize_row(row) for row in rows]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Content history is unavailable. Check database migrations and connectivity.") from exc


@app.post("/products/{product_id}/content/{content_version_id}/publish", dependencies=[Depends(require_api_key)])
def publish_product_content(product_id: int, content_version_id: int) -> dict[str, object]:
    if product_id <= 0 or content_version_id <= 0:
        raise HTTPException(status_code=422, detail="product_id and content_version_id must be positive integers")
    if not settings.pinterest_access_token or not settings.pinterest_board_id:
        raise HTTPException(status_code=503, detail="Pinterest access token and board ID must be configured before publishing.")

    from app.database import begin_publish_attempt, finish_publish_attempt, get_content_version, get_product as fetch_product
    try:
        product = fetch_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        content = get_content_version(product_id, content_version_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Content version not found")

        attempt = begin_publish_attempt(product_id=product_id, content_version_id=content_version_id, board_id=settings.pinterest_board_id)
        if attempt.get("blocked"):
            if attempt["status"] == "succeeded":
                return {"published": True, "already_published": True, "pin_id": attempt["pinterest_pin_id"], "publication_id": attempt["id"]}
            raise HTTPException(status_code=409, detail="Previous publish attempt is pending or uncertain. Check Pinterest before retrying.")

        try:
            actual = publish_image_pin(
                board_id=settings.pinterest_board_id,
                title=content["title"],
                description=content["description"],
                alt_text=content["alt_text"],
                image_url=product["image_url"],
                affiliate_url=product["affiliate_url"],
            )
        except PinterestPublishError as exc:
            outcome = "unknown" if exc.outcome_uncertain else "failed"
            finish_publish_attempt(attempt["id"], status=outcome, http_status=exc.http_status, error_code=exc.error_code, response_metadata={})
            if exc.outcome_uncertain:
                raise HTTPException(status_code=502, detail="Pinterest publish outcome is uncertain. Automatic retry is blocked; verify the board before retrying.") from exc
            raise HTTPException(status_code=502, detail="Pinterest rejected the request. No successful Pin creation was confirmed.") from exc

        saved = finish_publish_attempt(
            attempt["id"],
            status="succeeded",
            pinterest_pin_id=str(actual["pin_id"]),
            http_status=int(actual["http_status"]),
            response_metadata=actual["metadata"],
        )
        return {"published": True, "already_published": False, "pin_id": saved["pinterest_pin_id"], "publication_id": saved["id"], "http_status": saved["http_status"]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Publish request could not be fully recorded. Inspect publication record and Pinterest board before retrying.") from exc


@app.post("/publish", dependencies=[Depends(require_api_key)])
def publish(payload: PublishRequest) -> dict[str, object]:
    return publish_product_content(payload.product_id, payload.content_version_id)


@app.post("/learning-loop", dependencies=[Depends(require_api_key)])
def learning_loop_unavailable() -> None:
    raise HTTPException(status_code=501, detail="Learning Loop is not implemented. No analytics were ingested and no model was trained.")
