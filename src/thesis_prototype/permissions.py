from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class Role(str, Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    CONTRIBUTOR = "contributor"


ROLE_PERMISSIONS: Dict[Role, Set[str]] = {
    Role.ADMIN: {
        "submit_change",
        "view_own_requests",
        "view_assigned_reviews",
        "approve_case",
        "reject_case",
        "request_revision",
        "manage_users",
        "assign_roles",
        "view_all_cases",
        "recall_request",
        "resubmit_change",
    },
    Role.REVIEWER: {
        "view_assigned_reviews",
        "approve_case",
        "reject_case",
        "request_revision",
    },
    Role.CONTRIBUTOR: {
        "submit_change",
        "view_own_requests",
        "recall_request",
        "resubmit_change",
    },
}


def has_permission(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS[role]
