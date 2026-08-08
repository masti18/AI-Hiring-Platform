"""Requirement Intake service.

Objective: turn a raw hiring brief into a persisted, structured role.

Data flow:
    raw brief (+ optional structured filters)
      -> parse stated vs hidden filters (explicit args + inline directives)
      -> build a structured JD from STATED information only
      -> (optional) LLM enrichment of the JD summary
      -> guard: hidden rules must never leak into JD text
      -> persist role_requirement + write an audit record

Where AI sits: the LLM adapter optionally enriches the JD summary. The pipeline
is fully deterministic and offline-safe when no usable LLM output is available
(e.g. no OPENAI_API_KEY), so the module works without external calls.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.adapters.llm import LLMMessage, LLMProvider
from app.models.role_requirement import RoleRequirement
from app.schemas.requirements import (
    IntakeResult,
    JobDescription,
    RequirementIntakeRequest,
)
from app.schemas.rules import RulePredicate
from app.services.audit import record_audit_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_VALID_OPERATORS = {
    "eq",
    "neq",
    "lt",
    "lte",
    "gt",
    "gte",
    "in",
    "not_in",
    "contains",
    "between",
}

_OPERATOR_TEXT = {
    "eq": "=",
    "neq": "!=",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
    "in": "in",
    "not_in": "not in",
    "contains": "contains",
    "between": "between",
}

_LIST_OPERATORS = {"in", "not_in", "between"}


class RequirementLeakError(RuntimeError):
    """Raised if a hidden filter would be exposed in externally rendered JD text."""


def _coerce(token: str):
    token = token.strip()
    for caster in (int, float):
        try:
            return caster(token)
        except ValueError:
            continue
    return token


def _parse_rule_line(payload: str) -> RulePredicate | None:
    """Parse `<field> <operator> <value>` into a RulePredicate, or None if invalid."""
    parts = payload.strip().split(None, 2)
    if len(parts) < 3:
        return None
    field, operator, raw_value = parts[0], parts[1].lower(), parts[2].strip()
    if operator not in _VALID_OPERATORS:
        return None

    if operator in _LIST_OPERATORS:
        value = [_coerce(v) for v in raw_value.split(",") if v.strip()]
    else:
        value = _coerce(raw_value)

    return RulePredicate(field=field, operator=operator, value=value)


def _extract_inline_directives(
    brief: str,
) -> tuple[list[RulePredicate], list[RulePredicate], list[str]]:
    """Pull `HIDDEN:` / `STATED:` directive lines out of the brief.

    Returns (stated, hidden, remaining_lines) where remaining_lines is the brief
    text with directive lines removed (used to build the human-readable JD).
    """
    stated: list[RulePredicate] = []
    hidden: list[RulePredicate] = []
    remaining: list[str] = []

    for line in brief.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("hidden:"):
            rule = _parse_rule_line(stripped.split(":", 1)[1])
            if rule is not None:
                hidden.append(rule)
        elif lowered.startswith("stated:"):
            rule = _parse_rule_line(stripped.split(":", 1)[1])
            if rule is not None:
                stated.append(rule)
        else:
            remaining.append(line)

    return stated, hidden, remaining


def _render_predicate(rule: RulePredicate) -> str:
    value = rule.value
    if isinstance(value, list):
        value_text = ", ".join(str(v) for v in value)
    else:
        value_text = str(value)
    operator_text = _OPERATOR_TEXT.get(rule.operator, rule.operator)
    return f"{rule.field} {operator_text} {value_text}".strip()


def _dedupe(rules: list[RulePredicate]) -> list[RulePredicate]:
    seen: set[str] = set()
    unique: list[RulePredicate] = []
    for rule in rules:
        key = json.dumps(rule.model_dump(), sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            unique.append(rule)
    return unique


def _assert_no_leak(job_description: JobDescription, hidden: list[RulePredicate]) -> None:
    """Defensive guard: no hidden field/value/description token may appear in JD text."""
    rendered = json.dumps(job_description.model_dump(), default=str).lower()
    for rule in hidden:
        tokens: list[str] = [rule.field]
        if rule.description:
            tokens.append(rule.description)
        values = rule.value if isinstance(rule.value, list) else [rule.value]
        tokens.extend(str(v) for v in values)
        for token in tokens:
            token_str = str(token).strip().lower()
            if len(token_str) >= 3 and token_str in rendered:
                raise RequirementLeakError(
                    f"Hidden rule token '{token}' leaked into job description text."
                )


class RequirementIntakeService:
    """Extracts structured intake output from a raw brief."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm

    def _collect(
        self, request: RequirementIntakeRequest
    ) -> tuple[list[RulePredicate], list[RulePredicate], JobDescription]:
        inline_stated, inline_hidden, remaining = _extract_inline_directives(request.raw_brief)
        stated = _dedupe([*request.stated_filters, *inline_stated])
        hidden = _dedupe([*request.hidden_filters, *inline_hidden])
        job_description = self._build_job_description(request, remaining, stated)
        return stated, hidden, job_description

    def parse(self, request: RequirementIntakeRequest) -> IntakeResult:
        """Deterministic, offline extraction (no LLM call)."""
        stated, hidden, job_description = self._collect(request)
        _assert_no_leak(job_description, hidden)
        return IntakeResult(
            stated_filters=stated,
            hidden_filters=hidden,
            job_description=job_description,
            llm_metadata={"used": False, "reason": "deterministic_parse"},
        )

    async def parse_async(self, request: RequirementIntakeRequest) -> IntakeResult:
        """Extraction with optional LLM enrichment of the JD summary."""
        stated, hidden, job_description = self._collect(request)
        llm_metadata: dict = {"used": False, "reason": "no_llm_provider"}

        if self.llm is not None:
            job_description, llm_metadata = await self._enrich_summary(request, job_description)

        _assert_no_leak(job_description, hidden)
        return IntakeResult(
            stated_filters=stated,
            hidden_filters=hidden,
            job_description=job_description,
            llm_metadata=llm_metadata,
        )

    def _build_job_description(
        self,
        request: RequirementIntakeRequest,
        remaining_lines: list[str],
        stated: list[RulePredicate],
    ) -> JobDescription:
        prose = [ln.strip() for ln in remaining_lines if ln.strip()]

        def is_bullet(line: str) -> bool:
            return line.lstrip().startswith(("-", "*", "\u2022"))

        bullets = [ln.lstrip("-*\u2022 ").strip() for ln in prose if is_bullet(ln)]
        paragraphs = [ln for ln in prose if not is_bullet(ln)]
        summary = paragraphs[0] if paragraphs else f"{request.title} role."

        return JobDescription(
            title=request.title,
            summary=summary,
            responsibilities=bullets,
            requirements=[_render_predicate(rule) for rule in stated],
            nice_to_have=[],
            location=request.location,
            employment_type=request.employment_type,
        )

    async def _enrich_summary(
        self,
        request: RequirementIntakeRequest,
        job_description: JobDescription,
    ) -> tuple[JobDescription, dict]:
        assert self.llm is not None
        messages = [
            LLMMessage(
                role="system",
                content=(
                    "You write concise, inclusive job-description summaries. "
                    "Return JSON with a single key 'summary'. Never include internal "
                    "or confidential hiring rules."
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Title: {request.title}\n"
                    f"Draft summary: {job_description.summary}\n"
                    f"Responsibilities: {job_description.responsibilities}"
                ),
            ),
        ]
        result = await self.llm.complete(messages, response_schema={"summary": "string"})
        data = result.data if isinstance(result.data, dict) else {}
        enriched = data.get("summary")

        if isinstance(enriched, str) and enriched.strip() and not data.get("stub"):
            job_description = job_description.model_copy(update={"summary": enriched.strip()})
            return job_description, {
                "used": True,
                "provider": result.provider,
                "model": result.model,
                "usage": result.usage,
            }

        return job_description, {
            "used": False,
            "reason": "stub_or_empty",
            "provider": result.provider,
            "model": result.model,
        }


async def create_requirement(
    session: AsyncSession,
    request: RequirementIntakeRequest,
    *,
    llm: LLMProvider | None = None,
) -> RoleRequirement:
    """Run intake, persist the role requirement, and write an audit record."""
    result = await RequirementIntakeService(llm=llm).parse_async(request)

    requirement = RoleRequirement(
        company_id=request.company_id,
        title=request.title,
        raw_brief=request.raw_brief,
        status="intake_complete",
        stated_filters=[rule.model_dump() for rule in result.stated_filters],
        hidden_filters=[rule.model_dump() for rule in result.hidden_filters],
        job_description=result.job_description.model_dump(),
        llm_metadata=result.llm_metadata,
    )
    session.add(requirement)
    await session.flush()

    await record_audit_event(
        session,
        company_id=request.company_id,
        action="requirement.intake_completed",
        entity_type="role_requirement",
        entity_id=requirement.id,
        payload={
            "title": requirement.title,
            "status": requirement.status,
            "stated_filter_count": len(result.stated_filters),
            "hidden_filter_count": len(result.hidden_filters),
            "llm_enriched": bool(result.llm_metadata.get("used")),
        },
    )

    await session.commit()
    await session.refresh(requirement)
    return requirement


async def get_requirement(
    session: AsyncSession,
    requirement_id: uuid.UUID,
    company_id: uuid.UUID,
) -> RoleRequirement | None:
    """Fetch a single requirement, scoped to its company (tenant isolation)."""
    stmt = select(RoleRequirement).where(
        RoleRequirement.id == requirement_id,
        RoleRequirement.company_id == company_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_requirements(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> list[RoleRequirement]:
    """List all requirements for a company, newest first."""
    stmt = (
        select(RoleRequirement)
        .where(RoleRequirement.company_id == company_id)
        .order_by(RoleRequirement.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
