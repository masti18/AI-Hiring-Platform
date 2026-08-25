"""SQLAlchemy ORM models.

Schema rules (enforced from Milestone 1 onward):
- Every domain table includes company_id (multi-tenant ready).
- AI outputs are stored as structured JSON columns, never prose-only.
- Gate decisions are always persisted to the audit table.
"""

from app.models.company import Company

__all__ = ["Company"]
