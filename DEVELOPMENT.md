# Development & Docker Workflow

Everything you need to run, change and manage this stack.

---

## The stack

| Service | Port (host) | What it does |
|---|---|---|
| `frontend` | 3001 | Next.js UI |
| `backend` | 8000 | FastAPI. Also runs `alembic upgrade head` on every start |
| `worker` | – | arq worker: transcription + evaluation jobs |
| `db` | 5432 | Postgres |
| `redis` | **6380** | Job queue + provider quota counters |
| `minio` | 9000 / 9001 | Audio storage (9001 = web console, `minioadmin`/`minioadmin`) |

> **Redis is on 6380, not 6379.** Port 6379 is already taken by another project's
> `rag_redis` container on this machine. Inside the compose network the services
> still talk to `redis:6379`.

---

## Start / stop

```bash
docker compose up -d --build
```

```bash
docker compose ps
```

```bash
docker compose down
```

`down` keeps your data. To wipe the database, audio and job queue as well:

```bash
docker compose down -v
```

---

## After you change code

**This is the part that catches people out:** `docker compose up -d` on its own
reuses the existing image. Your edits will *not* appear. You must pass `--build`.

### Backend Python change (`backend/app/**`)

Rebuild both — the worker runs the same image:

```bash
docker compose up -d --build backend worker
```

### Frontend change (`frontend/**`)

```bash
docker compose up -d --build frontend
```

### Added a migration (`backend/alembic/versions/**`)

Same as a backend change. The backend container runs `alembic upgrade head`
before starting uvicorn, so the migration applies on boot:

```bash
docker compose up -d --build backend worker
```

### Changed `backend/.env`

No rebuild needed — `env_file` is read when the container starts:

```bash
docker compose restart backend worker
```

### Changed `requirements.txt` or `package.json`

```bash
docker compose build --no-cache backend frontend
```

```bash
docker compose up -d
```

### Changed `docker-compose.yml`

```bash
docker compose up -d
```

---

## ⚠️ Which database am I talking to?

This is the single most important thing to understand about this setup.

| How you run it | Database |
|---|---|
| `docker compose up` | Local `db` container — **throwaway** |
| `uvicorn` / `arq` natively | Whatever `backend/.env` says — currently **production Supabase** |

`docker-compose.yml` sets `DATABASE_URL` in its `environment:` block, and in
Compose that **overrides** anything in `env_file:`. So the containers ignore the
Supabase URL in `.env` and use the local Postgres.

Consequences:

- `docker compose down -v` only ever wipes the local container. Your Supabase
  data is not at risk from it.
- Running the app **natively** connects to production. `alembic upgrade head`
  run natively applies migrations to your live database.
- **Never point `TEST_DATABASE_URL` at Supabase.** The test suite calls
  `drop_all()` on it.

Check which one you are about to hit:

```bash
cd backend && ./venv/Scripts/python.exe -c "from app.core.config import settings; print(settings.DATABASE_URL)"
```

To make the native dev loop safe, point `.env` at the local container and let
Compose keep overriding it for the Docker path:

```
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/transcript_eval"
```

Keep the Supabase URL somewhere else (a `.env.production`, or your password
manager) rather than as the default in `.env`.

---

## Faster day-to-day loop (recommended)

Read the database warning above first — running natively means `.env` decides
where your writes go.

Rebuilding an image for every one-line change is slow. Run the infrastructure in
Docker and the app code natively, so you get hot reload:

```bash
docker compose up -d db redis minio
```

Then in three terminals:

```bash
cd backend && ./venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

```bash
cd backend && ./venv/Scripts/python.exe -m arq app.workers.jobs.WorkerSettings --watch app
```

```bash
cd frontend && npm run dev
```

**One catch:** when running natively, your `backend/.env` must point at the
*host* ports, not the compose service names:

```
REDIS_URL="redis://localhost:6380/0"
MINIO_ENDPOINT="localhost:9000"
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/transcript_eval"
```

Inside Docker those are overridden to `redis:6379` / `minio:9000` / `db:5432` by
`docker-compose.yml`, so the same `.env` works for both — just keep the host
values in the file.

---

## Logs

```bash
docker compose logs -f worker
```

```bash
docker compose logs -f backend
```

```bash
docker compose logs --tail=50 backend worker
```

The worker is where transcription happens, so that's the log to watch when an
upload seems stuck.

> SQL statements are logged because `DEBUG=True` in `backend/.env`. Set
> `DEBUG=False` to quiet them down.

---

## Database

```bash
docker compose exec db psql -U postgres -d transcript_eval
```

Current migration revision:

```bash
docker compose exec db psql -U postgres -d transcript_eval -tc "select version_num from alembic_version;"
```

Create a new migration after changing a model:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe your change"
```

> Autogenerate compares your models against the **live database**, not against
> the migration history. That is exactly how this project ended up with three
> tables and four columns missing from the chain. After generating, always read
> the file and confirm it would work on an *empty* database — test with
> `docker compose down -v && docker compose up -d --build`.

Apply migrations manually (normally automatic on backend start):

```bash
docker compose exec backend alembic upgrade head
```

---

## Tests

```bash
cd backend && ./venv/Scripts/python.exe -m pytest tests/ -q
```

Five test files need a Postgres test database and will error without it. Set
`TEST_DATABASE_URL` in `backend/.env` to run them:

```
TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/transcript_eval_test"
```

Create that database first:

```bash
docker compose exec db psql -U postgres -c "CREATE DATABASE transcript_eval_test;"
```

---

## Checking the system

Health (fails if Postgres *or* Redis is down):

```bash
curl -s http://localhost:8000/api/v1/health
```

Remaining provider quota and queue depth (admin login required):

```bash
curl -s http://localhost:8000/api/v1/quota -b cookies.txt
```

API docs: <http://localhost:8000/api/v1/docs>
MinIO console: <http://localhost:9001>

---

## Shell access

```bash
docker compose exec backend sh
```

```bash
docker compose exec worker ffmpeg -version
```

---

## Common problems

**Uploads stay in `queued` forever.**
The worker is down or can't reach Redis. Check `docker compose ps` and
`docker compose logs worker`. Note that a job *deferred* on quota is normal —
the log line says so and it will resume when the window resets.

**Backend container exits immediately.**
Almost always a migration failure. `docker compose logs backend` and look for
the `[SQL: ...]` line at the bottom of the traceback.

**Code changes have no effect.**
You omitted `--build`.

**Port already in use.**
Something else is on 3001/5432/8000/9000. Change the *left* number in the
`ports:` mapping in `docker-compose.yml`.

**`npm run dev` and Docker frontend both running.**
Both want port 3001. Stop one: `docker compose stop frontend`.
