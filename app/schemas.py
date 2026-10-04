from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Stage


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    company: str | None = Field(default=None, max_length=200)


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    company: str | None = Field(default=None, max_length=200)


class CustomerOut(CustomerIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class DealIn(BaseModel):
    customer_id: int
    title: str = Field(min_length=1, max_length=200)
    amount: int = Field(default=0, ge=0)
    stage: Stage = Stage.lead


class DealPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    amount: int | None = Field(default=None, ge=0)
    stage: Stage | None = None


class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    title: str
    amount: int
    stage: Stage
    created_at: datetime
    updated_at: datetime


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class NoteOut(NoteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class StageSummary(BaseModel):
    stage: Stage
    deals: int
    amount: int


class Pipeline(BaseModel):
    stages: list[StageSummary]
    open_amount: int
    won_amount: int
    win_rate: float | None  # won / (won + lost), None when nothing is closed yet
