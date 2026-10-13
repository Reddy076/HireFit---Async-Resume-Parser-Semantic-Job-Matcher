import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    skills_json: Mapped[str] = mapped_column(Text, default="[]")
    created_by: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
