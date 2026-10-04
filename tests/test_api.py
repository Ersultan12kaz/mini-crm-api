import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

KEY = {"X-API-Key": "test-key"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CRM_API_KEY", "test-key")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_customer(client, **kw):
    body = {"name": "Aigerim", "phone": "+77011234567", "email": "aigerim@example.kz", "company": "Aru Beauty"} | kw
    r = client.post("/customers", json=body, headers=KEY)
    assert r.status_code == 201, r.text
    return r.json()


def test_requires_api_key(client):
    assert client.get("/customers").status_code == 401
    assert client.get("/customers", headers={"X-API-Key": "wrong"}).status_code == 401


def test_key_not_configured(client, monkeypatch):
    monkeypatch.delenv("CRM_API_KEY")
    assert client.get("/customers", headers=KEY).status_code == 503


def test_customer_crud_and_search(client):
    c = make_customer(client)
    make_customer(client, name="Bolat", phone="+77770000000", email=None, company="Steppe Tech")

    assert client.get(f"/customers/{c['id']}", headers=KEY).json()["name"] == "Aigerim"
    assert [x["name"] for x in client.get("/customers?q=steppe", headers=KEY).json()] == ["Bolat"]
    assert len(client.get("/customers?limit=1", headers=KEY).json()) == 1

    r = client.patch(f"/customers/{c['id']}", json={"company": "Aru Beauty Studio"}, headers=KEY)
    assert r.json()["company"] == "Aru Beauty Studio" and r.json()["phone"] == "+77011234567"

    assert client.delete(f"/customers/{c['id']}", headers=KEY).status_code == 204
    assert client.get(f"/customers/{c['id']}", headers=KEY).status_code == 404


def test_validation(client):
    assert client.post("/customers", json={"name": ""}, headers=KEY).status_code == 422
    assert client.post("/customers", json={"name": "X", "email": "not-an-email"}, headers=KEY).status_code == 422
    c = make_customer(client)
    assert client.post("/deals", json={"customer_id": c["id"], "title": "Site", "amount": -5},
                       headers=KEY).status_code == 422


def test_notes(client):
    c = make_customer(client)
    client.post(f"/customers/{c['id']}/notes", json={"text": "Called, wants a quote"}, headers=KEY)
    client.post(f"/customers/{c['id']}/notes", json={"text": "Sent the quote"}, headers=KEY)
    notes = client.get(f"/customers/{c['id']}/notes", headers=KEY).json()
    assert [n["text"] for n in notes] == ["Sent the quote", "Called, wants a quote"]  # newest first
    assert client.post("/customers/999/notes", json={"text": "x"}, headers=KEY).status_code == 404


def test_deals_and_pipeline(client):
    c = make_customer(client)
    ids = []
    for title, amount, stage in [("Bot", 150000, "lead"), ("Site", 300000, "proposal"),
                                 ("CRM", 500000, "won"), ("Ads", 100000, "lost")]:
        r = client.post("/deals", json={"customer_id": c["id"], "title": title, "amount": amount, "stage": stage},
                        headers=KEY)
        ids.append(r.json()["id"])

    assert [d["title"] for d in client.get("/deals?stage=proposal", headers=KEY).json()] == ["Site"]

    p = client.get("/pipeline", headers=KEY).json()
    by = {s["stage"]: s for s in p["stages"]}
    assert by["lead"]["amount"] == 150000 and by["contacted"]["deals"] == 0
    assert p["open_amount"] == 450000 and p["won_amount"] == 500000 and p["win_rate"] == 0.5


def test_closed_deals_cannot_move(client):
    c = make_customer(client)
    d = client.post("/deals", json={"customer_id": c["id"], "title": "CRM", "stage": "won"}, headers=KEY).json()
    assert client.patch(f"/deals/{d['id']}", json={"stage": "lead"}, headers=KEY).status_code == 409
    # editing other fields of a closed deal is still allowed
    assert client.patch(f"/deals/{d['id']}", json={"amount": 10}, headers=KEY).json()["amount"] == 10


def test_deal_for_unknown_customer(client):
    assert client.post("/deals", json={"customer_id": 42, "title": "X"}, headers=KEY).status_code == 404
