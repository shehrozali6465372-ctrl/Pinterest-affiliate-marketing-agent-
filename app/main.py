"""Pinterest Affiliate Model 1 API.

External integrations only report success after real operations complete.
"""
import hmac
from contextlib import asynccontextmanager
from urllib.parse import quote, urlsplit

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
    lifespan=lifespan,
)

from app.workflow import router as workflow_router
app.include_router(workflow_router)

from app.diagnostics import router as diagnostics_router
app.include_router(diagnostics_router)

from app.learning import router as learning_router
app.include_router(learning_router)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Protect operational endpoints when APP_API_KEY is configured."""
    if not settings.app_api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


def require_configured_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Fail closed for publication-changing and operator endpoints if APP_API_KEY is missing."""
    if not settings.app_api_key:
        raise HTTPException(status_code=503, detail="API authentication is not configured.")
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
    legacy_pinterest_configured = bool(
        settings.pinterest_access_token and settings.pinterest_board_id
    )
    from app.credential_vault import token_encryption_key_is_valid

    encryption_key_valid = token_encryption_key_is_valid()
    account_workflow_configured = bool(settings.database_url and encryption_key_valid)
    credential_ingest_configured = bool(settings.pinterest_credential_ingest_key)
    return {
        "database_configured": bool(settings.database_url),
        # Backwards-compatible field: this refers only to the legacy direct-token publish route.
        "pinterest_configured": legacy_pinterest_configured,
        "pinterest_legacy_direct_configured": legacy_pinterest_configured,
        # Publishing from a stored OAuth credential needs DB + encryption; this does not prove account connection.
        "pinterest_account_workflow_configured": account_workflow_configured,
        "pinterest_token_encryption_key_valid": encryption_key_valid,
        # Hub-to-agent OAuth credential ingestion is a separate service-to-service path.
        "pinterest_credential_ingest_configured": credential_ingest_configured,
        "image_generation_configured": bool(settings.cloudflare_api_token and settings.cloudflare_account_id),
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model if settings.llm_api_key else None,
        "api_key_configured": bool(settings.app_api_key),
        "note": "Configuration presence does not prove credentials, account connection, access, or permissions are valid.",
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


class PinterestRefreshInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    client_id: str = Field(min_length=1, max_length=500)
    client_secret: str = Field(min_length=1, max_length=2000)


class PinterestOperationInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    operation: str = Field(min_length=1, max_length=50)
    payload: dict[str, object] = Field(default_factory=dict)


@app.post("/integrations/pinterest/refresh")
def refresh_pinterest_credential(
    payload: PinterestRefreshInput,
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> dict[str, object]:
    """Refresh an expired Pinterest access token using server-to-server app credentials."""
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")

    from datetime import datetime, timedelta, timezone
    import httpx
    from cryptography.exceptions import InvalidTag
    from app.credential_vault import (
        TokenEncryptionConfigurationError,
        get_pinterest_refresh_credential,
        store_pinterest_credential,
    )
    from app.database import DatabaseConfigurationError

    try:
        stored = get_pinterest_refresh_credential(payload.account_id)
    except LookupError:
        raise HTTPException(status_code=409, detail="No usable Pinterest refresh token is stored; reconnect Pinterest.") from None
    except InvalidTag:
        raise HTTPException(status_code=503, detail="Stored Pinterest refresh token failed authenticated decryption.") from None
    except TokenEncryptionConfigurationError:
        raise HTTPException(status_code=503, detail="Pinterest token encryption is not configured correctly.") from None
    except DatabaseConfigurationError:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured correctly.") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Pinterest refresh credential lookup failed.") from None

    # Avoid sending a refresh token to Pinterest after its declared expiry.
    # Null expiry remains supported for older stored credentials; malformed expiry fails closed.
    stored_refresh_expiry = stored.get("refresh_token_expires_at")
    if stored_refresh_expiry is not None:
        try:
            if not isinstance(stored_refresh_expiry, datetime):
                stored_refresh_expiry = datetime.fromisoformat(
                    str(stored_refresh_expiry).replace("Z", "+00:00")
                )
            if stored_refresh_expiry.tzinfo is None:
                stored_refresh_expiry = stored_refresh_expiry.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            raise HTTPException(
                status_code=503,
                detail="Stored Pinterest refresh-token expiry is invalid; reconnect the account.",
            ) from None
        if stored_refresh_expiry <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=409,
                detail="Stored Pinterest refresh token has expired; reconnect the account.",
            )

    try:
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = client.post(
                f"{settings.pinterest_api_base_url.rstrip('/')}/oauth/token",
                auth=(payload.client_id, payload.client_secret),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": stored["refresh_token"],
                    "continuous_refresh": "true",
                },
            )
        token_data = response.json() if response.content else {}
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Pinterest OAuth token refresh request failed.") from None

    if not response.is_success or not isinstance(token_data, dict) or not token_data.get("access_token"):
        status_code = 401 if response.status_code in (400, 401, 403) else 502
        raise HTTPException(
            status_code=status_code,
            detail="Pinterest rejected token refresh. Reconnect the account if the refresh token is invalid or expired.",
        )

    now = datetime.now(timezone.utc)
    expires_at = (
        (now + timedelta(seconds=int(token_data["expires_in"]))).isoformat()
        if token_data.get("expires_in") is not None else None
    )
    refresh_expiry = token_data.get("refresh_token_expires_at")
    if refresh_expiry is not None:
        try:
            refresh_token_expires_at = datetime.fromtimestamp(float(refresh_expiry), timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            refresh_token_expires_at = None
    elif token_data.get("refresh_token_expires_in") is not None:
        refresh_token_expires_at = (
            now + timedelta(seconds=int(token_data["refresh_token_expires_in"]))
        ).isoformat()
    else:
        # A successful refresh may omit refresh-token expiry metadata. Preserve
        # the previously stored expiry rather than reporting it as unknown.
        refresh_token_expires_at = stored.get("refresh_token_expires_at")

    try:
        saved = store_pinterest_credential({
            "account_id": stored["account_id"],
            "pinterest_user_id": stored["pinterest_user_id"],
            "username": stored.get("username") or "",
            "access_token": str(token_data["access_token"]),
            # Pinterest may omit a rotated refresh token; never erase the still-valid stored one.
            "refresh_token": str(token_data.get("refresh_token") or stored.get("refresh_token") or ""),
            "token_type": str(token_data.get("token_type") or "bearer"),
            "scope": str(token_data.get("scope") or stored.get("scope") or ""),
            "expires_at": expires_at,
            "refresh_token_expires_at": refresh_token_expires_at,
        })
    except Exception:
        raise HTTPException(status_code=503, detail="Pinterest refreshed a token but encrypted persistence could not be confirmed.") from None

    return {
        "refreshed": True,
        "account_id": saved["account_id"],
        "expires_at": saved.get("expires_at").isoformat() if saved.get("expires_at") else expires_at,
        "refresh_token_expires_at": (
            saved.get("refresh_token_expires_at").isoformat()
            if saved.get("refresh_token_expires_at")
            else refresh_token_expires_at.isoformat()
            if isinstance(refresh_token_expires_at, datetime)
            else refresh_token_expires_at
        ),
    }


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
    # Product-tag operations do not use query parameters; initialize this before
    # their early branch so the request cannot reference an unbound local.
    query = None
    if operation in {"product_tags", "add_product_tags"}:
        pin_id = str(data.get("pin_id") or "").strip()
        if not pin_id:
            raise HTTPException(status_code=400, detail="Hero Pin ID is required.")
        if operation == "product_tags":
            method, path, body = "GET", f"/pins/{quote(pin_id, safe='')}/product_tags", None
        else:
            product_pin_ids = data.get("product_pin_ids")
            if not isinstance(product_pin_ids, list) or not 1 <= len(product_pin_ids) <= 24:
                raise HTTPException(status_code=400, detail="Between 1 and 24 product Pin IDs are required.")
            if any(not isinstance(item, str) or not item.strip() for item in product_pin_ids) or len(set(product_pin_ids)) != len(product_pin_ids):
                raise HTTPException(status_code=400, detail="Product Pin IDs must be nonblank and unique.")
            method, path, body = "POST", f"/pins/{quote(pin_id, safe='')}/product_tags", {"product_tags": [{"pin_id": item.strip()} for item in product_pin_ids]}
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                response = client.request(method, f"{base}{path}", headers=headers, json=body, params=query)
            result = response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Pinterest product-tag request failed; read current tags before retrying a write.") from exc
        if not response.is_success:
            raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail="Pinterest rejected product-tag operation.")
        return {"data": result}
    allowed = {
        "account": ("GET", "/user_account", None),
        "boards": ("GET", "/boards", None),
        "list_pins": ("GET", "/pins", None),
        "create_board": ("POST", "/boards", {"name": str(data.get("name") or ""), "description": str(data.get("description") or "")}),
        "create_pin": ("POST", "/pins", {"board_id": str(data.get("board_id") or ""), "title": str(data.get("title") or ""), "description": str(data.get("description") or ""), "alt_text": str(data.get("alt_text") or ""), "media_source": {"source_type": "image_url", "url": str(data.get("image_url") or ""), "is_standard": True}, "link": str(data.get("destination_url") or "")}),
    }
    if operation == "disconnect":
        revoke_pinterest_credential(payload.account_id)
        return {"disconnected": True}
    if operation not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported Pinterest operation.")
    method, path, body = allowed[operation]
    query = None
    if operation == "list_pins":
        page_size = data.get("page_size", 100)
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
            raise HTTPException(status_code=422, detail="page_size must be an integer from 1 to 100.")
        query = {"page_size": page_size}
        bookmark = data.get("bookmark")
        if bookmark is not None:
            if not isinstance(bookmark, str) or not bookmark.strip() or len(bookmark) > 2000:
                raise HTTPException(status_code=422, detail="bookmark must be a non-empty string up to 2000 characters.")
            query["bookmark"] = bookmark
        # URL-created Product Pins may live on protected boards. Expose only
        # Pinterest's documented read filters so callers can discover them.
        for flag in ("include_protected_pins", "include_product_tag_obj"):
            if flag in data:
                if not isinstance(data[flag], bool):
                    raise HTTPException(status_code=422, detail=f"{flag} must be a boolean.")
                query[flag] = data[flag]
    if operation == "create_board" and not body["name"]:
        raise HTTPException(status_code=400, detail="Board name is required.")
    if operation == "create_pin" and not all(body.get(k) for k in ("board_id", "title", "link", "media_source")):
        raise HTTPException(status_code=400, detail="Board, title, image URL, and destination URL are required.")
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.request(method, f"{base}{path}", headers=headers, json=body, params=query)
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


class ProductTaggingInput(BaseModel):
    product_pin_ids: list[str] = Field(min_length=1, max_length=24)

    @field_validator("product_pin_ids")
    @classmethod
    def product_pin_ids_must_be_unique_and_nonblank(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("product_pin_ids must contain nonblank Pinterest product Pin IDs")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("product_pin_ids must not contain duplicates")
        return cleaned


@app.post("/publications/{publication_id}/product-tags", dependencies=[Depends(require_configured_api_key)])
def attach_product_tags_to_publication(publication_id: int, payload: ProductTaggingInput) -> dict[str, object]:
    """Attach existing Pinterest product Pins to an already-published hero Pin."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    from app.database import get_publication
    from app.credential_vault import get_pinterest_credential
    from app.pinterest import (
        PinterestProductTagError, PinterestReadError, add_product_tags_to_pin,
        get_pin_read_only, list_product_tags_read_only,
    )
    try:
        publication = get_publication(publication_id)
        if publication is None:
            raise HTTPException(status_code=404, detail="Publication not found")
        if publication.get("status") != "succeeded" or not publication.get("pinterest_pin_id"):
            raise HTTPException(status_code=409, detail="Only a confirmed successful publication can receive product tags")
        account_id = publication.get("account_id")
        board_id = publication.get("board_id")
        if not account_id or not board_id:
            raise HTTPException(status_code=409, detail="Publication lacks the account or board reference required for tagging")
        credential = get_pinterest_credential(str(account_id))
        hero_pin_id = str(publication["pinterest_pin_id"])
        hero = get_pin_read_only(pin_id=hero_pin_id, access_token=credential["access_token"])
        if str(hero.get("id")) != hero_pin_id or str(hero.get("board_id")) != str(board_id):
            raise HTTPException(status_code=409, detail="Pinterest hero Pin does not match the stored publication and board")

        existing = set(list_product_tags_read_only(pin_id=hero_pin_id, access_token=credential["access_token"]))
        requested = payload.product_pin_ids
        missing = [item for item in requested if item not in existing]
        if missing:
            add_product_tags_to_pin(pin_id=hero_pin_id, product_pin_ids=missing, access_token=credential["access_token"])
        verified = set(list_product_tags_read_only(pin_id=hero_pin_id, access_token=credential["access_token"]))
        not_verified = [item for item in requested if item not in verified]
        if not_verified:
            raise HTTPException(status_code=502, detail={"code": "product_tag_verification_incomplete", "message": "Pinterest write completed or may have completed, but read-back did not confirm every requested product tag. Inspect current tags before retrying.", "missing_product_pin_ids": not_verified})
        return {
            "tagged": True, "publication_id": publication_id, "hero_pin_id": hero_pin_id,
            "requested_product_pin_ids": requested,
            "newly_attached_product_pin_ids": missing,
            "already_attached_product_pin_ids": [item for item in requested if item in existing],
            "verified_product_pin_ids": requested,
            "verification": "read_after_write",
        }
    except HTTPException:
        raise
    except PinterestProductTagError as exc:
        status_code = 502 if exc.outcome_uncertain or exc.http_status is None or exc.http_status >= 500 else exc.http_status
        raise HTTPException(status_code=status_code, detail={"code": "pinterest_product_tag_write_failed", "message": str(exc), "outcome_uncertain": exc.outcome_uncertain, "verify_before_retry": exc.outcome_uncertain}) from exc
    except PinterestReadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Stored Pinterest account credential is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Product tagging could not be completed; inspect the hero Pin tags before retrying") from exc


@app.get("/publications/{publication_id}/product-tags", dependencies=[Depends(require_configured_api_key)])
def verify_publication_product_tags(publication_id: int) -> dict[str, object]:
    """Read-only product-tag verification for an existing publication."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    from app.database import get_publication
    from app.credential_vault import get_pinterest_credential
    from app.pinterest import PinterestReadError, get_pin_read_only, list_product_tags_read_only
    try:
        publication = get_publication(publication_id)
        if publication is None:
            raise HTTPException(status_code=404, detail="Publication not found")
        if publication.get("status") != "succeeded" or not publication.get("pinterest_pin_id"):
            raise HTTPException(status_code=409, detail="Only a confirmed successful publication can be verified")
        account_id = publication.get("account_id")
        board_id = publication.get("board_id")
        if not account_id or not board_id:
            raise HTTPException(status_code=409, detail="Publication lacks the account or board reference required for verification")
        credential = get_pinterest_credential(str(account_id))
        pin_id = str(publication["pinterest_pin_id"])
        hero = get_pin_read_only(pin_id=pin_id, access_token=credential["access_token"])
        if str(hero.get("id")) != pin_id or str(hero.get("board_id")) != str(board_id):
            raise HTTPException(status_code=409, detail="Pinterest hero Pin does not match the stored publication and board")
        tags = list_product_tags_read_only(pin_id=pin_id, access_token=credential["access_token"])
        return {"publication_id": publication_id, "hero_pin_id": pin_id, "product_pin_ids": tags, "verified": True, "read_only": True}
    except HTTPException:
        raise
    except PinterestReadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Stored Pinterest account credential is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Pinterest product-tag verification could not be completed") from exc


class PublicationReconciliationInput(BaseModel):
    outcome: str = Field(pattern=r"^(succeeded|failed)$")
    pinterest_pin_id: str | None = Field(default=None, min_length=1, max_length=200)
    operator_evidence: str = Field(min_length=12, max_length=2000)

    @field_validator("operator_evidence")
    @classmethod
    def evidence_must_be_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("operator_evidence must not be blank")
        return value


@app.get("/publications/{publication_id}", dependencies=[Depends(require_configured_api_key)])
def get_publication_status(publication_id: int) -> dict[str, object]:
    """Inspect a publication record without making any Pinterest requests."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    from app.database import get_publication
    try:
        row = get_publication(publication_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Publication status could not be read") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    for field in ("created_at", "updated_at"):
        if row.get(field) is not None:
            row[field] = row[field].isoformat()
    return row


@app.get("/publications/{publication_id}/pinterest-verification", dependencies=[Depends(require_configured_api_key)])
def verify_publication_on_pinterest(publication_id: int) -> dict[str, object]:
    """Read-only board pagination and Pin detail verification for an existing record."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    from app.database import get_publication
    from app.credential_vault import get_pinterest_credential
    from app.pinterest import PinterestReadError, get_pin_read_only, list_board_pins_read_only
    try:
        publication = get_publication(publication_id)
        if publication is None:
            raise HTTPException(status_code=404, detail="Publication not found")
        account_id = publication.get("account_id")
        board_id = publication.get("board_id")
        if not account_id or not board_id:
            raise HTTPException(status_code=409, detail="Publication lacks the account or board reference required for verification")
        credential = get_pinterest_credential(str(account_id))
        board_result = list_board_pins_read_only(board_id=str(board_id), access_token=credential["access_token"])
        pins = board_result["items"]
        expected_pin_id = publication.get("pinterest_pin_id")
        matching_pin = next((pin for pin in pins if str(pin.get("id")) == str(expected_pin_id)), None) if expected_pin_id else None
        detail = None
        if matching_pin is not None:
            detail = get_pin_read_only(pin_id=str(expected_pin_id), access_token=credential["access_token"])
        # Return only operator-relevant Pin fields; never return credential material or raw provider bodies.
        safe_pins = [{key: pin.get(key) for key in ("id", "board_id", "title", "description", "link", "created_at")} for pin in pins]
        detail_matches = bool(detail and str(detail.get("id")) == str(expected_pin_id) and str(detail.get("board_id")) == str(board_id))
        return {
            "publication_id": publication_id, "publication_status": publication.get("status"),
            "account_id": account_id, "board_id": board_id,
            "board_pages_read": board_result["pages_read"],
            "board_pins_seen": len(safe_pins), "pagination_complete": board_result["pagination_complete"],
            "stored_pin_id": expected_pin_id, "stored_pin_found_on_board": matching_pin is not None,
            "pin_detail_board_matches": detail_matches, "pins": safe_pins,
            "read_only": True,
        }
    except HTTPException:
        raise
    except PinterestReadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Stored Pinterest account credential is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Pinterest publication verification could not be completed") from exc


@app.post("/publications/{publication_id}/reconcile", dependencies=[Depends(require_configured_api_key)])
def reconcile_publication(publication_id: int, payload: PublicationReconciliationInput) -> dict[str, object]:
    """Operator-confirmed resolution of an `unknown` publish result; never publishes a Pin."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    if payload.outcome == "succeeded" and not payload.pinterest_pin_id:
        raise HTTPException(status_code=422, detail="Verified Pinterest Pin ID is required when outcome is succeeded")
    if payload.outcome == "failed" and payload.pinterest_pin_id:
        raise HTTPException(status_code=422, detail="Do not provide a Pin ID when confirming no Pin exists")
    from app.database import reconcile_unknown_publication
    try:
        row = reconcile_unknown_publication(
            publication_id, outcome=payload.outcome,
            pinterest_pin_id=payload.pinterest_pin_id,
            operator_evidence=payload.operator_evidence,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Publication not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Publication reconciliation failed; inspect the stored record before retrying") from exc
    for field in ("created_at", "updated_at"):
        if row.get(field) is not None:
            row[field] = row[field].isoformat()
    return {"reconciled": True, "published": row.get("status") == "succeeded", "publication": row}


@app.post("/products/{product_id}/content/{content_version_id}/publish", dependencies=[Depends(require_configured_api_key)])
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


@app.post("/publish", dependencies=[Depends(require_configured_api_key)])
def publish(payload: PublishRequest) -> dict[str, object]:
    return publish_product_content(payload.product_id, payload.content_version_id)


@app.post("/learning-loop", dependencies=[Depends(require_api_key)])
def learning_loop_unavailable() -> None:
    raise HTTPException(status_code=501, detail="Learning Loop is not implemented. No analytics were ingested and no model was trained.")
