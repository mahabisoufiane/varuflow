FROM python:3.11-slim AS builder

RUN pip install poetry==1.8.2

WORKDIR /build
COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt -o requirements.txt --without dev

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
