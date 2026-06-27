#!/usr/bin/env bash
# backup.sh — dump the Varuflow Postgres database to a gzip-compressed file.
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname ./scripts/backup.sh
#   DATABASE_URL=... ./scripts/backup.sh > /tmp/backup-$(date +%Y%m%d-%H%M%S).sql.gz
#
# The dump is written to stdout so callers can pipe it to a file, S3, or any
# other storage. All schema and data are included; no --data-only flag is set
# so restores work on an empty database.
#
# On Railway:
#   railway run ./scripts/backup.sh > backups/$(date +%Y%m%d-%H%M%S).sql.gz
#
# Restore procedure is in scripts/restore.sh.
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is not set." >&2
    exit 1
fi

# Extract connection parts from the URL.
# Supports postgresql+asyncpg:// (SQLAlchemy async driver) and postgresql://
CLEAN_URL="${DATABASE_URL/#postgresql+asyncpg:\/\//postgresql:\/\/}"

echo "Starting pg_dump …" >&2
pg_dump \
    --no-password \
    --format=custom \
    --compress=9 \
    "${CLEAN_URL}" \
| gzip -9

echo "Backup complete." >&2
