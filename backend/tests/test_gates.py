"""Auto-gate policy branching tests."""

import pytest

from app.agents.gates import evaluate_gate_policy
from app.agents.state import HiringGraphState


@pytest.mark.asyncio
async def test_gate_auto_approves_when_flag_true() -> None:
    state: HiringGraphState = {"company_id": "c1", "run_id": "r1"}
    decision = await evaluate_gate_policy(
        gate="gate1_post_sourcing",
        state=state,
        auto_approve=True,
        policy_result={"passed": True, "checks": []},
    )
    assert decision["action"] == "auto_approve"
    assert "auto_approve enabled" in decision["reasoning"]


@pytest.mark.asyncio
async def test_gate_awaits_human_when_flag_false() -> None:
    state: HiringGraphState = {"company_id": "c1", "run_id": "r1"}
    decision = await evaluate_gate_policy(
        gate="gate2_post_ai_call",
        state=state,
        auto_approve=False,
        policy_result={"passed": True, "checks": []},
    )
    assert decision["action"] == "await_human"


@pytest.mark.asyncio
async def test_gate_rejects_on_policy_failure() -> None:
    state: HiringGraphState = {"company_id": "c1", "run_id": "r1"}
    decision = await evaluate_gate_policy(
        gate="gate1_post_sourcing",
        state=state,
        auto_approve=True,
        policy_result={"passed": False, "checks": [{"name": "min_candidates", "ok": False}]},
    )
    assert decision["action"] == "reject"
