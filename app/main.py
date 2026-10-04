"""Mini CRM REST API: customers, deals pipeline and notes."""

import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.models import CLOSED_STAGES, Customer, Deal, Note, Stage
from app.schemas import (
    CustomerIn, CustomerOut, CustomerPatch, DealIn, DealOut, DealPatch, NoteIn, NoteOut, Pipeline, StageSummary,
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(api_key_header)) -> None:
    expected = os.getenv("CRM_API_KEY")
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "CRM_API_KEY is not configured on the server")
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-API-Key")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # for production schemas, use migrations (e.g. Alembic)
    yield


app = FastAPI(title="Mini CRM API", version="1.0.0", lifespan=lifespan, dependencies=[Depends(require_api_key)])


def _customer_or_404(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return customer


# --- Customers ---------------------------------------------------------------

@app.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED, tags=["customers"])
def create_customer(body: CustomerIn, db: Session = Depends(get_db)):
    customer = Customer(**body.model_dump())
    db.add(customer)
    db.commit()
    return customer


@app.get("/customers", response_model=list[CustomerOut], tags=["customers"])
def list_customers(
    q: str | None = Query(default=None, description="Search by name, phone, email or company"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Customer).order_by(Customer.id.desc()).limit(limit).offset(offset)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.name.ilike(like), Customer.phone.ilike(like),
                              Customer.email.ilike(like), Customer.company.ilike(like)))
    return db.scalars(stmt).all()


@app.get("/customers/{customer_id}", response_model=CustomerOut, tags=["customers"])
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return _customer_or_404(db, customer_id)


@app.patch("/customers/{customer_id}", response_model=CustomerOut, tags=["customers"])
def update_customer(customer_id: int, body: CustomerPatch, db: Session = Depends(get_db)):
    customer = _customer_or_404(db, customer_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    return customer


@app.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["customers"])
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    db.delete(_customer_or_404(db, customer_id))
    db.commit()


# --- Notes -------------------------------------------------------------------

@app.post("/customers/{customer_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED,
          tags=["notes"])
def add_note(customer_id: int, body: NoteIn, db: Session = Depends(get_db)):
    _customer_or_404(db, customer_id)
    note = Note(customer_id=customer_id, text=body.text)
    db.add(note)
    db.commit()
    return note


@app.get("/customers/{customer_id}/notes", response_model=list[NoteOut], tags=["notes"])
def list_notes(customer_id: int, db: Session = Depends(get_db)):
    return _customer_or_404(db, customer_id).notes


# --- Deals -------------------------------------------------------------------

@app.post("/deals", response_model=DealOut, status_code=status.HTTP_201_CREATED, tags=["deals"])
def create_deal(body: DealIn, db: Session = Depends(get_db)):
    _customer_or_404(db, body.customer_id)
    deal = Deal(**body.model_dump())
    db.add(deal)
    db.commit()
    return deal


@app.get("/deals", response_model=list[DealOut], tags=["deals"])
def list_deals(
    stage: Stage | None = None,
    customer_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Deal).order_by(Deal.id.desc()).limit(limit).offset(offset)
    if stage:
        stmt = stmt.where(Deal.stage == stage)
    if customer_id:
        stmt = stmt.where(Deal.customer_id == customer_id)
    return db.scalars(stmt).all()


@app.patch("/deals/{deal_id}", response_model=DealOut, tags=["deals"])
def update_deal(deal_id: int, body: DealPatch, db: Session = Depends(get_db)):
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found")
    changes = body.model_dump(exclude_unset=True)
    if deal.stage in CLOSED_STAGES and changes.get("stage", deal.stage) != deal.stage:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Deal is already {deal.stage.value}; closed deals can't move")
    for field, value in changes.items():
        setattr(deal, field, value)
    db.commit()
    return deal


@app.get("/pipeline", response_model=Pipeline, tags=["deals"])
def pipeline(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0)).group_by(Deal.stage)
    ).all()
    by_stage = {stage: (count, amount) for stage, count, amount in rows}
    stages = [StageSummary(stage=s, deals=by_stage.get(s, (0, 0))[0], amount=by_stage.get(s, (0, 0))[1])
              for s in Stage]
    won, lost = by_stage.get(Stage.won, (0, 0))[0], by_stage.get(Stage.lost, (0, 0))[0]
    return Pipeline(
        stages=stages,
        open_amount=sum(s.amount for s in stages if s.stage not in CLOSED_STAGES),
        won_amount=by_stage.get(Stage.won, (0, 0))[1],
        win_rate=round(won / (won + lost), 3) if won + lost else None,
    )
