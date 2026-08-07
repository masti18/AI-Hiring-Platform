"""LangGraph agent pipeline package.

Architecture:
- Stateful graph (not a linear chain): nodes may retry, branch, and escalate.
- Two review checkpoints (post-sourcing, post-AI-call) ALWAYS run policy evaluation
  and ALWAYS log decision + reasoning to the audit table.
- Whether a gate blocks for a human click is controlled by company config
  (auto_approve_gate1 / auto_approve_gate2), never hardcoded.
"""
