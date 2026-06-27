from __future__ import annotations
import uuid
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    result_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    result_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
