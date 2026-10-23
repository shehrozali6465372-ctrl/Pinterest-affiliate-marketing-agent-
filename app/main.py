"""Pinterest Affiliate Model 1 API scaffold.

This module intentionally does not fake AI generation, publishing, analytics, or ML.
Those capabilities will only be enabled after real provider integrations are configured.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str | None = None
    pinterest_access_token: str | None = None
    pinterest_board_id: str | None = None
    pinterest_api_base_url: str = "https://api.pinterest.com/v5"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None


settings = Settings()
app = FastAPI(title="Pinterest Affiliate Marketing Agent", version="1.0.0")


class ProductInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    product_details: str = Field(min_length=1, max_length=10000)
    image_url: HttpUrl
    affiliate_url: HttpUrl


@app.get("/health")
def health() -> dict[str, str]:
    """Health check only; it does not imply external integrations are ready."""
    return {"status": "ok", "service": "pinterest-affiliate-model-1"}


@app.get("/readiness")
def readiness() -> dict[str, object]:
    """Report configuration presence without exposing secrets."""
    return {
        "database_configured": bool(settings.database_url),
        "pinterest_configured": bool(
            settings.pinterest_access_token and settings.pinterest_board_id
        ),
        "llm_configured": bool(
            settings.llm_api_key and settings.llm_base_url and settings.llm_model
        ),
        "note": "Configuration presence does not prove credentials or permissions are valid.",
    }


@app.post("/products/validate")
def validate_product(product: ProductInput) -> dict[str, object]:
    """Validate supplied product fields without pretending to persist or generate content."""
    return {
        "valid": True,
        "product_name": product.product_name,
        "image_url": str(product.image_url),
        "affiliate_url": str(product.affiliate_url),
        "next_step": "Persistence and real content generation are not implemented yet.",
    }


@app.post("/publish")
def publish_unavailable() -> None:
    """Publishing stays unavailable until a real authorized Pinterest client is implemented."""
    raise HTTPException(
        status_code=501,
        detail="Pinterest publishing is not implemented. No Pin was published.",
    )


@app.post("/learning-loop")
def learning_loop_unavailable() -> None:
    """Learning stays unavailable until real analytics ingestion and evaluation exist."""
    raise HTTPException(
        status_code=501,
        detail="Learning Loop is not implemented. No analytics were ingested and no model was trained.",
    )
