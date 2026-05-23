# Local Development

Run the full Varuflow stack locally using Docker Compose.

---

## Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine + Compose** (Linux)
- WSL2 on Windows (recommended)
- 4 GB RAM available for Docker

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-org/varuflow.git
cd varuflow

# 2. Start all services
docker compose up -d

# 3. Open the app — no login required in local dev
open http://localhost:3000
```

In local dev mode the app loads directly without a login wall. The backend's `ALLOW_DEV_BYPASS=true` setting returns a synthetic `DEV_USER` for all unauthenticated requests.

---

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend (Next.js) | http://localhost:3000 | — |
| Backend (FastAPI) | http://localhost:8000 | — |
| API docs (Swagger) | http://localhost:8000/docs | — |
| API docs (ReDoc) | http://localhost:8000/redoc | — |
| Health check | http://localhost:8000/api/health | — |
| Supabase (GoTrue) | http://localhost:9999 | — |
| n8n automation | http://localhost:5678 | admin / your-n8n-password |
| PostgreSQL | localhost:5432 | postgres / postgres |

---

## Environment Variables

The `docker-compose.yml` already includes all required dev values. No `.env` file is needed for basic local development.

To override values (e.g. connect to a real Supabase project):

```bash
# backend/.env — overrides docker-compose backend environment
cp backend/.env.example backend/.env
# edit backend/.env with your values

# frontend/.env.local — overrides docker-compose frontend environment
cp frontend/.env.local.example frontend/.env.local
# edit frontend/.env.local with your values
```

---

## First Run (Database)

On first start, Alembic runs migrations automatically via `backend/app/main.py` lifespan hook. You should see in the backend logs:

```
INFO  Running Alembic migrations...
INFO  INFO  [alembic.runtime.migration] Running upgrade ...
INFO  Migrations complete.
```

To run migrations manually:

```bash
docker compose exec backend alembic upgrade head
```

To create a new migration after model changes:

```bash
docker compose exec backend alembic revision --autogenerate -m "your description"
# Review the generated file in backend/migrations/versions/
docker compose exec backend alembic upgrade head
```

---

## Useful Commands

```bash
# Watch logs (all services)
docker compose logs -f

# Watch a specific service
docker compose logs -f frontend
docker compose logs -f backend

# Restart a single service
docker compose restart frontend

# Apply env var changes (restart alone doesn't work)
docker compose up -d --force-recreate

# Run a one-off backend command
docker compose exec backend python -c "from app.config import settings; print(settings.ENV)"

# Open a psql shell
docker compose exec postgres psql -U postgres varuflow

# Stop all services
docker compose down

# Full reset (wipe volumes including DB data)
docker compose down -v
```

---

## Troubleshooting

### `Module not found: Can't resolve 'react-is'`

Stale Docker volume. Fix:

```bash
docker volume rm varuflow_frontend_node_modules
docker compose up -d
```

### `404 Page Not Found` at `http://localhost:3000`

The Next.js dev server is still compiling on first boot. Wait for:

```
✓ Ready in Xs
```

in `docker compose logs -f frontend`, then refresh.

### `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`

Docker Desktop is not running. Start Docker Desktop first, then retry.

### CORS errors in browser console

Check `docker compose logs -f backend | grep CORS`. The `CORS_ORIGINS` env var must be comma-separated (not a JSON array):

```yaml
# Correct
CORS_ORIGINS: "http://localhost:3000,http://localhost:3002"

# Wrong
CORS_ORIGINS: '["http://localhost:3000","http://localhost:3002"]'
```

### Backend won't start / crashes immediately

Check for startup validation errors:

```bash
docker compose logs backend | grep "SECURITY CONFIG ERROR"
```

In local dev, `ENV=development` disables the production secret validator. If `ENV` is set to anything else, the validator runs and will crash on placeholder secrets.

### Supabase `ERR_CONNECTION_REFUSED` at `localhost:9999`

The GoTrue container is still starting up. Wait 10–15 seconds and retry. Check:

```bash
docker compose logs supabase
```

### Using a real Supabase project locally

If you want to test with a real Supabase project instead of the local GoTrue:

1. Set in `frontend/.env.local`:
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://<your-project>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
   ```

2. Set in `backend/.env`:
   ```
   SUPABASE_URL=https://<your-project>.supabase.co
   SUPABASE_JWT_SECRET=<your-jwt-secret>
   ENFORCE_JWT_SIGNATURE=true
   ALLOW_DEV_BYPASS=false
   ```

3. Recreate containers:
   ```bash
   docker compose up -d --force-recreate
   ```

---

## Running Services Individually (Without Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set env vars
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/varuflow
export ENV=development
export ALLOW_DEV_BYPASS=true

# Run
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps  # Required — ESLint peer dep conflict with Next.js 16
npm run dev
```

Note: `npm install --legacy-peer-deps` is required. Plain `npm install` will fail with a peer dependency conflict between ESLint and Next.js 16.

---

## n8n Automation

n8n is available at http://localhost:5678 for workflow automation (webhooks, scheduled tasks, integrations).

Default credentials (set in `docker-compose.yml`):
- Username: `admin`
- Password: `your-n8n-password`

Change the password via `N8N_BASIC_AUTH_PASSWORD` in `docker-compose.yml` for any shared environment.
