# AI Hiring Platform — Build Prompt Pack

How to use this: paste the **Master Context Prompt** into a new Cursor project (or Claude Code, `claude` in your repo root) once, at the start. Then paste each **Milestone Prompt** in order, one per session. Each is self-contained — objective, schema, APIs, AI logic, edge cases — so the tool builds complete, working code without needing you to fill gaps. Don't skip ahead; each milestone assumes the previous one's schema/APIs exist.

Design decision baked into every prompt below: **auto-gate architecture** — both human review gates exist as real, auditable decision points with configurable thresholds, but default to full autonomy (no blocking UI wait). Change `AUTO_APPROVE=true/false` in config if you want to demo the manual-gate mode too.

---

## 0. Master Context Prompt (paste once, first)

```
You are acting as lead engineer on a 6-month college capstone: an autonomous
AI hiring platform that takes a role from a raw hiring brief to a signed
offer, with minimal-to-zero blocking human intervention.

STACK (fixed, do not deviate without flagging why):
- Frontend: Next.js 14 (App Router), React, TypeScript, Tailwind, shadcn/ui
- Backend: FastAPI (Python 3.11+), async throughout
- Orchestration: LangGraph for the agent pipeline (stateful graph, not a
  linear chain — nodes can retry, branch, and escalate)
- LLM: OpenAI GPT-4.x via API, with a swappable provider interface
- Databases: PostgreSQL (system of record), Redis (queues/cache/session),
  Qdrant (vector store for resume/JD embeddings), Neo4j (optional, only if
  we need candidate-relationship graph queries later — do not build this
  until milestone 6 unless a milestone prompt says so)
- Voice: Deepgram (STT), ElevenLabs (TTS), LiveKit (call transport)
- Infra: Docker Compose for local dev, structured for later AWS deploy
- Auth: JWT-based, single tenant is fine for MVP but design the DB schema
  multi-tenant-ready (company_id foreign key everywhere)

ARCHITECTURE PRINCIPLE — AUTO-GATE:
The pipeline has two review checkpoints (post-sourcing, post-AI-call).
Each checkpoint is a real node in the graph that ALWAYS runs a policy
evaluation and ALWAYS logs a decision + reasoning to an audit table.
Whether it blocks for a human click or auto-proceeds is controlled by a
per-company config flag (auto_approve_gate1, auto_approve_gate2), default
true. Never hardcode a human-blocking step — it must be a config-driven
branch in the graph.

HIDDEN RULES:
Every requirement intake must separate "stated" filters (visible in the
external JD) from "hidden" filters (internal-only, e.g. max commute
distance, culture-fit signals). Hidden rules are stored as structured,
machine-evaluable predicates (JSON rule objects: field, operator, value —
not free text) and are enforced at the sourcing/scoring stage, never
leaked into generated JD text.

WORKING STYLE FOR THIS PROJECT:
1. Before writing code for any feature, restate: objective → data model
   changes → API contract (request/response shapes) → where AI/LLM logic
   sits and what it returns → failure/edge cases → then code.
2. Every AI-generated output (JD text, candidate score, call evaluation)
   must be stored as structured JSON, never just prose, so downstream
   nodes and the audit trail can consume it.
3. Write Alembic migrations for every schema change, don't hand-edit prod
   schema.
4. Every external integration (LinkedIn, WhatsApp, email, Deepgram,
   ElevenLabs) goes behind an interface/adapter so it can be mocked in
   tests and swapped later.
5. Flag — don't silently accept — any request from me that would break
   modularity, skip the audit trail, or hardcode a company-specific rule
   into pipeline code instead of the rules engine.

Set up the repo now: monorepo with /frontend, /backend, /docker-compose.yml,
/backend/alembic, /backend/app/{models,api,agents,services,adapters}.
Confirm the skeleton compiles and the docker-compose stack (postgres,
redis, qdrant) starts before moving to Milestone 1.
```

---

## 1. Milestone 1 — Requirement Intake, Data Model, Hidden Rules (Month 1)

```
OBJECTIVE: Build the requirement-intake flow: a business user enters an
unstructured hiring brief (free text) and the system extracts a structured
job requirement PLUS separates stated vs hidden rules, storing both as
machine-enforceable predicates.

DATA MODEL (design full Postgres schema via SQLAlchemy + Alembic migration):
- companies (id, name, config JSONB — includes auto_approve_gate1/2,
  scoring_weights)
- roles (id, company_id, title, raw_brief TEXT, status, created_at)
- requirement_rules (id, role_id, rule_type ENUM['stated','hidden'],
  field, operator ENUM['eq','lt','gt','lte','gte','in','contains'],
  value JSONB, weight FLOAT, description TEXT)
- audit_log (id, role_id, candidate_id nullable, stage, decision,
  reasoning TEXT, actor ENUM['ai','human'], created_at) — this table gets
  written to by every future milestone, build it generically now.

API (FastAPI):
- POST /roles — accepts raw_brief text, kicks off extraction
- GET /roles/{id}/rules — returns extracted stated + hidden rules for
  human confirmation/edit before locking
- PATCH /roles/{id}/rules/{rule_id} — edit a rule (human can correct
  extraction mistakes at intake time — this is not a review gate, it's a
  setup step, so it's fine for this one to be a real UI form)
- POST /roles/{id}/lock — finalizes the ruleset, role moves to "sourcing"
  status

AI LOGIC:
- LangGraph node: takes raw_brief, prompts the LLM to output STRICT JSON
  matching the requirement_rules schema, classifying each extracted
  requirement as stated or hidden using these heuristics: anything about
  compensation banding internals, "don't tell candidates this", distance/
  location constraints, subjective culture terms ("positive attitude",
  "founder mindset") defaults to hidden unless the brief explicitly says
  it's fine to disclose.
- Must handle: brief has no explicit hidden rules (don't invent any),
  brief is contradictory (flag in audit_log, don't silently pick one),
  brief is too vague to extract structured fields (return a rules array
  with a "needs_clarification" flag per field rather than guessing).

FRONTEND: simple form (paste brief → view extracted rules table, stated
vs hidden clearly separated visually → edit → lock).

EDGE CASES TO HANDLE IN CODE, NOT JUST NOTE:
- Empty/garbage brief input
- LLM returns malformed JSON (retry once with a repair prompt, then fail
  loudly, never silently drop rules)
- Duplicate rule extraction (same field twice) — merge, don't duplicate

Build this fully, including migration, working API, and a functional
(not polished) frontend page. Write 3-5 pytest tests covering the
extraction edge cases above with a mocked LLM response.
```

---

## 2. Milestone 2 — JD Generation + Sourcing Engine (Month 2)

```
OBJECTIVE: Two connected features. (a) Generate an external-facing JD from
the locked role+rules, guaranteed to never leak hidden rules. (b) Source
candidates from resumes/LinkedIn, score against stated+hidden rules, and
rank.

DATA MODEL ADDITIONS:
- job_descriptions (id, role_id, generated_text, version, created_at)
- candidates (id, role_id, source ENUM['upload','linkedin','other'],
  raw_resume_text, parsed_profile JSONB, linkedin_url nullable,
  embedding_id — pointer into Qdrant, created_at)
- candidate_scores (id, candidate_id, rule_id, passed BOOLEAN,
  score_contribution FLOAT, reasoning TEXT)
- candidate_status (id, candidate_id, stage ENUM['sourced','gate1_pending',
  'gate1_approved','gate1_rejected', ...], updated_at)

API:
- POST /roles/{id}/jd/generate — returns generated JD text
- POST /roles/{id}/candidates/ingest — accepts resume files (PDF/DOCX) or
  a LinkedIn profile URL/scrape payload, parses, stores, embeds, scores
- GET /roles/{id}/candidates?sorted_by=score — ranked shortlist

AI LOGIC:
- JD generation: prompt template that takes ONLY the stated rules +
  role title/context as input (physically do not pass hidden rules into
  this prompt's context — this is a code-level guarantee, not just an
  instruction to the LLM).
- Resume parsing: extract structured profile (skills, years experience,
  location, past roles) from raw text via LLM, store as JSONB.
- Scoring: for each candidate, evaluate every requirement_rule
  (stated+hidden) against parsed_profile. Hard rules (hidden, boolean —
  e.g. distance) are pass/fail gates: a fail here means the candidate is
  excluded from the ranked list entirely, never just down-weighted —
  this is the ">15km candidate never reaches outreach" guarantee from the
  brief, enforce it as a hard filter in the query, not a soft score.
  Soft rules contribute to a weighted score.
- LinkedIn sourcing: since LinkedIn scraping has ToS/legal restrictions,
  build the adapter interface now but implement it against manually
  provided LinkedIn profile exports or a compliant API/partner data
  source — do not build a scraper that violates LinkedIn's terms. Flag
  this limitation back to me explicitly rather than silently building a
  scraper.

EDGE CASES:
- Resume with no extractable location (hidden distance rule can't
  evaluate) — exclude with reasoning "insufficient data", don't default
  to pass
- Duplicate candidate across sources — dedupe on email/name+phone fuzzy
  match
- Malformed/corrupt resume file — reject with clear error, log, don't
  crash the batch ingest

Build fully: migrations, working ingest+scoring pipeline, ranked
candidate list API + simple frontend table. Tests covering the hard-gate
distance-filter guarantee specifically, since that's a "what good looks
like" requirement in the brief.
```

---

## 3. Milestone 3 — Review Console (Auto-Gate) + Multi-Channel Outreach (Month 3)

```
OBJECTIVE: Build Gate 1 as an auto-gate (policy-evaluated, config-driven,
audited) and the outreach engine that fires for approved candidates.

DATA MODEL ADDITIONS:
- outreach_messages (id, candidate_id, channel ENUM['email','whatsapp',
  'linkedin'], template_used, sent_text, status ENUM['queued','sent',
  'delivered','responded','failed'], sent_at, response_text nullable)
- gate_decisions (id, candidate_id, gate ENUM['gate1','gate2'], decision
  ENUM['approved','rejected'], threshold_used FLOAT, actual_score FLOAT,
  actor ENUM['ai_auto','human'], reasoning TEXT, created_at)

API:
- POST /roles/{id}/candidates/{cid}/gate1/evaluate — runs the policy
  (score >= company.config.gate1_threshold), writes gate_decisions +
  audit_log; if company.config.auto_approve_gate1 is false, sets status
  to gate1_pending instead and stops (for the manual-demo mode)
- GET /roles/{id}/gate1/pending — console view, only populated when
  auto-approve is off
- POST /roles/{id}/candidates/{cid}/gate1/override — human override
  endpoint, always available regardless of auto mode, always logged as
  actor=human in gate_decisions (this satisfies "human can always audit
  and intervene" without making intervention mandatory)
- POST /candidates/{cid}/outreach/send — triggers multi-channel send for
  an approved candidate

AI LOGIC:
- Message personalization: generate email/WhatsApp/LinkedIn message text
  per candidate using their parsed_profile + JD, one LLM call producing
  all three channel variants in one structured response (consistent tone
  across channels).
- Response classification: incoming replies (webhook payloads) get
  classified by LLM as interested/not-interested/needs-info/out-of-office,
  structured output, drives status transitions.

ADAPTERS (build behind interfaces, mock-able):
- Email: SMTP or SendGrid/SES adapter
- WhatsApp: WhatsApp Business API adapter (note: requires business
  verification — build against the API contract with a mock provider for
  dev/demo if you don't have approved access yet, flag this to me)
- LinkedIn: LinkedIn does not have a public messaging API for this use
  case — flag this explicitly, do not scrape/automate outside ToS; build
  the adapter interface so it's a no-op/manual-export stub for the demo.

EDGE CASES:
- Candidate has no email/phone on file for a channel — skip that channel,
  log, don't fail the whole outreach batch
- Duplicate outreach (candidate already contacted for this role) —
  idempotency check before send
- Rate limiting per channel (don't blast — add a simple per-company
  send-rate cap)

Build fully with migrations, working gate1 auto-evaluation + override
endpoints, outreach send pipeline with at least the email adapter fully
functional (others can be stubbed with explicit TODO + the flag above),
and a console frontend page showing gate decisions with reasoning
(audit-visible even when auto mode skipped the human).
```

---

## 4. Milestone 4 — The Calling Agent (Month 4, the core module)

```
OBJECTIVE: The make-or-break module. An AI voice agent that conducts a
first-round interview near-indistinguishable from the company's own HR,
using a company/role-specific knowledge base and explicit rule enforcement,
producing a structured evaluation.

DATA MODEL ADDITIONS:
- knowledge_bases (id, company_id, role_id nullable — company-level or
  role-specific, culture_cues JSONB, ideal_answer_patterns JSONB,
  interviewer_phrasing_examples JSONB)
- call_sessions (id, candidate_id, role_id, status, transcript JSONB,
  audio_url, started_at, ended_at)
- call_evaluations (id, call_session_id, fit_score FLOAT, strengths TEXT[],
  risks TEXT[], rule_results JSONB — per-rule pass/fail with reasoning,
  recommendation ENUM['advance','reject','borderline'])

API:
- POST /roles/{id}/knowledge-base — set up KB (culture cues, phrasing
  examples, ideal answers) — this is largely human-authored config, not
  AI-generated, so build a structured form, not just a text blob
- POST /candidates/{cid}/call/initiate — starts a LiveKit session, agent
  places/receives call
- Webhook handlers for call events (started, transcript chunk, ended)
- GET /candidates/{cid}/call/evaluation — structured result

AI LOGIC (this is the hard part, spend real design effort here):
- LangGraph conversational agent with: (1) a system prompt built from the
  knowledge_base + requirement_rules for this role, (2) turn-by-turn
  state tracking so it knows which topics/rules it has already probed,
  (3) explicit instruction to ask natural follow-ups on vague answers
  rather than accepting them, (4) a hard stop list — hidden rules that
  must be verified in-conversation (e.g. commute distance confirmation)
  get an explicit required-question the agent cannot skip.
- STT (Deepgram) → LLM turn logic → TTS (ElevenLabs), with interruption
  handling: if the candidate speaks while the agent is talking, the agent
  must stop generating/speaking and re-process, not talk over them.
- Post-call: separate LLM pass over the full transcript produces the
  structured call_evaluations record — fit_score, strengths, risks, and
  a rule_results entry for every rule that was supposed to be checked in
  the call, explicitly flagging any rule that was NOT actually verified
  (don't let the model claim it checked something it didn't ask about).

EDGE CASES:
- Candidate doesn't answer / call fails to connect — retry policy (e.g.
  2 attempts, then mark as unreachable, don't silently drop from pipeline)
- Candidate gives an answer that directly fails a hard hidden rule mid-call
  (e.g. states they live 40km away) — agent should still complete the
  interview naturally (don't hang up abruptly, that's a bad candidate
  experience) but the evaluation must hard-flag the rule failure
- Background noise / bad transcription — evaluation should note low
  transcript confidence rather than scoring on garbled text as if
  it were reliable
- Candidate asks the agent something outside its knowledge base — agent
  should say it'll follow up rather than hallucinating company facts

This module needs test transcripts. Before wiring up real telephony,
build a text-mode simulation harness (feed the agent scripted candidate
responses, inspect the resulting evaluation JSON) so the conversation
logic can be iterated on cheaply. Then wire real Deepgram/ElevenLabs/
LiveKit once the logic is solid. Build fully, including the simulation
harness — this is the module the brief calls "make or break," treat it
that way.
```

---

## 5. Milestone 5 — Scheduling, Gate 2, Offer & Close (Month 5)

```
OBJECTIVE: Gate 2 (post-call auto-evaluation, same auto-gate pattern as
Gate 1), scheduling for final rounds, and offer rollout with acceptance
tracking.

DATA MODEL ADDITIONS:
- interview_slots (id, role_id, panel_member, start_time, end_time,
  status ENUM['available','booked'])
- final_interviews (id, candidate_id, slot_id, human_eval_notes TEXT,
  human_recommendation)
- offers (id, candidate_id, role_id, compensation JSONB, status
  ENUM['drafted','sent','accepted','declined','expired'], sent_at,
  responded_at)

API:
- Gate 2 mirrors Gate 1's pattern exactly (evaluate/override endpoints,
  same gate_decisions table, config-driven auto-approve)
- POST /roles/{id}/scheduling/propose — AI proposes slots based on panel
  availability + candidate stated availability from earlier outreach
  response
- POST /candidates/{cid}/offer/generate — drafts offer using
  company.config compensation bands + role data
- POST /candidates/{cid}/offer/send, /offer/webhook (candidate response)

AI LOGIC:
- Gate 2 evaluation reuses the call_evaluations.fit_score against
  company.config.gate2_threshold — same pattern as Gate 1, don't
  reinvent it.
- Scheduling: constraint-solving over available slots × candidate
  availability, not just "first available" — should handle no-overlap
  case explicitly (propose next available window, notify, don't silently
  fail)
- Offer letter generation: templated, pulling from compensation JSONB and
  role data, human-reviewable before send (offer letters are legally
  significant — this step should NOT be auto-sent without at least being
  logged with full generated content in audit_log even in auto mode)
- Acceptance tracking: parse candidate's reply (email/webhook) for
  accept/decline/negotiate intent, structured classification

EDGE CASES:
- Candidate wants to negotiate — classify as "negotiate" status, don't
  auto-modify the offer, surface for human (this is explicitly the one
  place the brief implies human judgment on comp matters)
- Offer expires with no response — status transition + reminder logic
- Panel member cancels a booked slot — reschedule flow

Build fully with migrations and working endpoints for the full flow;
frontend can be minimal list/detail views.
```

---

## 6. Milestone 6 — Integration, Security, Consent, Pilot, Demo (Month 6)

```
OBJECTIVE: Tie the full graph together end-to-end, harden it, and prepare
the pilot + demo the brief asks for.

TASKS:
1. Wire the LangGraph pipeline end-to-end: Requirement → JD → Sourcing →
   Gate1 → Outreach → Call → Gate2 → Scheduling → Offer → Close, as one
   orchestrated graph with proper state persistence (so a run can be
   inspected/resumed at any node, not just a black-box script).
2. Consent & privacy: candidate consent capture before resume storage and
   before any AI call (a clear consent record, timestamp, what they
   consented to — store this, don't just assume it), data retention
   policy config per company, PII handling review pass (encrypt at rest
   for candidate PII fields specifically, not just the whole DB).
3. Security pass: auth on every endpoint, rate limiting, input validation
   audit especially on file uploads and webhook handlers, secrets out of
   code into env/secret manager.
4. End-to-end test: run one full synthetic role through the entire
   pipeline with test data, verify every stage's audit_log entries exist
   and are coherent, verify the hidden-rule guarantee holds (a candidate
   who fails a hard hidden rule never appears in outreach even after all
   the intermediate steps).
5. Demo prep: a seed script that populates one realistic role + a batch
   of synthetic candidates (mix of qualifiers/disqualifiers) so the demo
   is reproducible, plus a short write-up (README) covering: architecture
   diagram, key design decisions (especially the auto-gate pattern and
   why), what's mocked/stubbed (LinkedIn, WhatsApp if not fully live) and
   why, and known limitations.

Treat this milestone as the one that turns "it works on my machine" into
"it works when someone else presses the button." Build the seed script,
the E2E test, and the README as real deliverables, not afterthoughts.
```

---

**Note on the two integration gaps flagged above (LinkedIn scraping, WhatsApp Business API access):** these aren't things a prompt can solve — WhatsApp Business API needs Meta approval (can take days), and LinkedIn has no compliant messaging/sourcing API for this use case. Decide early whether to (a) demo with mocked adapters and be upfront about it in the viva, or (b) swap LinkedIn sourcing for a compliant alternative (candidate-uploaded resumes + a job board API). I'd flag this to Sunil now rather than discovering it in Month 3.
