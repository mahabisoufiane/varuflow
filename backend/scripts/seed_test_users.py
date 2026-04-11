#!/usr/bin/env python3
"""Seed test users for all plan types.

Creates users directly in Supabase (no email confirmation required)
and matching orgs + members in the app database.

Usage:
    cd backend
    python scripts/seed_test_users.py

Requires in .env:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY   (Settings → API → service_role key)
    DATABASE_URL
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Allow running from backend/ or backend/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Fix URL scheme for asyncpg
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

PASSWORD = "Test1234!"

TEST_USERS = [
    {
        "email": "owner@varuflow.test",
        "full_name": "Owner User",
        "org_name": "Nordisk Handel AB",
        "org_number": "556100-1111",
        "plan": "FREE",
        "role": "OWNER",
        "label": "FREE plan — OWNER",
    },
    {
        "email": "pro@varuflow.test",
        "full_name": "Pro User",
        "org_name": "Svenska Grossist AB",
        "org_number": "556200-2222",
        "plan": "PRO",
        "role": "OWNER",
        "label": "PRO plan — OWNER",
    },
    {
        "email": "admin@varuflow.test",
        "full_name": "Admin User",
        "org_name": "Svenska Grossist AB",   # same org as pro@
        "org_number": None,
        "plan": None,                         # inherits from org
        "role": "ADMIN",
        "label": "PRO plan — ADMIN (member of pro@ org)",
        "join_org_email": "pro@varuflow.test",
    },
    {
        "email": "member@varuflow.test",
        "full_name": "Member User",
        "org_name": "Svenska Grossist AB",
        "org_number": None,
        "plan": None,
        "role": "MEMBER",
        "label": "PRO plan — MEMBER (member of pro@ org)",
        "join_org_email": "pro@varuflow.test",
    },
]


async def create_supabase_user(client: httpx.AsyncClient, email: str, full_name: str) -> str:
    """Create or fetch a Supabase user. Returns the user UUID."""
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    # Try to create
    res = await client.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": PASSWORD,
            "email_confirm": True,       # skip email verification
            "user_metadata": {"full_name": full_name},
        },
    )

    if res.status_code in (200, 201):
        return res.json()["id"]

    # Already exists — fetch by email
    if res.status_code == 422 and "already been registered" in res.text:
        list_res = await client.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=headers,
            params={"page": 1, "per_page": 1000},
        )
        users = list_res.json().get("users", [])
        for u in users:
            if u["email"] == email:
                print(f"  ↳ user already exists, reusing id {u['id']}")
                return u["id"]

    raise RuntimeError(f"Failed to create {email}: {res.status_code} {res.text}")


async def seed(db: AsyncSession) -> None:
    # Map email → supabase user id (filled during creation)
    user_ids: dict[str, uuid.UUID] = {}
    # Map org email → org_id (for members joining existing orgs)
    org_ids: dict[str, uuid.UUID] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        print("\n── Creating Supabase users ──────────────────────────────")
        for u in TEST_USERS:
            print(f"  {u['email']} ({u['label']}) …", end=" ", flush=True)
            uid = await create_supabase_user(client, u["email"], u["full_name"])
            user_ids[u["email"]] = uuid.UUID(uid)
            print("✓")

    print("\n── Seeding database orgs + members ─────────────────────")
    for u in TEST_USERS:
        uid = user_ids[u["email"]]

        # Check if member row already exists
        existing = await db.scalar(
            select(text("1")).select_from(
                text("organization_members")
            ).where(text(f"user_id = '{uid}'"))
        )
        if existing:
            print(f"  {u['email']} — member row already exists, skipping")
            continue

        if "join_org_email" in u:
            # Member/admin joining an existing org
            org_id = org_ids[u["join_org_email"]]
        else:
            # Owner — create new org
            org_id = uuid.uuid4()
            org_ids[u["email"]] = org_id
            await db.execute(
                text("""
                    INSERT INTO organizations (id, name, org_number, plan, is_active, created_at)
                    VALUES (:id, :name, :org_number, :plan, true, now())
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": str(org_id),
                    "name": u["org_name"],
                    "org_number": u.get("org_number"),
                    "plan": u["plan"],
                },
            )

        await db.execute(
            text("""
                INSERT INTO organization_members (id, org_id, user_id, role, created_at)
                VALUES (:id, :org_id, :user_id, :role, now())
                ON CONFLICT DO NOTHING
            """),
            {
                "id": str(uuid.uuid4()),
                "org_id": str(org_id),
                "user_id": str(uid),
                "role": u["role"],
            },
        )
        print(f"  {u['email']} — org + member created ✓")

    await db.commit()


def print_table(user_ids: None = None) -> None:
    col = 34
    print("\n" + "═" * 72)
    print("  TEST ACCOUNTS — ready to use")
    print("═" * 72)
    print(f"  {'EMAIL':<{col}} {'PASSWORD':<14} PLAN / ROLE")
    print("─" * 72)
    for u in TEST_USERS:
        print(f"  {u['email']:<{col}} {PASSWORD:<14} {u['label']}")
    print("═" * 72)
    print(f"\n  Login URL: https://varuflow.vercel.app/auth/login")
    print(f"  Local URL: http://localhost:3000/auth/login\n")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        await seed(db)

    await engine.dispose()
    print_table()


if __name__ == "__main__":
    asyncio.run(main())
