from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = WORKSPACE_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(WORKSPACE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "MathMaster"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    database_backend: str = "sqlite"
    sqlite_path: str = str(DEFAULT_DATA_DIR / "mathmaster.db")
    mysql_host: str = "106.54.35.68"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "mathmaster"
    database_echo: bool = False

    storage_backend: str = "local"
    storage_base_dir: str = str(DEFAULT_DATA_DIR)
    sftp_host: str | None = None
    sftp_port: int = 22
    sftp_username: str | None = None
    sftp_password: str | None = None
    sftp_private_key: str | None = None
    sftp_timeout_seconds: int = 15
    file_service_base_url: str | None = None

    mineu_base_url: str | None = None
    mineu_api_key: str | None = None
    mineu_use_mock: bool = True
    mineu_poll_seconds: int = 3
    mineu_poll_max_attempts: int = 40

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    default_model_slice: str = "gpt-5.4-high"
    default_model_analysis: str = "gpt-5.4-high"
    default_model_chat: str = "gpt-5.4-mini"
    fallback_model: str = "claude-sonnet-4.6"
    llm_timeout_seconds: int = 45
    llm_use_mock: bool = True

    local_workspace_root: str = str(WORKSPACE_ROOT)

    @property
    def sqlite_path_obj(self) -> Path:
        return Path(self.sqlite_path).expanduser().resolve()

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_backend.lower() == "sqlite":
            return str(URL.create("sqlite+pysqlite", database=str(self.sqlite_path_obj)))
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
