"""Pinterest Affiliate Model 1 API.

External integrations only report success after real operations complete.
"""
import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.config import settings
from app.auth import require_api_key, require_credential_ingest_key
from app.content_generation import ContentGenerationError, PROMPT_VERSION, generate_pin_content
from app.publishing_gateway import publish_pin
from app.security_headers import SecurityHeadersMiddleware


logger = logging.getLogger(__name__)


async def _workflow_checkpoint_cleanup_loop() -> None:
    """Best-effort hourly cleanup; safe across multiple service workers."""
    from app.config import settings
    from app.database import cleanup_expired_workflow_checkpoints

    while True:
        try:
            removed = await asyncio.to_thread(
                cleanup_expired_workflow_checkpoints,
                retention_hours=settings.workflow_checkpoint_retention_hours,
            )
            if removed:
                logger.info("workflow_checkpoint_cleanup cleared_payloads=%s retention_hours=%s", removed, settings.workflow_checkpoint_retention_hours)
        except Exception as exc:
            logger.warning("workflow_checkpoint_cleanup outcome=failed exception_type=%s", type(exc).__name__)
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    cleanup_task = asyncio.create_task(_workflow_checkpoint_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
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
app.add_middleware(SecurityHeadersMiddleware)

from app.workflow import router as workflow_router
app.include_router(workflow_router)

from app.diagnostics import router as diagnostics_router
app.include_router(diagnostics_router)

from app.learning import router as learning_router
app.include_router(learning_router)

from app.trends import router as trends_router
app.include_router(trends_router)

from app.trend_visuals import router as trend_visuals_router
app.include_router(trend_visuals_router)

from app.model2_registry import router as model2_registry_router
app.include_router(model2_registry_router)

from app.model2_learning import router as model2_learning_router
app.include_router(model2_learning_router)


# Backwards-compatible name for publication-changing routes; one auth implementation.
require_configured_api_key = require_api_key


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
    # Static-token publishing has been retired; legacy env vars never enable publishing.
    legacy_pinterest_configured = False
    from app.credential_vault import token_encryption_key_is_valid

    encryption_key_valid = token_encryption_key_is_valid()
    account_workflow_configured = bool(settings.database_url and encryption_key_valid)
    credential_ingest_configured = bool(settings.pinterest_credential_ingest_key)
    return {
        "database_configured": bool(settings.database_url),
        # Backwards-compatible field: this refers only to the legacy direct-token publish route.
        "pinterest_configured": legacy_pinterest_configured,
        "pinterest_legacy_direct_configured": legacy_pinterest_configured,
        "pinterest_legacy_direct_publishing_enabled": False,
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


@app.post("/integrations/pinterest/credentials", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_credential_ingest_key)])
def ingest_pinterest_credential(
    payload: PinterestCredentialInput,
) -> dict[str, object]:
    """Accept Pinterest OAuth credentials from the trusted Modern Living Hub backend only."""
    from app.credential_vault import (
        store_pinterest_credential,
        token_encryption_key_is_valid,
    )
    if not token_encryption_key_is_valid():
        raise HTTPException(
            status_code=503,
            detail="Pinterest credential encryption is not configured or invalid.",
        )
    try:
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



class PinterestAnalyticsIntegrationInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    period_days: int = Field(default=30, ge=1, le=90)



@app.post("/integrations/pinterest/analytics/run", dependencies=[Depends(require_credential_ingest_key)])
def run_pinterest_analytics_integration(payload: PinterestAnalyticsIntegrationInput) -> dict[str, object]:
    """Run read-only Pinterest organic analytics ingestion through the trusted Hub boundary."""
    from app.learning import LearningRequest, run_learning_loop
    return run_learning_loop(LearningRequest(account_id=payload.account_id, period_days=payload.period_days))


@app.post("/integrations/pinterest/refresh", dependencies=[Depends(require_credential_ingest_key)])
def refresh_pinterest_credential(
    payload: PinterestRefreshInput,
) -> dict[str, object]:
    """Refresh an expired Pinterest access token using server-to-server app credentials."""
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
        refresh_token_expires_at = stored_refresh_expiry

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


class ManualPublishInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    board_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    image_url: HttpUrl
    destination_url: str = Field(min_length=8, max_length=4096)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()

    @field_validator("destination_url")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        parts = urlsplit(value)
        if value != value.strip() or parts.scheme.lower() not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ValueError("destination_url must be an absolute HTTP(S) URL without embedded credentials")
        return value


@app.post("/integrations/pinterest/publish-manual")
def publish_manual_pin(
    payload: ManualPublishInput,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=200),
    _: None = Depends(require_credential_ingest_key),
) -> dict[str, object]:
    """Publish a Hub-authored Pin through persisted content and the publication ledger."""
    import hashlib
    import json
    import httpx
    from app.credential_vault import get_pinterest_credential
    from app.database import persist_manual_publish_draft, begin_publish_attempt, finish_publish_attempt
    from app.pinterest import image_media_source, PinterestPublishError

    fingerprint_payload = {
        "account_id": payload.account_id, "board_id": payload.board_id,
        "title": payload.title, "description": payload.description,
        "image_url": str(payload.image_url), "destination_url": payload.destination_url,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    try:
        credential = get_pinterest_credential(payload.account_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected.") from None
    except Exception:
        # Vault configuration, decryption, and DB errors must fail closed without
        # exposing internal details or reaching Pinterest.
        raise HTTPException(status_code=503, detail="Pinterest credential is temporarily unavailable; no Pin publish request was sent.") from None
    token = credential["access_token"]
    try:
        media_source = image_media_source(str(payload.image_url))
    except PinterestPublishError as exc:
        raise HTTPException(status_code=422, detail="Image media source is invalid; no Pin publish request was sent.") from None
    except Exception:
        raise HTTPException(status_code=422, detail="Image media source could not be prepared; no Pin publish request was sent.") from None
    base = settings.pinterest_api_base_url.rstrip("/")

    # Verify account and board ownership before persisting or reserving a publish.
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=8.0)) as client:
            account_response = client.get(f"{base}/user_account", headers={"Authorization": f"Bearer {token}"})
            if not account_response.is_success:
                raise HTTPException(status_code=401 if account_response.status_code in (401, 403) else 502, detail="Stored Pinterest account could not be verified.")
            account_data = account_response.json()
            actual_user_id = account_data.get("id") if isinstance(account_data, dict) else None
            expected_user_id = credential.get("pinterest_user_id")
            expected_account_id = f"pinterest:{expected_user_id}" if expected_user_id else None
            if (not isinstance(actual_user_id, (str, int))
                    or str(actual_user_id) != str(expected_user_id or "")
                    or payload.account_id != expected_account_id):
                raise HTTPException(status_code=409, detail="Stored Pinterest credential identity does not match the requested account; no Pin publish request was sent.")
            boards_response = client.get(f"{base}/boards?page_size=100", headers={"Authorization": f"Bearer {token}"})
            if not boards_response.is_success:
                raise HTTPException(status_code=502, detail="Could not verify the selected Pinterest board.")
            boards_data = boards_response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Pinterest preflight failed; no Pin publish request was sent.") from None
    board_items = boards_data.get("items", []) if isinstance(boards_data, dict) else []
    bookmark = boards_data.get("bookmark") if isinstance(boards_data, dict) else None
    seen_bookmarks: set[str] = set()
    board_found = any(isinstance(item, dict) and str(item.get("id")) == payload.board_id for item in board_items)
    # Pinterest boards are paginated; don't reject a valid board just because it
    # isn't in the first 100. Stop on repeated cursors or a conservative page cap.
    pagination_limited = False
    for page_number in range(99):
        if board_found or not isinstance(bookmark, str) or not bookmark or bookmark in seen_bookmarks:
            break
        if page_number == 98:
            pagination_limited = True
        seen_bookmarks.add(bookmark)
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=8.0)) as client:
                page_response = client.get(
                    f"{base}/boards",
                    params={"page_size": 100, "bookmark": bookmark},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if not page_response.is_success:
                raise HTTPException(status_code=502, detail="Could not verify the selected Pinterest board across pages.")
            page_data = page_response.json()
        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError):
            raise HTTPException(status_code=502, detail="Pinterest board pagination failed; no Pin publish request was sent.") from None
        page_items = page_data.get("items", []) if isinstance(page_data, dict) else []
        board_found = any(isinstance(item, dict) and str(item.get("id")) == payload.board_id for item in page_items)
        bookmark = page_data.get("bookmark") if isinstance(page_data, dict) else None
    if not board_found and pagination_limited and isinstance(bookmark, str) and bookmark:
        raise HTTPException(status_code=503, detail="Pinterest board list exceeded the safe verification limit; no Pin publish request was sent.")
    if not board_found:
        raise HTTPException(status_code=422, detail="Selected board does not belong to the connected Pinterest account or was not found.")

    try:
        product, content, created = persist_manual_publish_draft(
            title=payload.title, description=payload.description,
            image_url=str(payload.image_url), affiliate_url=payload.destination_url,
            idempotency_key=idempotency_key, request_fingerprint=fingerprint,
        )
    except ValueError as exc:
        if str(exc) == "idempotency_key_payload_mismatch":
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with different Pin data.") from None
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Could not persist or recover the manual Pin draft; no Pin publish request was sent.") from None

    result = publish_pin(
        product_id=product["id"], content_version_id=content["id"],
        board_id=payload.board_id, account_id=payload.account_id,
        access_token=token, title=payload.title, description=payload.description,
        alt_text="", media_source=media_source,
        destination_url=payload.destination_url,
    )
    return {**result, "draft_created": created}



@app.post("/integrations/pinterest/operation", dependencies=[Depends(require_credential_ingest_key)])
def pinterest_account_operation(
    payload: PinterestOperationInput,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    """Execute a bounded Pinterest API operation using an encrypted Neon credential."""
    from app.credential_vault import get_pinterest_credential, revoke_pinterest_credential
    import httpx
    import hashlib
    import json
    operation = payload.operation
    data = payload.payload
    allowed = {
        "account": ("GET", "/user_account", None),
        "boards": ("GET", "/boards?page_size=100", None),
        "create_board": ("POST", "/boards", {"name": str(data.get("name") or ""), "description": str(data.get("description") or "")}),
    }
    if operation == "disconnect":
        try:
            revoke_pinterest_credential(payload.account_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Pinterest account is not connected.") from None
        except ValueError:
            raise HTTPException(status_code=409, detail="Stored Pinterest credential identity is invalid; disconnect was not applied.") from None
        except Exception:
            raise HTTPException(status_code=503, detail="Pinterest credential could not be safely disconnected.") from None
        return {"disconnected": True}
    if operation not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported Pinterest operation.")
    try:
        credential = get_pinterest_credential(payload.account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected.") from exc
    base = settings.pinterest_api_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {credential['access_token']}", "Content-Type": "application/json"}
    method, path, body = allowed[operation]
    if operation == "create_board" and not body["name"]:
        raise HTTPException(status_code=400, detail="Board name is required.")
    if operation == "create_board" and not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key is required for create_board.")
    expected_user_id = str(credential.get("pinterest_user_id") or "")
    if not expected_user_id or payload.account_id != f"pinterest:{expected_user_id}":
        raise HTTPException(status_code=409, detail="Stored Pinterest credential identity does not match the requested account.")
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            identity_response = client.get(f"{base}/user_account", headers=headers)
            if not identity_response.is_success:
                raise HTTPException(
                    status_code=401 if identity_response.status_code in (401, 403) else 502,
                    detail="Stored Pinterest account could not be verified; operation was not sent.",
                )
            identity_data = identity_response.json()
            actual_user_id = identity_data.get("id") if isinstance(identity_data, dict) else None
            if not isinstance(actual_user_id, (str, int)) or str(actual_user_id) != expected_user_id:
                raise HTTPException(
                    status_code=409,
                    detail="Pinterest token identity does not match the requested account; operation was not sent.",
                )
            if operation == "create_board":
                fingerprint = hashlib.sha256(json.dumps(
                    {"account_id": payload.account_id, "name": body["name"],
                     "description": body["description"]},
                    sort_keys=True, separators=(",", ":"),
                ).encode()).hexdigest()
                from app.database import (
                    claim_pinterest_board_operation,
                    complete_pinterest_board_operation,
                    mark_pinterest_board_operation_failed,
                    mark_pinterest_board_operation_uncertain,
                )
                try:
                    claim = claim_pinterest_board_operation(
                        account_id=payload.account_id,
                        idempotency_key=idempotency_key,
                        request_fingerprint=fingerprint,
                    )
                except ValueError as exc:
                    if str(exc) == "idempotency_key_payload_mismatch":
                        raise HTTPException(status_code=409, detail="Idempotency-Key was already used with different board data.") from None
                    raise
                except Exception:
                    raise HTTPException(status_code=503, detail="Board operation ledger is unavailable; Pinterest write was not sent.") from None
                if claim["status"] == "succeeded":
                    return {"data": claim["result"], "replayed": True}
                if claim["status"] in {"uncertain", "in_progress"}:
                    raise HTTPException(status_code=409, detail="Board creation outcome is uncertain or still in progress; automatic retry is blocked pending reconciliation.")
                if claim["status"] == "failed":
                    raise HTTPException(status_code=409, detail="This board operation was previously rejected; use a new reviewed operation after resolving the rejection.")
            response = client.request(method, f"{base}{path}", headers=headers, json=body)
        try:
            result = response.json() if response.content else {}
        except ValueError:
            if operation == "create_board":
                mark_pinterest_board_operation_uncertain(account_id=payload.account_id, idempotency_key=idempotency_key)
                raise HTTPException(status_code=502, detail="Pinterest board response was unreadable; outcome marked uncertain and will not be retried.") from None
            raise HTTPException(status_code=502, detail="Pinterest API returned an unreadable response.") from None
    except httpx.HTTPError as exc:
        if operation == "create_board":
            try:
                mark_pinterest_board_operation_uncertain(account_id=payload.account_id, idempotency_key=idempotency_key)
            except Exception:
                # The durable in_progress row itself blocks another provider POST.
                pass
            raise HTTPException(status_code=502, detail="Pinterest board request outcome is uncertain; automatic retry is blocked.") from None
        raise HTTPException(status_code=502, detail="Pinterest API request failed.") from exc
    if not response.is_success:
        if operation == "create_board":
            try:
                if response.status_code < 500:
                    mark_pinterest_board_operation_failed(account_id=payload.account_id, idempotency_key=idempotency_key)
                else:
                    mark_pinterest_board_operation_uncertain(account_id=payload.account_id, idempotency_key=idempotency_key)
            except Exception:
                pass
            if response.status_code >= 500:
                raise HTTPException(status_code=502, detail="Pinterest board response is ambiguous; automatic retry is blocked.")
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail="Pinterest API rejected or could not complete the operation.")
    if operation == "create_board":
        try:
            complete_pinterest_board_operation(
                account_id=payload.account_id, idempotency_key=idempotency_key, result=result,
            )
        except Exception:
            try:
                mark_pinterest_board_operation_uncertain(account_id=payload.account_id, idempotency_key=idempotency_key)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail="Pinterest may have created the board, but durable success could not be confirmed; automatic retry is blocked.") from None
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
    """Verify a stored successful Pin by reading every board page and its Pin detail."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    from app.database import get_publication
    from app.credential_vault import get_pinterest_credential_read_only
    from app.pinterest import PinterestReadError, get_pin_read_only, list_board_pins_read_only
    try:
        publication = get_publication(publication_id)
        if publication is None:
            raise HTTPException(status_code=404, detail="Publication not found")
        if publication.get("status") != "succeeded" or not publication.get("pinterest_pin_id"):
            raise HTTPException(status_code=409, detail="Only a confirmed successful publication can be verified")
        if not publication.get("account_id") or not publication.get("board_id"):
            raise HTTPException(status_code=409, detail="Publication is missing account or board ownership metadata")
        credential = get_pinterest_credential_read_only(publication["account_id"])
        token = credential["access_token"]
        board = list_board_pins_read_only(board_id=str(publication["board_id"]), access_token=token)
        pin = get_pin_read_only(pin_id=str(publication["pinterest_pin_id"]), access_token=token)
    except HTTPException:
        raise
    except LookupError:
        raise HTTPException(status_code=409, detail="Pinterest account is not connected in Neon") from None
    except PinterestReadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=503, detail="Read-only Pinterest verification could not be completed") from None
    pin_id = str(publication["pinterest_pin_id"])
    return {
        "publication_id": publication_id,
        "pinterest_pin_id": pin_id,
        "pagination_complete": bool(board.get("pagination_complete")),
        "board_pages_read": board.get("pages_read", 0),
        "stored_pin_found_on_board": any(
            isinstance(item, dict) and str(item.get("id")) == pin_id
            for item in board.get("items", []) if isinstance(board.get("items"), list)
        ),
        "pin_detail_board_matches": str(pin.get("board_id")) == str(publication["board_id"]),
        "read_only": True,
    }


@app.post("/publications/{publication_id}/reconcile", dependencies=[Depends(require_configured_api_key)])
def reconcile_publication(publication_id: int, payload: PublicationReconciliationInput) -> dict[str, object]:
    """Operator-confirmed resolution of an unknown or stale pending publish; never publishes a Pin."""
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
    """Retired legacy route: static-token publishing is intentionally disabled."""
    if product_id <= 0 or content_version_id <= 0:
        raise HTTPException(status_code=422, detail="product_id and content_version_id must be positive integers")
    raise HTTPException(
        status_code=410,
        detail="Legacy publishing is disabled. Use the account-scoped encrypted-credential publishing integration.",
    )


@app.post("/publish", dependencies=[Depends(require_configured_api_key)])
def publish(payload: PublishRequest) -> dict[str, object]:
    return publish_product_content(payload.product_id, payload.content_version_id)


@app.post("/learning-loop", dependencies=[Depends(require_api_key)])
def learning_loop_unavailable() -> None:
    raise HTTPException(status_code=501, detail="Learning Loop is not implemented. No analytics were ingested and no model was trained.")


from app.affiliate_scheduler import router as affiliate_scheduler_router
app.include_router(affiliate_scheduler_router)


from app.dashboard import router as dashboard_router
app.include_router(dashboard_router)
