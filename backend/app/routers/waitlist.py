"""Public waitlist endpoint — no auth required."""
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.waitlist import Waitlist

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


class WaitlistJoin(BaseModel):
    email: str
    company_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


@router.post("", status_code=status.HTTP_201_CREATED)
async def join_waitlist(body: WaitlistJoin, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(Waitlist).where(Waitlist.email == body.email))
    if existing:
        # Idempotent — already on list is fine, don't expose that info
        return {"status": "ok"}
    entry = Waitlist(email=body.email, company_name=body.company_name)
    db.add(entry)
    await db.commit()
    return {"status": "ok"}
