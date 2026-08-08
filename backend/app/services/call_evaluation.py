"""Deterministic AI screening-call evaluation.

Produces a structured `CallEvaluation` from a transcript. This is the offline,
deterministic baseline; the screening service can optionally enrich/override it
with an LLM when one is configured. Kept pure (no I/O) for easy testing.
"""

from __future__ import annotations

import re

from app.schemas.screening import (
    CallDimension,
    CallEvaluation,
    Recommendation,
    TranscriptTurn,
)

DEFAULT_QUESTIONS = [
    "Can you walk me through your most relevant experience for this role?",
    "Describe a challenging problem you solved and your approach.",
    "Why are you interested in this position?",
]

ADVANCE_THRESHOLD = 0.6
HOLD_THRESHOLD = 0.4
_TARGET_WORDS = 20.0


def build_transcript(questions: list[str], answers: list[str]) -> list[TranscriptTurn]:
    """Interleave interviewer questions and candidate answers into a transcript."""
    turns: list[TranscriptTurn] = []
    for idx, question in enumerate(questions):
        turns.append(TranscriptTurn(speaker="interviewer", text=question))
        answer = answers[idx] if idx < len(answers) else ""
        turns.append(TranscriptTurn(speaker="candidate", text=answer))
    return turns


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if len(tok) >= 3}


def _recommendation(overall: float) -> Recommendation:
    if overall >= ADVANCE_THRESHOLD:
        return "advance"
    if overall >= HOLD_THRESHOLD:
        return "hold"
    return "reject"


def evaluate_transcript(
    transcript: list[TranscriptTurn],
    *,
    signal_tokens: set[str] | None = None,
) -> CallEvaluation:
    """Score a transcript on responsiveness, communication, and role alignment."""
    questions = [t for t in transcript if t.speaker == "interviewer"]
    answers = [t for t in transcript if t.speaker == "candidate"]
    total_questions = len(questions) or 1

    answered = [a for a in answers if a.text.strip()]
    responsiveness = len(answered) / total_questions

    if answered:
        avg_words = sum(len(a.text.split()) for a in answered) / len(answered)
        communication = min(1.0, avg_words / _TARGET_WORDS)
    else:
        communication = 0.0

    combined = _tokenize(" ".join(a.text for a in answered))
    if signal_tokens:
        matched = signal_tokens & combined
        role_alignment = len(matched) / len(signal_tokens)
    else:
        role_alignment = 1.0

    dimensions = [
        CallDimension(
            name="responsiveness",
            score=round(responsiveness, 4),
            notes=f"{len(answered)}/{total_questions} questions answered",
        ),
        CallDimension(
            name="communication",
            score=round(communication, 4),
            notes="based on average answer depth",
        ),
        CallDimension(
            name="role_alignment",
            score=round(role_alignment, 4),
            notes="overlap between answers and role signal terms",
        ),
    ]

    overall = round(sum(d.score for d in dimensions) / len(dimensions), 4)
    recommendation = _recommendation(overall)

    strengths = [d.name for d in dimensions if d.score >= ADVANCE_THRESHOLD]
    concerns = [d.name for d in dimensions if d.score < HOLD_THRESHOLD]
    reasoning = (
        f"Overall {overall:.2f} → {recommendation}. "
        f"Strengths: {', '.join(strengths) or 'none'}. "
        f"Concerns: {', '.join(concerns) or 'none'}."
    )

    return CallEvaluation(
        overall_score=overall,
        recommendation=recommendation,
        dimensions=dimensions,
        strengths=strengths,
        concerns=concerns,
        reasoning=reasoning,
    )
