# EvalPulse - Call Evaluation & Audio Analysis Backend API

An enterprise-grade, multi-tenant Python FastAPI backend for automatic speech-to-text (STT) transcription, generic AI speaker diarization (Agent vs Customer), and customizable LLM quality scorecard evaluations.

---

## 🛠️ Technology Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **Database & ORM**: SQLAlchemy 2.0 Async ORM + PostgreSQL
- **Database Migrations**: Alembic
- **Speech-to-Text (STT)**: Groq Whisper (`whisper-large-v3-turbo`)
- **LLM Engine**: AsyncOpenAI Client (Ministral / Groq LLMs)
- **Authentication**: JWT via httpOnly cookie (or Bearer token for API clients) + PBKDF2-SHA256 Password Hashing
- **Data Validation**: Pydantic v2 & Pydantic-Settings
- **ASGI Server**: Uvicorn

---

## ✨ Key Features

1. **Groq Whisper Audio Transcription**:
   - Transcribes call recordings (`.mp3`, `.wav`, `.m4a`) into raw text using Groq's high-speed Whisper API.

2. **Generic Speaker Diarization & Role Labeling**:
   - Analyzes full call context to assign exact `Agent:` vs `Customer:` turns.
   - **100% Text & Script Fidelity**: Preserves original spoken words, Hindi Devanagari script, Hinglish, and English without translation or paraphrasing.
   - Domain-agnostic rules for e-commerce, telecom, banking, technical support, healthcare, and sales.

3. **Multi-Tenant Organization Security**:
   - Every API request is authenticated via JWT.
   - Queries are strictly isolated by `organization_id` so tenants can never view or modify other organizations' data.

4. **Dynamic Scorecard Templates & Versioning**:
   - Support for custom evaluation parameters, score ranges, weightings, and AI extraction sections.
   - Every evaluation run snapshots template criteria at execution time for immutable historical reporting.

---

## 🚀 Getting Started

### 1. Environment Configuration

Create a `.env` file in the `backend` root directory:

```env
PROJECT_NAME="EvalPulse API"
ENVIRONMENT="development"
DEBUG=True

# Database Configuration
DATABASE_URL="postgresql+asyncpg://user:password@host:5432/evalpulse"
# Dedicated Postgres database for running the test suite (never point this at DATABASE_URL)
TEST_DATABASE_URL="postgresql+asyncpg://user:password@host:5432/evalpulse_test"

# Security & JWT
SECRET_KEY="your-super-secret-jwt-key"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Groq Whisper STT & LLM API Keys
GROQ_STT_KEY="your-groq-api-key"
GROQ_STT_BASE_URL="https://api.groq.com/openai/v1"
STT_MODEL_NAME="whisper-large-v3-turbo"

LLM_API_KEY="your-llm-api-key"
LLM_BASE_URL="https://api.mistral.ai/v1"
LLM_MODEL_NAME="ministral-3b-2512"
LLM_TIMEOUT=60.0
```

### 2. Install Dependencies

```bash
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Database Migrations

```bash
alembic upgrade head
```

### 4. Start Development Server

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API server will run at `http://localhost:8000`.

### 5. Alternative: Docker

```bash
docker compose up --build
```

Runs a local Postgres alongside the API (see `docker-compose.yml` at the repo root). Migrations run automatically on container start. This is for local development only - `docker-compose.yml`'s Postgres service is not intended as a production database.

---

## 📚 Interactive API Documentation

FastAPI provides automatic interactive API docs accessible at:

- **Swagger UI**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **ReDoc**: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🗺️ Key API Endpoints Summary

### Authentication (`/api/v1/auth`)
- `POST /register`: Register a new organization and admin account.
- `POST /login`: Authenticate user and receive JWT access token.
- `GET /me`: Fetch currently authenticated user profile.

### Transcripts & Audio (`/api/v1/transcripts`)
- `POST /upload-audio`: Upload call recording file (`.mp3`, `.wav`), run Whisper STT + speaker diarization, and optionally trigger AI evaluation.
- `POST /`: Submit raw text transcript.
- `GET /`: List all transcripts for the caller's organization.
- `GET /{id}`: Retrieve transcript details and speaker dialogue segments.
- `DELETE /{id}`: Delete a transcript and associated analysis runs.
- `POST /{id}/analyze`: Trigger AI scorecard evaluation on a transcript.

### Templates & Scorecards (`/api/v1/templates`)
- `GET /`: List scorecard templates.
- `POST /`: Create a custom template with criteria parameters.
- `POST /{id}/activate`: Set template as default scorecard.
- `DELETE /{id}`: Delete a scorecard template.

### Analysis Reports (`/api/v1/analysis-runs`)
- `GET /`: List all evaluation runs.
- `GET /{id}`: Retrieve parameter breakdowns, score summary, evidence quotes, and token usage.

---

## 🏛️ Project Directory Architecture

```
backend/
├── app/
│   ├── api/             # FastAPI Route Handlers & Dependencies
│   │   ├── deps.py      # Auth & Service Dependency Injection
│   │   └── v1/          # Endpoint API Router v1
│   ├── core/            # App Config, Security & DB Session Engine
│   ├── models/          # SQLAlchemy Database Entities
│   ├── schemas/         # Pydantic Schemas & DTOs
│   ├── services/        # Business Logic (STT, Diarization, LLM, Template)
│   └── main.py          # FastAPI Application Entrypoint
├── alembic/             # Database Migration Scripts
├── requirements.txt     # Python Package Dependencies
└── README.md            # Backend Documentation
```
