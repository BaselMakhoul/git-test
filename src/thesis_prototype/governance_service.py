from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from .models import (
    ConflictIssue,
    IssueCategory,
    ReviewDecision,
    ReviewerDecisionType,
    SeverityLevel,
    ValidationStatus,
    WorkflowState,
)
from .registry import InMemoryIssueRegistry


class ReviewWorkflowState(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    REVISION_REQUESTED = "revision_requested"
    RESUBMITTED = "resubmitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


_ALLOWED_TRANSITIONS = {
    ReviewWorkflowState.OPEN: {ReviewWorkflowState.UNDER_REVIEW},
    ReviewWorkflowState.UNDER_REVIEW: {
        ReviewWorkflowState.APPROVED,
        ReviewWorkflowState.REJECTED,
        ReviewWorkflowState.REVISION_REQUESTED,
    },
    ReviewWorkflowState.REVISION_REQUESTED: {ReviewWorkflowState.RESUBMITTED},
    ReviewWorkflowState.RESUBMITTED: {ReviewWorkflowState.UNDER_REVIEW, ReviewWorkflowState.APPROVED},
    ReviewWorkflowState.APPROVED: {ReviewWorkflowState.CLOSED},
    ReviewWorkflowState.REJECTED: {ReviewWorkflowState.CLOSED},
    ReviewWorkflowState.CLOSED: set(),
}


@dataclass(frozen=True)
class ReviewHistoryEvent:
    review_case_id: str
    event_type: str
    timestamp: datetime
    actor_id: str
    detail: str


@dataclass
class ReviewCase:
    review_case_id: str
    originating_change_id: str
    linked_issue_id: str
    source_validation_result_id: Optional[str] = None
    current_change_id: Optional[str] = None
    workflow_state: ReviewWorkflowState = ReviewWorkflowState.OPEN
    assigned_reviewer: Optional[str] = None
    final_decision: Optional[ReviewerDecisionType] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    linked_resubmissions: List[str] = field(default_factory=list)


class GovernanceReviewService:
    """Deterministic governance workflow orchestrator for flagged outputs."""

    def __init__(self, registry: InMemoryIssueRegistry) -> None:
        self.registry = registry
        self._review_cases: Dict[str, ReviewCase] = {}
        self._history: Dict[str, List[ReviewHistoryEvent]] = {}
        self._case_by_issue: Dict[str, str] = {}

    def open_review_for_issue(self, issue_id: str, actor_id: str = "system") -> ReviewCase:
        issue = self.registry.get_issue(issue_id)
        if issue_id in self._case_by_issue:
            return self._review_cases[self._case_by_issue[issue_id]]

        case = ReviewCase(
            review_case_id=f"rc-{uuid4().hex[:10]}",
            originating_change_id=issue.originating_change_id,
            current_change_id=issue.originating_change_id,
            linked_issue_id=issue_id,
        )
        self._store_case(case)
        self._record(case.review_case_id, "review_opened", actor_id, f"Opened review for issue {issue_id}")
        return case

    def open_review_for_failed_validation(self, validation_result_id: str, actor_id: str = "system") -> ReviewCase:
        result = self.registry.get_validation_result(validation_result_id)
        if result.status is not ValidationStatus.FAIL:
            raise ValueError("Only failed validation results can enter governance workflow")

        synthetic_issue_id = f"iss-gov-{validation_result_id.replace('val-', '')[:12]}"
        try:
            issue = self.registry.get_issue(synthetic_issue_id)
        except KeyError:
            issue = ConflictIssue(
                issue_id=synthetic_issue_id,
                originating_change_id=result.change_id,
                issue_category=IssueCategory.POLICY,
                severity=SeverityLevel.MEDIUM,
                evidence={
                    "source": "validation_result",
                    "validation_result_id": validation_result_id,
                    "machine_code": result.machine_readable_message,
                    "user_readable_description": result.user_readable_message,
                },
                current_workflow_state=WorkflowState.OPEN,
            )
            self.registry.create_issue(issue)

        case = self.open_review_for_issue(issue.issue_id, actor_id=actor_id)
        case.source_validation_result_id = validation_result_id
        case.updated_at = datetime.now(timezone.utc)
        self._record(
            case.review_case_id,
            "validation_linked",
            actor_id,
            f"Linked failed validation result {validation_result_id}",
        )
        return case

    def assign_reviewer(self, review_case_id: str, reviewer_id: str, actor_id: str = "system") -> ReviewCase:
        case = self.get_review_case(review_case_id)
        if case.workflow_state in {ReviewWorkflowState.APPROVED, ReviewWorkflowState.REJECTED, ReviewWorkflowState.CLOSED}:
            raise ValueError("Cannot assign reviewer to finalized review case")

        previous = case.assigned_reviewer
        case.assigned_reviewer = reviewer_id
        if case.workflow_state is ReviewWorkflowState.OPEN:
            self._transition(case, ReviewWorkflowState.UNDER_REVIEW)
        case.updated_at = datetime.now(timezone.utc)

        self._record(
            review_case_id,
            "reviewer_assigned",
            actor_id,
            f"Assigned reviewer {reviewer_id} (previous={previous})",
        )
        issue = self.registry.get_issue(case.linked_issue_id)
        issue.assigned_reviewer = reviewer_id
        issue.updated_at = case.updated_at
        return case

    def get_assigned_reviewer(self, review_case_id: str) -> Optional[str]:
        return self.get_review_case(review_case_id).assigned_reviewer

    def request_revision(self, review_case_id: str, reviewer_id: str, rationale: str) -> ReviewDecision:
        return self._record_decision(review_case_id, reviewer_id, ReviewerDecisionType.REQUEST_REVISION, rationale)

    def approve(self, review_case_id: str, reviewer_id: str, rationale: str) -> ReviewDecision:
        case = self.get_review_case(review_case_id)
        self._ensure_approvable(case)
        return self._record_decision(review_case_id, reviewer_id, ReviewerDecisionType.APPROVE, rationale)

    def reject(self, review_case_id: str, reviewer_id: str, rationale: str) -> ReviewDecision:
        return self._record_decision(review_case_id, reviewer_id, ReviewerDecisionType.REJECT, rationale)

    def close_review_case(self, review_case_id: str, actor_id: str = "system") -> ReviewCase:
        case = self.get_review_case(review_case_id)
        if case.workflow_state not in {ReviewWorkflowState.APPROVED, ReviewWorkflowState.REJECTED}:
            raise ValueError("Only approved/rejected cases can be closed")
        self._transition(case, ReviewWorkflowState.CLOSED)
        self._record(review_case_id, "case_closed", actor_id, f"Closed case in state {case.workflow_state.value}")

        issue = self.registry.get_issue(case.linked_issue_id)
        issue.current_workflow_state = WorkflowState.CLOSED
        issue.updated_at = datetime.now(timezone.utc)
        return case

    def resubmit_with_correction(
        self,
        review_case_id: str,
        revised_change_id: str,
        actor_id: str,
    ) -> ReviewCase:
        case = self.get_review_case(review_case_id)
        if case.workflow_state is not ReviewWorkflowState.REVISION_REQUESTED:
            raise ValueError("Resubmission allowed only from REVISION_REQUESTED state")

        self.registry.get_change(revised_change_id)
        case.linked_resubmissions.append(revised_change_id)
        case.current_change_id = revised_change_id
        self._transition(case, ReviewWorkflowState.RESUBMITTED)
        self._record(review_case_id, "resubmitted", actor_id, f"Linked revised change {revised_change_id}")

        issue = self.registry.get_issue(case.linked_issue_id)
        issue.reviewer_action = ReviewerDecisionType.REQUEST_REVISION
        issue.updated_at = datetime.now(timezone.utc)
        issue.evidence["resubmissions"] = list(case.linked_resubmissions)
        return case

    def return_to_review(self, review_case_id: str, actor_id: str = "system") -> ReviewCase:
        case = self.get_review_case(review_case_id)
        if case.workflow_state is not ReviewWorkflowState.RESUBMITTED:
            raise ValueError("Can only return RESUBMITTED case to UNDER_REVIEW")
        self._transition(case, ReviewWorkflowState.UNDER_REVIEW)
        self._record(review_case_id, "under_review", actor_id, "Returned resubmitted case to UNDER_REVIEW")
        return case

    def get_review_case(self, review_case_id: str) -> ReviewCase:
        if review_case_id not in self._review_cases:
            raise KeyError(f"review case with id '{review_case_id}' was not found")
        return self._review_cases[review_case_id]

    def get_review_history(self, review_case_id: str) -> List[ReviewHistoryEvent]:
        self.get_review_case(review_case_id)
        return sorted(self._history.get(review_case_id, []), key=lambda e: e.timestamp)

    def list_review_cases_for_change(self, change_id: str) -> List[ReviewCase]:
        return [case for case in self._review_cases.values() if case.originating_change_id == change_id]

    def list_review_cases(self) -> List[ReviewCase]:
        return list(self._review_cases.values())

    def is_approval_blocked(self, review_case_id: str) -> bool:
        case = self.get_review_case(review_case_id)
        try:
            self._ensure_approvable(case)
            return False
        except ValueError:
            return True

    def _record_decision(
        self,
        review_case_id: str,
        reviewer_id: str,
        decision_type: ReviewerDecisionType,
        rationale: str,
    ) -> ReviewDecision:
        case = self.get_review_case(review_case_id)
        if case.assigned_reviewer != reviewer_id:
            raise PermissionError("Only the assigned reviewer can make decisions")
        if case.workflow_state in {ReviewWorkflowState.APPROVED, ReviewWorkflowState.REJECTED, ReviewWorkflowState.CLOSED}:
            raise ValueError("No additional decisions allowed for finalized review case")
        if not rationale.strip():
            raise ValueError("rationale is required")

        if decision_type is ReviewerDecisionType.REQUEST_REVISION:
            self._transition(case, ReviewWorkflowState.REVISION_REQUESTED)
        elif decision_type is ReviewerDecisionType.APPROVE:
            if case.workflow_state not in {ReviewWorkflowState.UNDER_REVIEW, ReviewWorkflowState.RESUBMITTED}:
                raise ValueError("Approval allowed only from UNDER_REVIEW or RESUBMITTED")
            self._transition(case, ReviewWorkflowState.APPROVED)
        elif decision_type is ReviewerDecisionType.REJECT:
            if case.workflow_state not in {ReviewWorkflowState.UNDER_REVIEW, ReviewWorkflowState.RESUBMITTED}:
                raise ValueError("Rejection allowed only from UNDER_REVIEW or RESUBMITTED")
            self._transition(case, ReviewWorkflowState.REJECTED)

        decision = ReviewDecision(
            decision_id=f"dec-{uuid4().hex[:10]}",
            issue_id=case.linked_issue_id,
            reviewer_id=reviewer_id,
            decision_type=decision_type,
            rationale=rationale,
        )
        self.registry.record_review_decision(decision)

        case.final_decision = decision_type
        case.updated_at = decision.decided_at
        self._record(
            review_case_id,
            "decision_recorded",
            reviewer_id,
            f"{decision_type.value}: {rationale}",
        )

        issue = self.registry.get_issue(case.linked_issue_id)
        issue.reviewer_action = decision_type
        issue.final_outcome = decision_type.value
        issue.updated_at = decision.decided_at
        if decision_type is ReviewerDecisionType.REQUEST_REVISION:
            issue.current_workflow_state = WorkflowState.IN_REVIEW
        else:
            issue.current_workflow_state = WorkflowState.RESOLVED
        return decision

    def _ensure_approvable(self, case: ReviewCase) -> None:
        target_change_id = case.current_change_id or case.originating_change_id
        validation_results = self.registry.get_validation_results_for_change(target_change_id)
        if any(result.status is ValidationStatus.FAIL for result in validation_results):
            raise ValueError("Cannot approve while failing validation results remain for current change")

    def _store_case(self, case: ReviewCase) -> None:
        self._review_cases[case.review_case_id] = case
        self._case_by_issue[case.linked_issue_id] = case.review_case_id

    def _transition(self, case: ReviewCase, new_state: ReviewWorkflowState) -> None:
        allowed = _ALLOWED_TRANSITIONS[case.workflow_state]
        if new_state not in allowed:
            raise ValueError(f"Invalid transition from {case.workflow_state.value} to {new_state.value}")
        case.workflow_state = new_state
        case.updated_at = datetime.now(timezone.utc)

    def _record(self, review_case_id: str, event_type: str, actor_id: str, detail: str) -> None:
        event = ReviewHistoryEvent(
            review_case_id=review_case_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id=actor_id,
            detail=detail,
        )
        self._history.setdefault(review_case_id, []).append(event)
