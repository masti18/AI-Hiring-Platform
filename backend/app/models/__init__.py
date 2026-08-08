"""SQLAlchemy ORM models.

Schema rules (enforced from Milestone 1 onward):
- Every domain table includes company_id (multi-tenant ready).
- AI outputs are stored as structured JSON columns, never prose-only.
- Gate decisions are always persisted to the audit table.
"""

from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.role_requirement import RoleRequirement
from app.models.screening_call import ScreeningCall
from app.models.sourcing_run import SourcingRun

__all__ = [
    "AuditLog",
    "Candidate",
    "Company",
    "RoleRequirement",
    "ScreeningCall",
    "SourcingRun",
]
