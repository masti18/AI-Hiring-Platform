"""SQLAlchemy ORM models.

Schema rules:
- Every domain table includes company_id (multi-tenant ready).
- AI outputs are stored as structured JSON columns, never prose-only.
- Gate decisions are always persisted to audit_events.
"""

from app.models.audit import AuditEvent
from app.models.company import Company
from app.models.pipeline_run import PipelineRun
from app.models.role import Role
from app.models.user import User

__all__ = ["AuditEvent", "Company", "PipelineRun", "Role", "User"]
