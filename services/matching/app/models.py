import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("resume_id", "job_id", name="uq_match_resume_job"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resume_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    ret_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ce_score: Mapped[float] = mapped_column(Float)
    skill_score: Mapped[float] = mapped_column(Float)
    final_score: Mapped[float] = mapped_column(Float, index=True)
    matched_json: Mapped[str] = mapped_column(Text, default="[]")
    missing_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
