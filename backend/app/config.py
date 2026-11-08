from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_provider: Literal["claude", "openai"] = "claude"
    claude_model: str = "claude-sonnet-5-5"
    openai_model: str = ""
    free_runs_per_day: int = 3
    max_free_runs_total_per_day: int = 100
    max_upload_mb: int = 5
    max_text_chars: int = 30000
    max_context_chars: int = 2000
    max_body_kb: int = 1024
    allowed_origins: list[str] = ["http://localhost:5173"]
    # Set only when running behind a proxy that appends X-Forwarded-For (e.g. Render).
    trust_proxy: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
