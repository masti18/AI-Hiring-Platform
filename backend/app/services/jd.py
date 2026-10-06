"""Hiring brief intake + JD generation.

Hidden filters are never passed into JD generation prompts or written into JD text fields.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.adapters.llm import LLMMessage, LLMStructuredResult, get_llm_provider
from app.schemas.role import JobDescription
from app.schemas.rules import RulePredicate


JD_SCHEMA_HINT = {
    "title": "string",
    "summary": "string",
    "responsibilities": ["string"],
    "required_qualifications": ["string"],
    "preferred_qualifications": ["string"],
    "location": "string|null",
    "employment_type": "string|null",
    "benefits": ["string"],
    "stated_requirements": [{"field": "string", "operator": "string", "value": "any"}],
    "metadata": {"generated_by": "string"},
}


def _serialize_predicates(preds: list[RulePredicate]) -> list[dict[str, Any]]:
    return [p.model_dump() for p in preds]


def assert_no_hidden_leak(jd: dict[str, Any], hidden: list[dict[str, Any]]) -> None:
    """Fail closed if any hidden predicate value appears as a standalone token in JD prose."""
    if not hidden:
        return
    blob = json.dumps(jd, default=str).lower()
    for pred in hidden:
        # Check description notes and distinctive string values
        for key in ("description",):
            note = pred.get(key)
            if isinstance(note, str) and len(note) >= 8 and note.lower() in blob:
                raise ValueError(f"Hidden filter leaked into JD via {key}: {note[:40]}")
        value = pred.get("value")
        if isinstance(value, str) and len(value) >= 12 and value.lower() in blob:
            # Only flag long distinctive strings to avoid false positives on common words
            raise ValueError("Hidden filter value leaked into JD text")


def build_stub_jd(
    *,
    title: str,
    brief_text: str,
    location: str | None,
    employment_type: str | None,
    stated_filters: list[dict[str, Any]],
) -> JobDescription:
    reqs = [
        f"{p.get('field')} {p.get('operator')} {p.get('value')}"
        for p in stated_filters
    ]
    return JobDescription(
        title=title,
        summary=brief_text.strip()[:400] or f"Open role: {title}",
        responsibilities=[
            "Deliver on core responsibilities for this role",
            "Collaborate with cross-functional partners",
            "Uphold team quality and delivery standards",
        ],
        required_qualifications=reqs
        or [
            "Relevant professional experience",
            "Strong communication skills",
        ],
        preferred_qualifications=["Domain familiarity", "Evidence of ownership"],
        location=location,
        employment_type=employment_type,
        benefits=[],
        stated_requirements=stated_filters,
        metadata={"generated_by": "stub", "schema": "JobDescription/v1"},
    )


async def extract_filters_from_brief(brief_text: str) -> dict[str, list[dict[str, Any]]]:
    """LLM extracts stated vs hidden predicates. Returns structured lists."""
    provider = get_llm_provider()
    messages = [
        LLMMessage(
            role="system",
            content=(
                "You extract hiring filters as JSON. "
                "Return {\"stated\": [...], \"hidden\": [...]} where each item is "
                "{\"field\",\"operator\",\"value\",\"description\"}. "
                "Stated = OK to publish in a public JD. "
                "Hidden = internal-only (commute, culture signals, internal prefs). "
                "Operators: eq,neq,lt,lte,gt,gte,in,not_in,contains,between."
            ),
        ),
        LLMMessage(role="user", content=brief_text),
    ]
    result = await provider.complete(messages, response_schema={"stated": [], "hidden": []})
    return _normalize_filter_payload(result)


def _normalize_filter_payload(result: LLMStructuredResult) -> dict[str, list[dict[str, Any]]]:
    data = result.data or {}
    if data.get("stub"):
        # Heuristic stub extraction for offline/dev
        return {"stated": [], "hidden": []}
    stated_raw = data.get("stated") or data.get("stated_filters") or []
    hidden_raw = data.get("hidden") or data.get("hidden_filters") or []
    stated: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    for raw, bucket in ((stated_raw, stated), (hidden_raw, hidden)):
        if not isinstance(raw, list):
            continue
        for item in raw:
            try:
                bucket.append(RulePredicate.model_validate(item).model_dump())
            except Exception:  # noqa: BLE001 — skip malformed LLM rows
                continue
    return {"stated": stated, "hidden": hidden}


async def generate_job_description(
    *,
    title: str,
    brief_text: str,
    location: str | None,
    employment_type: str | None,
    stated_filters: list[dict[str, Any]],
    hidden_filters: list[dict[str, Any]],
) -> tuple[JobDescription, LLMStructuredResult]:
    """Generate structured JD from brief + stated filters only."""
    provider = get_llm_provider()
    # Intentionally omit hidden_filters from the prompt payload.
    user_payload = {
        "title": title,
        "brief_text": brief_text,
        "location": location,
        "employment_type": employment_type,
        "stated_filters": stated_filters,
        "output_schema": JD_SCHEMA_HINT,
        "rules": [
            "Do not invent discriminatory criteria.",
            "Only use stated_filters for public requirements.",
            "Never mention internal or hidden criteria.",
        ],
    }
    messages = [
        LLMMessage(
            role="system",
            content=(
                "You write external-facing job descriptions as JSON matching the schema. "
                "Never include internal/hidden hiring criteria."
            ),
        ),
        LLMMessage(role="user", content=json.dumps(user_payload)),
    ]
    result = await provider.complete(messages, response_schema=JD_SCHEMA_HINT)

    if result.data.get("stub"):
        jd = build_stub_jd(
            title=title,
            brief_text=brief_text,
            location=location,
            employment_type=employment_type,
            stated_filters=stated_filters,
        )
    else:
        payload = dict(result.data)
        payload.setdefault("title", title)
        payload.setdefault("location", location)
        payload.setdefault("employment_type", employment_type)
        payload.setdefault("stated_requirements", stated_filters)
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        meta = {**meta, "generated_by": result.provider, "model": result.model}
        payload["metadata"] = meta
        jd = JobDescription.model_validate(payload)

    assert_no_hidden_leak(jd.model_dump(), hidden_filters)
    return jd, result


_HIDDEN_HINTS = re.compile(
    r"\b(commute|culture.?fit|internal.?only|must live within|max distance|visa.?not|"
    r"no relocation|personality|age|zip.?code)\b",
    re.I,
)


def split_brief_heuristically(brief_text: str) -> dict[str, list[dict[str, Any]]]:
    """Lightweight non-LLM splitter for tests / offline extract_filters fallback."""
    stated: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    for line in brief_text.splitlines():
        text = line.strip(" -•\t")
        if len(text) < 8:
            continue
        if _HIDDEN_HINTS.search(text):
            hidden.append(
                RulePredicate(
                    field="internal_signal",
                    operator="contains",
                    value=text[:120],
                    description=text[:200],
                ).model_dump()
            )
        elif re.search(r"\b(years?|experience|degree|remote|hybrid|python|sql)\b", text, re.I):
            stated.append(
                RulePredicate(
                    field="requirement",
                    operator="contains",
                    value=text[:120],
                    description=None,
                ).model_dump()
            )
    return {"stated": stated, "hidden": hidden}
