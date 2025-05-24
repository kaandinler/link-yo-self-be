# settings.py
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Ortam değişkeni
    environment: str = "development"

    # Güvenlik ayarları
    allowed_hosts: Optional[List[str]] = None
    allowed_origins: Optional[List[str]] = None

settings = Settings()
