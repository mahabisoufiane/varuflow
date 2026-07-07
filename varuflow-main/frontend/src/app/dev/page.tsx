"use client";

// File: src/app/dev/page.tsx
// Purpose: Local development hub — everything a developer needs to know about
// this project on one page: what it is, service URLs, auth modes, run/test
// commands, live backend status. Served at http://localhost:3000/dev and the
// root of localhost redirects here in development. Hidden in production.

import { useEffect, useState } from "react";

const IS_DEV = process.env.NODE_ENV === "development";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const AUTH_MODE =
  !SUPABASE_URL || SUPABASE_URL.includes("placeholder") || SUPABASE_URL.includes("localhost")
    ? "dev-bypass"
    : "real";

interface Health {
  status: string;
  version: string;
  database: string;
  config: Record<string, boolean>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-[var(--vf-border)] bg-[var(--vf-bg-surface)] p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--vf-text-muted)]">{title}</h2>
      {children}
    </section>
  );
}

function Code({ children }: { children: string }) {
  return (
    <code className="block overflow-x-auto whitespace-pre rounded-md bg-[var(--vf-bg-inset)] px-3 py-2 font-mono text-xs text-[var(--vf-text-primary)]">
      {children}
    </code>
  );
}

function Row({ k, v, href }: { k: string; v: string; href?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-[var(--vf-divider)] py-1.5 text-sm last:border-0">
      <span className="text-[var(--vf-text-muted)]">{k}</span>
      {href ? (
        <a href={href} className="font-mono text-sm text-[var(--vf-brand-primary)] hover:underline">{v}</a>
      ) : (
        <span className="font-mono text-sm text-[var(--vf-text-primary)]">{v}</span>
      )}
    </div>
  );
}

export default function DevHubPage() {
  const [health, setHealth] = useState<Health | null | "down">(null);

  useEffect(() => {
    if (!IS_DEV) return;
    const load = () =>
      fetch("http://localhost:8000/api/health")
        .then((r) => r.json())
        .then(setHealth)
        .catch(() => setHealth("down"));
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  if (!IS_DEV) {
    // Never expose internals outside local development.
    return <p className="p-10 text-sm text-[var(--vf-text-muted)]">Not available.</p>;
  }

  const backendUp = health !== null && health !== "down";

  return (
    <main className="mx-auto max-w-3xl space-y-5 px-6 py-10 text-[var(--vf-text-primary)]">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--vf-brand-primary)]">Local dev hub</p>
        <h1 className="mt-1 text-2xl font-bold">Varuflow</h1>
        <p className="mt-2 max-w-xl text-sm text-[var(--vf-text-secondary)]">
          Business OS for Nordic wholesalers — inventory, invoicing, orders, purchasing,
          customers and cash flow. Next.js 16 frontend (operator-console shell, Proxmox-style
          IA), FastAPI backend, PostgreSQL. Sweden-first: default locale <b>sv</b>, all app
          URLs locale-prefixed.
        </p>
      </header>

      <Section title="Live status">
        <div className="flex items-center gap-2 pb-2">
          <span className={`h-2.5 w-2.5 rounded-full ${health === null ? "bg-[var(--vf-warning)]" : backendUp ? "bg-[var(--vf-success)]" : "bg-[var(--vf-danger)]"}`} />
          <span className="text-sm font-medium">
            {health === null ? "Checking backend…" : backendUp ? `Backend up · db ${(health as Health).database} · v${(health as Health).version}` : "Backend DOWN — start it (see Run commands)"}
          </span>
        </div>
        {backendUp && (
          <p className="text-xs text-[var(--vf-text-muted)]">
            Integrations configured:{" "}
            {Object.entries((health as Health).config).filter(([, v]) => v).map(([k]) => k).join(", ") || "none (normal for local dev)"}
          </p>
        )}
        <div className="mt-2">
          <Row k="Auth mode (this build)" v={AUTH_MODE === "real" ? "REAL — login required" : "DEV BYPASS — no login"} />
        </div>
      </Section>

      <Section title="URLs">
        <Row k="App (Swedish default)" v="localhost:3000/sv/dashboard" href="/sv/dashboard" />
        <Row k="App (English)" v="localhost:3000/en/dashboard" href="/en/dashboard" />
        <Row k="Login / Signup" v="/sv/auth/login" href="/sv/auth/login" />
        <Row k="Backend API" v="localhost:8000/api/health" href="http://localhost:8000/api/health" />
        <Row k="API docs (Swagger)" v="localhost:8000/docs" href="http://localhost:8000/docs" />
        <Row k="PostgreSQL (Docker)" v="localhost:5544 · db varuflow" />
      </Section>

      <Section title="Auth modes — how to switch">
        <p className="mb-2 text-sm text-[var(--vf-text-secondary)]">
          One variable in <span className="font-mono text-xs">frontend/.env.local</span> controls everything
          (middleware, layout gate, client session guards), then restart the frontend:
        </p>
        <Code>{`# REAL login flow (current: ${AUTH_MODE === "real" ? "THIS" : "not active"})
NEXT_PUBLIC_SUPABASE_URL=https://tmizvegzdlwpqceavvwh.supabase.co

# DEV bypass — explore without logging in (current: ${AUTH_MODE === "real" ? "not active" : "THIS"})
NEXT_PUBLIC_SUPABASE_URL=https://placeholder.supabase.co`}</Code>
        <p className="mt-2 text-xs text-[var(--vf-text-muted)]">
          The backend accepts either mode locally (ENV=development + ALLOW_DEV_BYPASS=true in
          backend/.env). In dev-bypass a demo org "Varuflow Demo AB" is auto-provisioned.
        </p>
      </Section>

      <Section title="Run commands">
        <Code>{`# Database (Docker, host port 5544 — 5432 is taken by another project)
docker start varuflow-db

# Backend — DATABASE_URL must be exported (alembic reads os.environ, not .env)
cd backend
export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5544/varuflow'
poetry run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Pages 404 after a machine restart? Stale .next cache — one command:
cd frontend && npm run dev:clean`}</Code>
      </Section>

      <Section title="Tests & quality gates">
        <Code>{`# Backend route guards (all GET routes ≠5xx · 22-step money-path mutations)
cd backend
DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5544/varuflow' \\
  poetry run pytest tests/test_route_smoke.py tests/test_mutation_smoke.py -q

# Frontend gates
cd frontend
npx tsc --noEmit                      # types
./scripts/check-tokens.sh             # design-token ratchet (no new hardcoded colors)
./scripts/check-silent-swallow.sh     # no new .catch(() => []) data swallows`}</Code>
      </Section>

      <Section title="Project facts">
        <Row k="Design system" v="Steel Blue #2f5ea8 · --vf-* CSS vars · light+dark" />
        <Row k="Console shell" v="4 regions: header · resource tree · content · task drawer" />
        <Row k="Migrations" v="apply clean from empty DB (178 revisions)" />
        <Row k="Working branch" v="dev (integration) · PRs: feat/operator-console, fix/migrations-from-scratch" />
        <Row k="Design docs" v="frontend/design-audit/{token-inventory,gap-analysis}.md" />
        <Row k="Repo guide" v="CLAUDE.md · README.md" />
      </Section>

      <footer className="pb-6 text-center text-xs text-[var(--vf-text-muted)]">
        This page exists only in development (NODE_ENV) — production serves the marketing site here.
      </footer>
    </main>
  );
}
