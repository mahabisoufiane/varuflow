# Root Dockerfile — builds the backend only (used by Railway)
# Frontend is deployed separately on Vercel.

FROM python:3.11-slim AS builder

RUN pip install poetry==1.8.2

WORKDIR /build
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry export -f requirements.txt -o requirements.txt --without dev --no-interaction

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ app/
COPY backend/migrations/ migrations/
COPY backend/alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
