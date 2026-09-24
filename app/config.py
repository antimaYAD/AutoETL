"""Application configuration, loaded from environment variables / .env."""
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "AutoETL"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Database. Either set DATABASE_URL directly, or set the DB_* parts below
    # and it will be assembled for you (DATABASE_URL takes precedence if set).
    database_url: str = "postgresql+psycopg2://autoetl:autoetl@localhost:5432/autoetl"
    db_host: str | None = None
    db_port: int = 5432
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None

    # Auth
    secret_key: str = "change-me-in-env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Storage
    storage_dir: Path = BASE_DIR / "storage"
    max_upload_size_mb: int = 100
    allowed_upload_extensions: tuple[str, ...] = (".csv", ".xlsx", ".xls")

    @model_validator(mode="after")
    def _assemble_database_url_from_parts(self) -> "Settings":
        """If DB_HOST/DB_NAME/DB_USER/DB_PASSWORD are set, build DATABASE_URL
        from them instead of requiring the caller to hand-assemble the URL
        (and correctly percent-encode the password).
        """
        if self.db_host and self.db_name and self.db_user:
            password = quote_plus(self.db_password) if self.db_password else ""
            auth = f"{self.db_user}:{password}" if password else self.db_user
            self.database_url = f"postgresql+psycopg2://{auth}@{self.db_host}:{self.db_port}/{self.db_name}"
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
