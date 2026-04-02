# Multi-stage: Frontend + Backend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS backend-builder
WORKDIR /app/backend
COPY backend/pyproject.toml backend/poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev
COPY backend ./

# Production image
FROM node:20-alpine
WORKDIR /app

# Copy built frontend
COPY --from=frontend-builder /app/frontend/.next/standalone ./
COPY --from=frontend-builder /app/frontend/public ./public
COPY --from=frontend-builder /app/frontend/next.config.mjs ./

EXPOSE 3000
ENV PORT=3000
CMD ["npm", "start"]