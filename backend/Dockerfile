FROM python:3.11-slim AS builder

RUN pip install poetry==1.8.2

WORKDIR /build
COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt -o requirements.txt --without dev

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "bcrypt==4.0.1"

COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .

EXPOSE 8000

RUN adduser --disabled-password --gecos "" appuser
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
