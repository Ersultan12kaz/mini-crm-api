import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Stage(str, enum.Enum):
    lead = "lead"
    contacted = "contacted"
    proposal = "proposal"
    won = "won"
    lost = "lost"


CLOSED_STAGES = {Stage.won, Stage.lost}


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    deals: Mapped[list["Deal"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    notes: Mapped[list["Note"]] = relationship(back_populates="customer", cascade="all, delete-orphan",
                                               order_by="Note.id.desc()")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(BigInteger, default=0)  # whole currency units, e.g. tenge
    stage: Mapped[Stage] = mapped_column(Enum(Stage, native_enum=False, length=16), default=Stage.lead, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="deals")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="notes")
