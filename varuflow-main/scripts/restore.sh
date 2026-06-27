#!/usr/bin/env bash
# restore.sh — restore a Varuflow database from a gzip-compressed pg_dump file.
#
# SAFETY GUARD: This script refuses to run unless ENV=development.
# Never point it at a production DATABASE_URL.
#
# Usage:
#   ENV=development DATABASE_URL=postgresql://user:pass@localhost:5432/varuflow_restore \
#     ./scripts/restore.sh backup-20260101-120000.sql.gz
#
# The target database must already exist. The script drops all existing
# tables before restoring so the result matches the dump exactly.
#
# Restore procedure:
#   1. Create a scratch database:       createdb varuflow_restore
#   2. Run this script:                 ./scripts/restore.sh <dump-file>
#   3. Smoke-test the scratch DB:       psql $DATABASE_URL -c "\dt"
#   4. When satisfied, update DATABASE_URL to point at the restored DB.
set -euo pipefail

# ── Safety guard ──────────────────────────────────────────────────────────────
if [[ "${ENV:-}" != "development" ]]; then
    echo "ERROR: ENV is '${ENV:-}' (expected 'development')." >&2
    echo "Refusing to restore into a non-development database." >&2
    echo "Set ENV=development if you are certain this is safe." >&2
    exit 1
fi

DUMP_FILE="${1:-}"
if [[ -z "${DUMP_FILE}" ]]; then
    echo "Usage: ENV=development DATABASE_URL=... $0 <dump-file.sql.gz>" >&2
    exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
    echo "ERROR: dump file not found: ${DUMP_FILE}" >&2
    exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is not set." >&2
    exit 1
fi

CLEAN_URL="${DATABASE_URL/#postgresql+asyncpg:\/\//postgresql:\/\/}"

echo "Restoring '${DUMP_FILE}' → ${CLEAN_URL} …" >&2
echo "WARNING: This will DROP all existing objects in the target database." >&2
read -r -p "Continue? [y/N] " CONFIRM
if [[ "${CONFIRM}" != "y" && "${CONFIRM}" != "Y" ]]; then
    echo "Aborted." >&2
    exit 1
fi

gunzip --stdout "${DUMP_FILE}" | pg_restore \
    --no-password \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --format=custom \
    --dburl="${CLEAN_URL}"

echo "Restore complete. Run 'alembic upgrade head' if needed." >&2
