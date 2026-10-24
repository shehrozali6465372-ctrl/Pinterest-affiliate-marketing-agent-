"""Server-side environment settings for the Pinterest agent."""
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
