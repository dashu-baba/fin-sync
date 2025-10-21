from __future__ import annotations
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production", "test"] = Field(default="development")
    log_level: str = Field(default="INFO")
    app_port: int = Field(default=8501, ge=1, le=65535)

    # Upload policy
    max_total_mb: int = Field(default=100, ge=1)
    max_files: int = Field(default=25, ge=1)
    allowed_ext: tuple[str, ...] = ("pdf", "csv")

    # Paths
    data_dir: Path = Field(default=Path(os.getenv("DATA_DIR", "data")))
    uploads_dir: Path | None = None
    logs_dir: Path = Field(default=Path(os.getenv("LOGS_DIR", "data/output")))
    log_file: Path | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        level = str(value).upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level

    @model_validator(mode="after")
    def _derive_paths_and_ensure_dirs(self) -> "AppConfig":
        if self.uploads_dir is None:
            self.uploads_dir = self.data_dir / "uploads"
        if self.log_file is None:
            self.log_file = self.logs_dir / "app.log"

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        return self

config = AppConfig()
