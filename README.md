# AI Hiring Platform (HireFlow)

College capstone: an autonomous AI hiring system that takes a role from a raw hiring brief to a signed offer with minimal-to-zero blocking human intervention.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js 14 (App Router), React, TypeScript, Tailwind, shadcn/ui |
| Backend | FastAPI (Python 3.11+), async |
| Orchestration | LangGraph (stateful graph — retry / branch / escalate) |
| LLM | OpenAI GPT-4.x via swappable provider interface |
| Data | PostgreSQL (SoR), Redis (queues/cache/session), Qdrant (embeddings) |
| Voice | Deepgram (STT), ElevenLabs (TTS), LiveKit (transport) — adapters stubbed |
| Infra | Docker Compose (local) → AWS later |
| Auth | JWT; DB schema multi-tenant-ready (`company_id` everywhere) |

## Architecture principles

### Auto-gate
Two review checkpoints (post-sourcing, post-AI-call) **always** run policy evaluation and **always** log decision + reasoning to the audit trail. Whether a gate blocks for a human is controlled by per-company flags:

- `auto_approve_gate1` (default `true`)
- `auto_approve_gate2` (default `true`)

Never hardcode a human-blocking step.

### Hidden rules
Requirement intake separates **stated** filters (visible in external JD) from **hidden** filters (internal-only). Hidden rules are structured JSON predicates (`field`, `operator`, `value`) enforced at sourcing/scoring — never leaked into generated JD text.

### AI outputs
JD text, candidate scores, and call evaluations are stored as **structured JSON**, not prose-only.

## Monorepo layout

```
/
├── frontend/                 # Next.js 14 App Router
├── backend/
│   ├── alembic/              # Migrations (never hand-edit prod schema)
│   ├── app/
│   │   ├── models/           # SQLAlchemy ORM (multi-tenant ready)
│   │   ├── api/              # FastAPI routers
│   │   ├── agents/           # LangGraph pipeline + auto-gates
│   │   ├── services/         # Domain services (audit, health, …)
│   │   ├── adapters/         # External integrations (LLM, email, voice, …)
│   │   ├── schemas/          # Pydantic contracts
│   │   └── core/             # Config, DB, security, logging
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml        # postgres, redis, qdrant (+ optional full profile)
├── .env.example
└── README.md
```

## Quick start

### 1. Infra

```bash
cp .env.example .env
docker compose up -d postgres redis qdrant
```

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Health: `GET http://localhost:8000/health`

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:3000`

### Full stack via Compose

```bash
docker compose --profile full up --build
```

## Working agreements

1. Before coding a feature: restate objective → data model → API contract → where AI sits → failure cases → then code.
2. Alembic migrations for every schema change.
3. External integrations behind adapters (mockable / swappable).
4. Flag any request that would break modularity, skip the audit trail, or hardcode company-specific rules into pipeline code.

## Milestone 0 status

- [x] Monorepo skeleton
- [x] FastAPI app + health endpoints
- [x] LangGraph graph skeleton with config-driven gates
- [x] LLM / email / voice adapter interfaces
- [x] Alembic + initial `companies` migration (auto-gate flags)
- [x] Next.js 14 + Tailwind + shadcn/ui button primitive
- [x] Docker Compose: postgres, redis, qdrant
