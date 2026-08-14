from typing import Optional
from pydantic import field_validator, model_validator
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
    # mistral-small, not ministral-3b. Re-scoring one unchanged transcript five
    # times on the 3B model moved the overall result by 15.7 points, with a
    # single parameter landing on 0, 4, 6, 6 and 7 - unusable for QA, where the
    # same call must score the same way twice. On mistral-small the same test
    # holds within ~5 points and most parameters are identical run to run.
    LLM_MODEL_NAME: str = "mistral-small-latest"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 60
    LLM_MAX_RETRIES: int = 3
    # Independent scoring passes per evaluation; each parameter takes the
    # median. LLM scoring is not reproducible even at temperature 0, and for
    # call QA the same call must not pass one day and fail the next. 3 is the
    # smallest number that lets a median discard a single outlier. Set to 1 to
    # disable and score in a single pass.
    LLM_SELF_CONSISTENCY_SAMPLES: int = 3

    # STT Configuration (Groq Whisper Provider)
    GROQ_STT_KEY: Optional[str] = None
    GROQ_STT_BASE_URL: str = "https://api.groq.com/openai/v1"
    # large-v3 (not -turbo): on Groq's free tier both models share the same
    # quota (20 RPM / 28,800 audio-seconds per day), and turbo is a distilled
    # 4-decoder-layer model that is measurably weaker on Hindi and other Indic
    # languages. Turbo only buys latency, and this pipeline is queue-bound
    # rather than latency-bound, so large-v3 is free accuracy.
    STT_MODEL_NAME: str = "whisper-large-v3"
    STT_MAX_RETRIES: int = 3
    # Parallel chunk transcriptions per call. Groq's free tier allows 20
    # requests/minute for Whisper, so firing every chunk at once just collects
    # 429s and burns retry budget.
    STT_MAX_CONCURRENT_CHUNKS: int = 3
    # Splitting a recording is off by default. Every seam is a chance to lose
    # or duplicate words, and an earlier silence-trimming split silently
    # dropped 9 seconds of a 311-second call. A recording that will not fit in
    # one request is re-encoded smaller instead; only if that still fails is
    # the upload rejected, so nothing is ever transcribed from fragments
    # without the operator explicitly turning this on.
    STT_ALLOW_CHUNKING: bool = False
    # Duration-weighted mean token probability below which a transcript is
    # flagged as unreliable and the report warns before showing analysis.
    STT_MIN_CONFIDENCE: float = 0.55
    # Speaker attribution is the headline feature, so it gets a capable model
    # rather than the cheapest one: ministral-3b labelled an entire 46-segment
    # two-party call as a single speaker. mistral-small (24B) handles it, and
    # Mistral's free tier (~1B tokens/month) absorbs the cost easily.
    DIARIZATION_MODEL_NAME: str = "mistral-small-latest"
    # Defaults to the main LLM provider's credentials.
    DIARIZATION_BASE_URL: Optional[str] = None
    DIARIZATION_API_KEY: Optional[str] = None

    # Job queue (Redis + arq). Transcription and evaluation run in a worker
    # process so a slow provider, a rate limit, or a redeploy cannot lose an
    # upload the way a bare asyncio.create_task did.
    REDIS_URL: str = "redis://localhost:6379/0"
    WORKER_MAX_JOBS: int = 4
    WORKER_JOB_TIMEOUT: int = 900
    WORKER_MAX_TRIES: int = 4

    # Provider bills are in USD; Indian clients budget in rupees. Kept as a
    # setting rather than hardcoded in the UI so the whole app converts against
    # one number that can be refreshed as the rate moves.
    # ~95.3 as of 2026-08-13. Review periodically - the rupee moved ~9% in the
    # preceding 12 months, which is larger than most of the cost differences
    # this dashboard is used to compare.
    USD_TO_INR_RATE: float = 95.3

    # MinIO Object Storage (Audio files)
    MINIO_ENDPOINT: str = "localhost:9000"
    # Host the *browser* uses to fetch presigned audio URLs. Inside Docker the
    # API talks to "minio:9000", which no browser can resolve - and the
    # presigned signature covers the host header, so the URL cannot simply be
    # string-rewritten afterwards. Signing has to be done against the public
    # host from the start. Defaults to MINIO_ENDPOINT for non-Docker runs.
    MINIO_PUBLIC_ENDPOINT: Optional[str] = None
    MINIO_PUBLIC_SECURE: Optional[bool] = None
    # MinIO's default. Pinned so presigning never needs a live region lookup.
    MINIO_REGION: str = "us-east-1"
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

    @model_validator(mode="after")
    def _test_database_must_differ(self) -> "Settings":
        """Refuse to start if the test database points at the real one.

        The test suite calls Base.metadata.drop_all() against TEST_DATABASE_URL.
        A copy-paste of the production URL into that variable would silently
        destroy live data, so the mistake is made unstartable rather than
        merely documented.
        """
        if self.TEST_DATABASE_URL and self.TEST_DATABASE_URL == self.DATABASE_URL:
            raise ValueError(
                "TEST_DATABASE_URL must not equal DATABASE_URL - the test suite "
                "drops every table in it. Point it at a dedicated test database."
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


settings = Settings()
