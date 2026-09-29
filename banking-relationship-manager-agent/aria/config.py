from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARIA_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="aria")
    environment: str = Field(default="dev")
    max_tool_calls: int = Field(default=8)
    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()
