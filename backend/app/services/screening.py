"""AI screening call orchestration (Milestone 3).

Pipeline for one candidate:
    load candidate + role (tenant-scoped)
      -> conduct a (mockable) voice call via the voice adapters, producing a
         structured transcript from the candidate's answers
      -> evaluate the transcript into a structured CallEvaluation
         (deterministic baseline, optionally enriched/overridden by an LLM)
      -> persist a screening_call
      -> run the post-AI-call auto-gate (gate2): ALWAYS evaluate + audit;
         blocking is config-driven via company.auto_approve_gate2
      -> return the call

Voice + LLM integrations stay behind adapter interfaces so the stage is mockable.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.adapters.llm import LLMMessage, LLMProvider
from app.adapters.voice import (
    CallTransportAdapter,
    MockCallTransportAdapter,
    MockSTTAdapter,
    MockTTSAdapter,
    SpeechToTextAdapter,
    TextToSpeechAdapter,
)
from app.agents.gates import evaluate_gate_policy
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.role_requirement import RoleRequirement
from app.models.screening_call import ScreeningCall
from app.schemas.screening import CallEvaluation, ScreeningCallRequest, TranscriptTurn
from app.services.audit import record_audit_event
from app.services.call_evaluation import (
    ADVANCE_THRESHOLD,
    DEFAULT_QUESTIONS,
    build_transcript,
    evaluate_transcript,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CandidateNotFound(LookupError):
    """Raised when the target candidate does not exist for the tenant."""


def _signal_tokens(role: RoleRequirement) -> set[str]:
    tokens = {tok for tok in re.split(r"[^a-z0-9]+", role.title.lower()) if len(tok) >= 3}
    for rule in role.stated_filters or []:
        field = str(rule.get("field", "")) if isinstance(rule, dict) else ""
        tokens |= {tok for tok in re.split(r"[^a-z0-9]+", field.lower()) if len(tok) >= 3}
    return tokens


async def _conduct_call(
    candidate: Candidate,
    transcript: list[TranscriptTurn],
    *,
    transport: CallTransportAdapter,
    tts: TextToSpeechAdapter,
    stt: SpeechToTextAdapter,
) -> dict:
    """Exercise the (mock) voice stack and return provider metadata."""
    room = await transport.create_room(f"screen-{candidate.id}")
    synthesized = 0
    transcribed = 0
    stt_provider = None
    for turn in transcript:
        if turn.speaker == "interviewer":
            synthesized += len(await tts.synthesize(turn.text))
        elif turn.text.strip():
            result = await stt.transcribe(turn.text.encode("utf-8"))
            stt_provider = result.get("provider")
            transcribed += 1
    return {
        "transport": room.get("provider"),
        "room": room.get("room"),
        "tts_bytes": synthesized,
        "stt": stt_provider,
        "answers_transcribed": transcribed,
    }


async def _maybe_llm_override(
    llm: LLMProvider | None,
    deterministic: CallEvaluation,
    role_title: str,
) -> tuple[CallEvaluation, dict]:
    if llm is None:
        return deterministic, {"used": False, "reason": "no_llm_provider"}

    messages = [
        LLMMessage(
            role="system",
            content=(
                "You are a hiring screener. Return JSON with 'overall_score' (0..1) "
                "and 'recommendation' ('advance'|'hold'|'reject')."
            ),
        ),
        LLMMessage(role="user", content=f"Role: {role_title}. Summary: {deterministic.reasoning}"),
    ]
    result = await llm.complete(messages, response_schema={"overall_score": "number"})
    data = result.data if isinstance(result.data, dict) else {}
    score = data.get("overall_score")
    rec = data.get("recommendation")
    if (
        not data.get("stub")
        and isinstance(score, int | float)
        and rec in {"advance", "hold", "reject"}
    ):
        enriched = deterministic.model_copy(
            update={"overall_score": round(float(score), 4), "recommendation": rec}
        )
        return enriched, {"used": True, "provider": result.provider, "model": result.model}
    return deterministic, {
        "used": False,
        "reason": "stub_or_invalid",
        "provider": result.provider,
        "model": result.model,
    }


async def conduct_screening(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    request: ScreeningCallRequest,
    *,
    llm: LLMProvider | None = None,
    transport: CallTransportAdapter | None = None,
    tts: TextToSpeechAdapter | None = None,
    stt: SpeechToTextAdapter | None = None,
) -> ScreeningCall:
    """Run an AI screening call for a candidate and evaluate it through gate2."""
    candidate = (
        await session.execute(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise CandidateNotFound(str(candidate_id))

    role = (
        await session.execute(
            select(RoleRequirement).where(RoleRequirement.id == candidate.role_requirement_id)
        )
    ).scalar_one_or_none()

    company = (
        await session.execute(select(Company).where(Company.id == company_id))
    ).scalar_one_or_none()
    auto_approve = bool(company.auto_approve_gate2) if company is not None else True

    if request.transcript is not None:
        transcript = list(request.transcript)
    else:
        questions = request.questions or DEFAULT_QUESTIONS
        transcript = build_transcript(questions, request.answers)

    providers = await _conduct_call(
        candidate,
        transcript,
        transport=transport or MockCallTransportAdapter(),
        tts=tts or MockTTSAdapter(),
        stt=stt or MockSTTAdapter(),
    )

    signal = _signal_tokens(role) if role is not None else None
    deterministic = evaluate_transcript(transcript, signal_tokens=signal)
    evaluation, llm_meta = await _maybe_llm_override(
        llm, deterministic, role.title if role is not None else candidate.name
    )
    providers["llm"] = llm_meta

    passed = evaluation.recommendation == "advance"
    policy_result = {
        "passed": passed,
        "checks": [
            {
                "name": "call_recommendation",
                "ok": passed,
                "recommendation": evaluation.recommendation,
                "overall_score": evaluation.overall_score,
                "advance_threshold": ADVANCE_THRESHOLD,
            }
        ],
    }
    decision = await evaluate_gate_policy(
        gate="gate2_post_ai_call",
        state={"company_id": str(company_id), "candidate_id": str(candidate_id)},
        auto_approve=auto_approve,
        policy_result=policy_result,
    )

    call = ScreeningCall(
        company_id=company_id,
        role_requirement_id=candidate.role_requirement_id,
        candidate_id=candidate_id,
        status="completed",
        transcript=[turn.model_dump() for turn in transcript],
        evaluation=evaluation.model_dump(),
        overall_score=evaluation.overall_score,
        recommendation=evaluation.recommendation,
        gate2_decision=dict(decision),
        providers=providers,
    )
    session.add(call)
    await session.flush()

    await record_audit_event(
        session,
        company_id=company_id,
        action="gate2_post_ai_call",
        entity_type="screening_call",
        entity_id=call.id,
        payload={
            "gate": decision["gate"],
            "action": decision["action"],
            "reasoning": decision["reasoning"],
            "recommendation": evaluation.recommendation,
            "overall_score": evaluation.overall_score,
            "candidate_id": str(candidate_id),
        },
    )

    await session.commit()
    await session.refresh(call)
    return call


async def list_screening_calls(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
) -> list[ScreeningCall]:
    stmt = (
        select(ScreeningCall)
        .where(
            ScreeningCall.candidate_id == candidate_id,
            ScreeningCall.company_id == company_id,
        )
        .order_by(ScreeningCall.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_screening_call(
    session: AsyncSession,
    call_id: uuid.UUID,
    company_id: uuid.UUID,
) -> ScreeningCall | None:
    stmt = select(ScreeningCall).where(
        ScreeningCall.id == call_id,
        ScreeningCall.company_id == company_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()
