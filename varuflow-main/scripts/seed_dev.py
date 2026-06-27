#!/usr/bin/env python3
"""Development database seed script.

Creates a demo organisation, owner user, and sample data so a freshly
cloned repo is usable without manual setup.

SAFETY GUARD: This script refuses to run outside a development environment.
Never run this against a staging or production database.

Usage:
    cd backend
    ENV=development poetry run python ../scripts/seed_dev.py
"""
import asyncio
import os
import sys
import uuid

assert os.getenv("ENV") == "development", (
    "Refusing to seed non-development environment. "
    "Set ENV=development to proceed."
)

# Project root on the path so app.* imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


async def main() -> None:
    from sqlalchemy import select

    from app.database import async_session, engine
    from app.models.organization import Organization, OrganizationMember, OrgPlan, OrgRole

    demo_org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    demo_user_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    async with async_session() as db:
        existing = await db.get(Organization, demo_org_id)
        if existing:
            print(f"Demo org already exists ({demo_org_id}) — skipping seed.")
            return

        org = Organization(
            id=demo_org_id,
            name="Demo Företag AB",
            org_number="556000-0001",
            plan=OrgPlan.ENTERPRISE,
        )
        member = OrganizationMember(
            org_id=demo_org_id,
            user_id=demo_user_id,
            role=OrgRole.OWNER,
        )
        db.add_all([org, member])
        await db.commit()
        print(f"Demo org created: id={demo_org_id} user_id={demo_user_id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
