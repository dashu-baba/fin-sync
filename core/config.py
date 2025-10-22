from __future__ import annotations
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Base .env load first
load_dotenv()

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unknown env keys to avoid crashes
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

    # GCP / Vertex AI
    gcp_project_id: str | None = Field(default=os.getenv("GCP_PROJECT_ID"))
    gcp_location: str = Field(default=os.getenv("GCP_LOCATION", "us-central1"))
    vertex_model: str = Field(default=os.getenv("VERTEX_MODEL", "gemini-2.5-pro"))
    vertex_model_genai: str = Field(default=os.getenv("VERTEX_MODEL_GENAI", os.getenv("VERTEX_MODEL", "gemini-2.5-pro")))
    vertex_model_embed: str = Field(default=os.getenv("VERTEX_MODEL_EMBED", "textembedding-gecko@003"))

    # Storage / Elastic
    gcs_bucket: str | None = Field(default=os.getenv("GCS_BUCKET"))
    elastic_cloud_id: str | None = Field(default=os.getenv("ELASTIC_CLOUD_ID"))
    elastic_api_key: str | None = Field(default=os.getenv("ELASTIC_API_KEY"))
    elastic_index_name: str = Field(default=os.getenv("ELASTIC_INDEX_NAME", "finsync-transactions"))

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        level = str(value).upper() if value else "INFO"
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if level not in allowed:
            # Fallback to INFO instead of raising to avoid boot failure
            return "INFO"
        return level

    @model_validator(mode="after")
    def _derive_paths_and_ensure_dirs(self) -> "AppConfig":
        # Layered environment loading: .env.<ENVIRONMENT> overrides base
        env_file_variant = Path(f".env.{self.environment}")
        if env_file_variant.exists():
            load_dotenv(env_file=env_file_variant, override=True)
            # Re-read dynamic fields that might be env-driven
            self.gcp_project_id = os.getenv("GCP_PROJECT_ID", self.gcp_project_id)
            self.gcp_location = os.getenv("GCP_LOCATION", self.gcp_location)
            self.vertex_model = os.getenv("VERTEX_MODEL", self.vertex_model)
            self.vertex_model_genai = os.getenv("VERTEX_MODEL_GENAI", self.vertex_model_genai)
            self.vertex_model_embed = os.getenv("VERTEX_MODEL_EMBED", self.vertex_model_embed)
            self.gcs_bucket = os.getenv("GCS_BUCKET", self.gcs_bucket)
            self.elastic_cloud_id = os.getenv("ELASTIC_CLOUD_ID", self.elastic_cloud_id)
            self.elastic_api_key = os.getenv("ELASTIC_API_KEY", self.elastic_api_key)
            self.elastic_index_name = os.getenv("ELASTIC_INDEX_NAME", self.elastic_index_name)

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
