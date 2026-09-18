from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_db: str = 'arena'
    postgres_user: str = 'arena'
    postgres_password: str = ''
    ai_provider: Literal['mock', 'compatible'] = 'mock'
    ai_base_url: str = 'https://your-provider.example/v1'
    ai_api_key: str = ''
    ai_model: str = ''
    ai_timeout_seconds: float = Field(default=30, gt=0)
    history_retention_days: int = Field(default=7, ge=0)
    session_retention_days: int = Field(default=30, ge=0)
    active_session_idle_days: int = Field(default=30, ge=1)
    retention_interval_seconds: int = Field(default=3600, ge=60)

    @model_validator(mode='after')
    def validate_settings(self):
        if self.session_retention_days < self.history_retention_days:
            raise ValueError('SESSION_RETENTION_DAYS must be >= HISTORY_RETENTION_DAYS')
        if self.ai_provider == 'compatible' and not (self.ai_api_key and self.ai_model):
            raise ValueError('Compatible AI requires AI_API_KEY and AI_MODEL')
        return self

    @property
    def database_url(self) -> URL:
        return URL.create('postgresql+psycopg', username=self.postgres_user,
                          password=self.postgres_password, host=self.postgres_host,
                          port=self.postgres_port, database=self.postgres_db)


@lru_cache
def get_settings() -> Settings:
    return Settings()
