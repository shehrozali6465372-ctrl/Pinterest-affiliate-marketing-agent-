"""Server-side environment settings for the Pinterest agent."""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import unicodedata


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
    cloudflare_image_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    workflow_checkpoint_retention_hours: int = Field(default=72, ge=1, le=720)
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
