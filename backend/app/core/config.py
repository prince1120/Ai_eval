from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Scribe Teal AI Platform API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str
    # Dedicated Postgres database for the test suite (never the dev/prod DATABASE_URL).
    TEST_DATABASE_URL: Optional[str] = None

    # Comma-separated list of allowed browser origins for CORS (no wildcard - cookies require an explicit list)
    CORS_ORIGINS: str = "http://localhost:3001,http://127.0.0.1:3001"

    # Auto-convert standard postgres:// or postgresql:// to postgresql+asyncpg:// for Supabase
    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # JWT Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # LLM Configuration (Mistral AI Provider)
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://api.mistral.ai/v1"
    LLM_MODEL_NAME: str = "ministral-3b-2512"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 60
    LLM_MAX_RETRIES: int = 3

    # STT Configuration (Groq Whisper Provider)
    GROQ_STT_KEY: Optional[str] = None
    GROQ_STT_BASE_URL: str = "https://api.groq.com/openai/v1"
    STT_MODEL_NAME: str = "whisper-large-v3-turbo"

    # MinIO Object Storage (Audio files)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "call-recordings"
    MINIO_SECURE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


settings = Settings()
