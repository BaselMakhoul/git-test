from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .auth_service import AuthService, User
from .conflict_detection import ConflictDetectionService
from .governance_service import GovernanceReviewService
from .models import OntologyChange, OperationType
from .permissions import Role, has_permission
from .registry import InMemoryIssueRegistry
from .validation_service import ValidationConfig, ValidationService


class DemoBackend:
    """Thin orchestration layer for demo API/UI interactions."""

    def __init__(self) -> None:
        self.registry = InMemoryIssueRegistry()
        self.conflicts = ConflictDetectionService(self.registry)
        self.validation = ValidationService(
            self.registry,
            ValidationConfig(
                expected_domain_by_property={"hasSymptom": "Disease"},
                expected_range_by_property={"hasSymptom": "Symptom"},
            ),
        )
        self.governance = GovernanceReviewService(self.registry)
        self.auth = AuthService()
        self._seed_demo_users()

    def _seed_demo_users(self) -> None:
        if self.auth.list_users():
            return
        self.auth.create_user("admin", "admin123", "Admin User", Role.ADMIN)
        self.auth.create_user("reviewer", "review123", "Reviewer User", Role.REVIEWER)
        self.auth.create_user("contributor", "contrib123", "Contributor User", Role.CONTRIBUTOR)

    # -------- Auth / user management --------
    def login(self, username: str, password: str) -> Dict[str, Any]:
        user = self.auth.authenticate(username, password)
        return to_jsonable(user)

    def list_users(self, actor_user_id: str) -> List[Dict[str, Any]]:
        self._require_permission(actor_user_id, "manage_users")
        return [to_jsonable(u) for u in self.auth.list_users()]

    def create_user(
        self,
        actor_user_id: str,
        username: str,
        password: str,
        display_name: str,
        role: str,
        active: bool = True,
    ) -> Dict[str, Any]:
        self._require_permission(actor_user_id, "manage_users")
        user = self.auth.create_user(username, password, display_name, Role(role), active=active)
        return to_jsonable(user)

    def set_user_active(self, actor_user_id: str, user_id: str, active: bool) -> Dict[str, Any]:
        self._require_permission(actor_user_id, "manage_users")
        return to_jsonable(self.auth.set_user_active(user_id, active))

    def assign_user_role(self, actor_user_id: str, user_id: str, role: str) -> Dict[str, Any]:
        self._require_permission(actor_user_id, "assign_roles")
        return to_jsonable(self.auth.assign_role(user_id, Role(role)))

    # -------- Core data actions with RBAC --------
    def create_change(
        self,
        contributor_id: str,
        affected_entity: str,
        operation_type: str,
        label: Optional[str],
        description: Optional[str],
        optional_note: Optional[str] = None,
        scenario_id: Optional[str] = None,
        revision_reference: Optional[str] = None,
        proposed_values_extra: Optional[Dict[str, Any]] = None,
        actor_user_id: Optional[str] = None,
    ) -> OntologyChange:
        if actor_user_id:
            self._require_permission(actor_user_id, "submit_change")
            actor = self.auth.get_user_by_id(actor_user_id)
            if actor.role is Role.CONTRIBUTOR:
                contributor_id = actor.user_id

        op = OperationType(operation_type)
        proposed_values: Dict[str, Any] = {}
        if label is not None:
            proposed_values["label"] = label
        if description is not None:
            proposed_values["description"] = description
        if proposed_values_extra:
            proposed_values.update(proposed_values_extra)

        change = OntologyChange(
            change_id=f"chg-{uuid4().hex[:10]}",
            contributor_id=contributor_id,
            timestamp=datetime.now(timezone.utc),
            target_ontology_fragment=f"Class:{affected_entity}",
            affected_entity=affected_entity,
            operation_type=op,
            proposed_values=proposed_values,
            optional_note=optional_note,
            scenario_id=scenario_id,
            revision_reference=revision_reference,
        )
        self.registry.create_change(change)
        return change

    def list_changes(self, actor_user_id: Optional[str] = None) -> List[OntologyChange]:
        changes = sorted(self.registry.list_changes(), key=lambda c: (c.timestamp, c.change_id))
        if not actor_user_id:
            return changes
        user = self.auth.get_user_by_id(actor_user_id)
        if user.role is Role.ADMIN:
            return changes
        if user.role is Role.CONTRIBUTOR:
            return [c for c in changes if c.contributor_id == user.user_id]
        if user.role is Role.REVIEWER:
            reviewer_issue_change_ids = {
                issue.originating_change_id
                for issue in self.registry.list_issues()
                if issue.assigned_reviewer == user.user_id
            }
            return [c for c in changes if c.change_id in reviewer_issue_change_ids]
        return []

    def get_change(self, change_id: str) -> OntologyChange:
        return self.registry.get_change(change_id)

    def detect_conflicts(self, change_id: str, mode: str = "all") -> List[Dict[str, Any]]:
        change = self.registry.get_change(change_id)
        if mode == "direct":
            issues = self.conflicts.detect_direct_duplicates(change)
        elif mode == "near":
            issues = self.conflicts.detect_near_duplicates(change)
        elif mode == "overlap":
            issues = self.conflicts.detect_overlap_conflicts(change)
        elif mode == "all":
            issues = self.conflicts.detect_all(change)
        else:
            raise ValueError("mode must be one of: direct, near, overlap, all")
        return [to_jsonable(issue) for issue in issues]

    def validate_change(self, change_id: str) -> List[Dict[str, Any]]:
        change = self.registry.get_change(change_id)
        results = self.validation.validate_change(change)
        return [to_jsonable(result) for result in results]

    def get_issues_for_change(self, change_id: str) -> List[Dict[str, Any]]:
        return [to_jsonable(issue) for issue in self.registry.get_issues_for_change(change_id)]

    def get_validation_results_for_change(self, change_id: str) -> List[Dict[str, Any]]:
        return [to_jsonable(result) for result in self.registry.get_validation_results_for_change(change_id)]

    def get_registry_summary(self, actor_user_id: Optional[str] = None) -> Dict[str, Any]:
        changes = self.list_changes(actor_user_id=actor_user_id)
        summary = {
            "changes": [to_jsonable(change) for change in changes],
            "issues_by_change": {},
            "validation_by_change": {},
            "history_by_issue": {},
        }
        for change in changes:
            issues = self.registry.get_issues_for_change(change.change_id)
            vals = self.registry.get_validation_results_for_change(change.change_id)
            summary["issues_by_change"][change.change_id] = [to_jsonable(issue) for issue in issues]
            summary["validation_by_change"][change.change_id] = [to_jsonable(v) for v in vals]
            for issue in issues:
                summary["history_by_issue"][issue.issue_id] = [
                    to_jsonable(event) for event in self.registry.get_issue_history(issue.issue_id)
                ]
        return summary

    # Governance hooks (T36)
    def open_review_for_issue(self, issue_id: str, actor_id: str = "system") -> Dict[str, Any]:
        case = self.governance.open_review_for_issue(issue_id=issue_id, actor_id=actor_id)
        return to_jsonable(case)

    def open_review_for_failed_validation(self, validation_result_id: str, actor_id: str = "system") -> Dict[str, Any]:
        case = self.governance.open_review_for_failed_validation(validation_result_id=validation_result_id, actor_id=actor_id)
        return to_jsonable(case)

    def assign_reviewer(self, review_case_id: str, reviewer_id: str, actor_id: str = "system") -> Dict[str, Any]:
        case = self.governance.assign_reviewer(review_case_id=review_case_id, reviewer_id=reviewer_id, actor_id=actor_id)
        return to_jsonable(case)

    def approve_review(self, review_case_id: str, reviewer_id: str, rationale: str, actor_user_id: Optional[str] = None) -> Dict[str, Any]:
        if actor_user_id:
            self._require_permission(actor_user_id, "approve_case")
        return to_jsonable(self.governance.approve(review_case_id, reviewer_id, rationale))

    def reject_review(self, review_case_id: str, reviewer_id: str, rationale: str, actor_user_id: Optional[str] = None) -> Dict[str, Any]:
        if actor_user_id:
            self._require_permission(actor_user_id, "reject_case")
        return to_jsonable(self.governance.reject(review_case_id, reviewer_id, rationale))

    def request_review_revision(
        self,
        review_case_id: str,
        reviewer_id: str,
        rationale: str,
        actor_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if actor_user_id:
            self._require_permission(actor_user_id, "request_revision")
        return to_jsonable(self.governance.request_revision(review_case_id, reviewer_id, rationale))

    def resubmit_review_case(
        self,
        review_case_id: str,
        revised_change_id: str,
        actor_id: str,
        actor_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if actor_user_id:
            self._require_permission(actor_user_id, "resubmit_change")
        case = self.governance.resubmit_with_correction(review_case_id, revised_change_id, actor_id)
        return to_jsonable(case)

    def recall_change(self, change_id: str, actor_user_id: str) -> Dict[str, Any]:
        self._require_permission(actor_user_id, "recall_request")
        user = self.auth.get_user_by_id(actor_user_id)
        change = self.registry.get_change(change_id)
        if user.role is Role.CONTRIBUTOR and change.contributor_id != user.user_id:
            raise PermissionError("contributors can only recall their own changes")
        if self.registry.get_issues_for_change(change_id):
            raise ValueError("cannot recall change once issues exist")
        return {"change_id": change_id, "status": "recalled", "recalled_by": actor_user_id}

    def get_review_history(self, review_case_id: str) -> List[Dict[str, Any]]:
        return [to_jsonable(e) for e in self.governance.get_review_history(review_case_id)]

    def get_review_case(self, review_case_id: str) -> Dict[str, Any]:
        return to_jsonable(self.governance.get_review_case(review_case_id))

    def list_review_cases(self, actor_user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        cases = self.governance.list_review_cases()
        if actor_user_id:
            user = self.auth.get_user_by_id(actor_user_id)
            if user.role is Role.REVIEWER:
                cases = [c for c in cases if c.assigned_reviewer == user.user_id]
            elif user.role is Role.CONTRIBUTOR:
                cases = [c for c in cases if c.originating_change_id in {ch.change_id for ch in self.list_changes(actor_user_id)}]
        return [to_jsonable(case) for case in cases]

    def is_approval_blocked(self, review_case_id: str) -> bool:
        return self.governance.is_approval_blocked(review_case_id)

    def return_case_to_review(self, review_case_id: str, actor_id: str = "system") -> Dict[str, Any]:
        return to_jsonable(self.governance.return_to_review(review_case_id, actor_id=actor_id))

    # Roles and permissions overview
    def permissions_overview(self) -> Dict[str, List[str]]:
        from .permissions import ROLE_PERMISSIONS

        return {role.value: sorted(list(perms)) for role, perms in ROLE_PERMISSIONS.items()}

    def _require_permission(self, actor_user_id: str, permission: str) -> User:
        actor = self.auth.get_user_by_id(actor_user_id)
        if not has_permission(actor.role, permission):
            raise PermissionError(f"Role '{actor.role.value}' is not allowed to perform '{permission}'")
        return actor


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value
