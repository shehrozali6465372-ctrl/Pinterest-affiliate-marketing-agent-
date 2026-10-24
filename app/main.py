"""Pinterest Affiliate Model 1 API.

External integrations only report success after real operations complete.
"""
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
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


settings = Settings()


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
    version="1.2.0",
    description="Model 1: USA Home Decor & Kitchen affiliate Pin workflow.",
    lifespan=lifespan,
)


class ProductInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    product_details: str = Field(min_length=1, max_length=10000)
    image_url: HttpUrl
    # Keep affiliate URL as raw text so Pydantic cannot normalize its tracking parameters.
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


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check only; does not prove integrations are ready."""
    return {"status": "ok", "service": "pinterest-affiliate-model-1"}


@app.get("/readiness")
def readiness() -> dict[str, object]:
    """Report configuration presence without exposing secrets or asserting validity."""
    return {
        "database_configured": bool(settings.database_url),
        "pinterest_configured": bool(settings.pinterest_access_token and settings.pinterest_board_id),
        "image_generation_configured": bool(settings.cloudflare_api_token and settings.cloudflare_account_id),
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model if settings.llm_api_key else None,
        "note": "Configuration presence does not prove credentials, access, or permissions are valid.",
    }


@app.post("/products/validate")
def validate_product(product: ProductInput) -> dict[str, object]:
    """Validate input without persisting it or pretending to generate content."""
    return {
        "valid": True,
        "product_name": product.product_name,
        "image_url": str(product.image_url),
        "affiliate_url": product.affiliate_url,
        "next_step": "Validation only; this endpoint does not persist the product.",
    }


@app.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(product: ProductInput) -> dict[str, object]:
    """Persist supplied product information in PostgreSQL."""
    try:
        from app.database import create_product as save_product
        row = save_product(
            product_name=product.product_name,
            product_details=product.product_details,
            image_url=str(product.image_url),
            affiliate_url=product.affiliate_url,
        )
        return {
            "id": row["id"],
            "product_name": row["product_name"],
            "product_details": row["product_details"],
            "image_url": row["image_url"],
            "affiliate_url": row["affiliate_url"],
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Product persistence is unavailable. Apply database migrations and check database connectivity.") from exc


@app.get("/products/{product_id}")
def read_product(product_id: int) -> dict[str, object]:
    """Retrieve persisted product intake."""
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
    return {
        "id": row["id"],
        "product_name": row["product_name"],
        "product_details": row["product_details"],
        "image_url": row["image_url"],
        "affiliate_url": row["affiliate_url"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@app.post("/publish")
def publish_unavailable() -> None:
    """Publishing remains unavailable until a real authorized Pinterest client is implemented."""
    raise HTTPException(status_code=501, detail="Pinterest publishing is not implemented. No Pin was published.")


@app.post("/learning-loop")
def learning_loop_unavailable() -> None:
    """Learning remains unavailable until real analytics ingestion and evaluation exist."""
    raise HTTPException(status_code=501, detail="Learning Loop is not implemented. No analytics were ingested and no model was trained.")
