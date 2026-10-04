# Mini CRM API

A REST API for a small business CRM: **customers, a deals pipeline and notes**, with search,
pagination, API-key auth and a pipeline summary endpoint. Interactive docs are generated
automatically at `/docs`.

Built with **FastAPI, SQLAlchemy 2, PostgreSQL** and Docker.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/customers` | Create a customer |
| GET | `/customers?q=&limit=&offset=` | List / search by name, phone, email, company |
| GET / PATCH / DELETE | `/customers/{id}` | Read, partial update, delete (cascades deals and notes) |
| POST / GET | `/customers/{id}/notes` | Add a note / list notes (newest first) |
| POST | `/deals` | Create a deal for a customer |
| GET | `/deals?stage=&customer_id=` | List deals with filters |
| PATCH | `/deals/{id}` | Update title, amount or stage (won/lost deals can't change stage) |
| GET | `/pipeline` | Count and amount per stage, open amount, won amount, win rate |

All endpoints require the `X-API-Key` header (constant-time comparison). Input is validated with
Pydantic; errors come back as standard JSON (401, 404, 409, 422).

Pipeline stages: `lead → contacted → proposal → won / lost`.

## Example

```bash
curl -X POST localhost:8000/customers -H "X-API-Key: $CRM_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"name": "Aigerim", "phone": "+77011234567", "company": "Aru Beauty"}'

curl localhost:8000/pipeline -H "X-API-Key: $CRM_API_KEY"
```

```json
{
  "stages": [{"stage": "lead", "deals": 1, "amount": 150000}, "..."],
  "open_amount": 450000,
  "won_amount": 500000,
  "win_rate": 0.5
}
```

## Run with Docker (PostgreSQL)

```bash
printf 'POSTGRES_PASSWORD=change-me\nCRM_API_KEY=change-me-too\n' > .env
docker compose up -d --build
open http://localhost:8000/docs
```

## Run locally (SQLite)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
CRM_API_KEY=dev .venv/bin/uvicorn app.main:app --reload
```

## Tests

```bash
.venv/bin/pip install pytest httpx2
.venv/bin/python -m pytest
```

8 API tests cover auth, CRUD, search, validation, notes, the pipeline maths and closed-deal rules,
using an isolated in-memory database.

## Notes for production

Tables are created on startup for convenience; a real deployment would manage schema changes with
Alembic migrations.
