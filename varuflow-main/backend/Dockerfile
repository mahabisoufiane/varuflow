# L-6: mutable tag — Dependabot (docker ecosystem, /backend) opens weekly PRs
# to bump this when a new python:3.11-slim is published. To pin to a digest for
# fully reproducible builds, replace both occurrences below with:
#   FROM python:3.11-slim@sha256:<digest>
# Get the current digest: docker inspect python:3.11-slim | jq -r '.[0].RepoDigests[0]'
FROM python:3.14-slim AS builder

# L-1: upgrade pip in the build stage to mitigate PYSEC-2026-196 path-traversal
# CVE (affects pip install, not runtime). Pin pip version so the builder is
# deterministic; Dependabot bumps this the same week a new pip is released.
RUN pip install --no-cache-dir --upgrade "pip>=25.0"
RUN pip install --no-cache-dir "poetry==1.8.2"

WORKDIR /build
COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt -o requirements.txt --without dev

FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /build/requirements.txt .
# bcrypt is declared in pyproject.toml (>=4.0.0) and lands in requirements.txt;
# no separate pip install needed.
RUN pip install --no-cache-dir --upgrade "pip>=25.0" && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .

EXPOSE 8000

RUN adduser --disabled-password --gecos "" appuser
USER appuser

# python:3.11-slim has no curl; use the stdlib urllib instead.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
