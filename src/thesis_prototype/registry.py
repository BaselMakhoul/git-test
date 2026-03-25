from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from .models import (
    AIExplanationArtifact,
    ConflictIssue,
    OntologyChange,
    ReviewDecision,
    ValidationResult,
    WorkflowState,
)

_ALLOWED_STATE_TRANSITIONS = {
    WorkflowState.OPEN: {WorkflowState.IN_REVIEW, WorkflowState.CLOSED},
    WorkflowState.IN_REVIEW: {WorkflowState.RESOLVED, WorkflowState.CLOSED},
    WorkflowState.RESOLVED: {WorkflowState.CLOSED},
    WorkflowState.CLOSED: set(),
}


@dataclass(frozen=True)
class IssueHistoryEvent:
    issue_id: str
    event_type: str
    timestamp: datetime
    detail: str


class InMemoryIssueRegistry:
    """Step-1 persistence registry for ontology changes and issue traceability."""

    def __init__(self) -> None:
        self._changes: Dict[str, OntologyChange] = {}
        self._issues: Dict[str, ConflictIssue] = {}
        self._validation_results: Dict[str, ValidationResult] = {}
        self._review_decisions: Dict[str, ReviewDecision] = {}
        self._ai_artifacts: Dict[str, AIExplanationArtifact] = {}
        self._issue_history: List[IssueHistoryEvent] = []

    def create_change(self, change: OntologyChange) -> None:
        self._ensure_absent(change.change_id, self._changes, "change")
        self._changes[change.change_id] = change

    def create_issue(self, issue: ConflictIssue) -> None:
        self._ensure_present(issue.originating_change_id, self._changes, "change")
        self._ensure_absent(issue.issue_id, self._issues, "issue")
        self._issues[issue.issue_id] = issue
        self._record_history(issue.issue_id, "issue_created", issue.created_at, "Issue created")

    def create_validation_result(self, result: ValidationResult) -> None:
        self._ensure_present(result.change_id, self._changes, "change")
        self._ensure_absent(result.validation_result_id, self._validation_results, "validation result")
        self._validation_results[result.validation_result_id] = result

    def record_review_decision(self, decision: ReviewDecision) -> None:
        self._ensure_present(decision.issue_id, self._issues, "issue")
        self._ensure_absent(decision.decision_id, self._review_decisions, "decision")
        self._review_decisions[decision.decision_id] = decision
        issue = self._issues[decision.issue_id]
        issue.reviewer_action = decision.decision_type
        issue.assigned_reviewer = decision.reviewer_id
        issue.updated_at = decision.decided_at
        self._record_history(decision.issue_id, "decision_recorded", decision.decided_at, decision.decision_type.value)

    def record_ai_explanation_artifact(self, artifact: AIExplanationArtifact) -> None:
        self._ensure_absent(artifact.explanation_id, self._ai_artifacts, "AI artifact")
        if artifact.related_issue_id:
            self._ensure_present(artifact.related_issue_id, self._issues, "issue")
            self._issues[artifact.related_issue_id].ai_explanation_artifact_ids.append(artifact.explanation_id)
        if artifact.related_validation_result_id:
            self._ensure_present(
                artifact.related_validation_result_id,
                self._validation_results,
                "validation result",
            )
        self._ai_artifacts[artifact.explanation_id] = artifact

    def link_validation_to_issue(self, issue_id: str, validation_result_id: str) -> None:
        self._ensure_present(issue_id, self._issues, "issue")
        self._ensure_present(validation_result_id, self._validation_results, "validation result")
        issue = self._issues[issue_id]
        if validation_result_id not in issue.validation_result_ids:
            issue.validation_result_ids.append(validation_result_id)
            issue.updated_at = datetime.now(timezone.utc)

    def get_change(self, change_id: str) -> OntologyChange:
        return self._get(change_id, self._changes, "change")

    def get_issue(self, issue_id: str) -> ConflictIssue:
        return self._get(issue_id, self._issues, "issue")

    def get_validation_result(self, validation_result_id: str) -> ValidationResult:
        return self._get(validation_result_id, self._validation_results, "validation result")

    def get_review_decision(self, decision_id: str) -> ReviewDecision:
        return self._get(decision_id, self._review_decisions, "decision")

    def get_ai_explanation_artifact(self, explanation_id: str) -> AIExplanationArtifact:
        return self._get(explanation_id, self._ai_artifacts, "AI artifact")

    def get_issues_for_change(self, change_id: str) -> List[ConflictIssue]:
        self._ensure_present(change_id, self._changes, "change")
        return [issue for issue in self._issues.values() if issue.originating_change_id == change_id]

    def list_changes(self) -> List[OntologyChange]:
        return list(self._changes.values())

    def list_issues(self) -> List[ConflictIssue]:
        return list(self._issues.values())

    def get_validation_results_for_change(self, change_id: str) -> List[ValidationResult]:
        self._ensure_present(change_id, self._changes, "change")
        return [result for result in self._validation_results.values() if result.change_id == change_id]

    def get_issue_history(self, issue_id: str) -> List[IssueHistoryEvent]:
        self._ensure_present(issue_id, self._issues, "issue")
        return sorted((event for event in self._issue_history if event.issue_id == issue_id), key=lambda e: e.timestamp)

    def update_workflow_state(self, issue_id: str, new_state: WorkflowState, changed_at: datetime | None = None) -> None:
        issue = self._get(issue_id, self._issues, "issue")
        allowed_next_states = _ALLOWED_STATE_TRANSITIONS[issue.current_workflow_state]
        if new_state not in allowed_next_states:
            raise ValueError(
                f"Invalid transition from {issue.current_workflow_state.value} to {new_state.value}"
            )
        effective_time = self._as_utc(changed_at) if changed_at else datetime.now(timezone.utc)
        old_state = issue.current_workflow_state
        issue.current_workflow_state = new_state
        issue.updated_at = effective_time
        self._record_history(
            issue_id,
            "workflow_state_changed",
            effective_time,
            f"{old_state.value}->{new_state.value}",
        )

    def _record_history(self, issue_id: str, event_type: str, timestamp: datetime, detail: str) -> None:
        self._issue_history.append(
            IssueHistoryEvent(
                issue_id=issue_id,
                event_type=event_type,
                timestamp=self._as_utc(timestamp),
                detail=detail,
            )
        )

    @staticmethod
    def _ensure_absent(record_id: str, table: Dict[str, object], record_type: str) -> None:
        if record_id in table:
            raise ValueError(f"{record_type} with id '{record_id}' already exists")

    @staticmethod
    def _ensure_present(record_id: str, table: Dict[str, object], record_type: str) -> None:
        if record_id not in table:
            raise KeyError(f"{record_type} with id '{record_id}' was not found")

    @staticmethod
    def _get(record_id: str, table: Dict[str, object], record_type: str):
        if record_id not in table:
            raise KeyError(f"{record_type} with id '{record_id}' was not found")
        return table[record_id]

    @staticmethod
    def _as_utc(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return timestamp.astimezone(timezone.utc)
