"""Deterministic screening-call evaluation logic."""

from app.services.call_evaluation import (
    DEFAULT_QUESTIONS,
    build_transcript,
    evaluate_transcript,
)

SIGNAL = {"backend", "engineer", "years", "experience"}
STRONG_ANSWERS = [
    (
        "As a backend engineer I bring eight years of hands-on experience designing "
        "reliable payment platforms, scalable APIs, and strong on-call ownership across "
        "several high-growth engineering teams."
    ),
    (
        "I once cut backend latency in half over three years of experience by redesigning "
        "our data access layer, adding caching, and carefully load-testing every change we "
        "shipped to production."
    ),
    (
        "I am excited about this backend engineer role because it matches my years of "
        "experience building resilient distributed systems and mentoring other engineers on "
        "reliability best practices."
    ),
]


def test_build_transcript_interleaves() -> None:
    transcript = build_transcript(["Q1", "Q2"], ["A1"])
    assert [t.speaker for t in transcript] == [
        "interviewer",
        "candidate",
        "interviewer",
        "candidate",
    ]
    assert transcript[1].text == "A1"
    assert transcript[3].text == ""  # missing answer -> empty


def test_strong_candidate_advances() -> None:
    transcript = build_transcript(DEFAULT_QUESTIONS, STRONG_ANSWERS)
    evaluation = evaluate_transcript(transcript, signal_tokens=SIGNAL)
    assert evaluation.recommendation == "advance"
    assert evaluation.overall_score >= 0.6
    assert "responsiveness" in evaluation.strengths


def test_empty_answers_reject() -> None:
    transcript = build_transcript(DEFAULT_QUESTIONS, [])
    evaluation = evaluate_transcript(transcript, signal_tokens=SIGNAL)
    assert evaluation.recommendation == "reject"
    assert evaluation.overall_score < 0.4
    assert "responsiveness" in evaluation.concerns


def test_no_signal_tokens_defaults_alignment_high() -> None:
    transcript = build_transcript(["Tell me about yourself"], ["I build backend systems well."])
    evaluation = evaluate_transcript(transcript, signal_tokens=set())
    alignment = next(d for d in evaluation.dimensions if d.name == "role_alignment")
    assert alignment.score == 1.0
