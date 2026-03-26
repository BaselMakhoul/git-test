from datetime import datetime, timedelta, timezone

import pytest

from thesis_prototype.models import (
    AIArtifactType,
    AIExplanationArtifact,
    ConflictIssue,
    IssueCategory,
    OntologyChange,
    OperationType,
    ReviewDecision,
    ReviewerDecisionType,
    RuleType,
    SeverityLevel,
    ValidationResult,
    ValidationStatus,
    WorkflowState,
)
from thesis_prototype.registry import InMemoryIssueRegistry


def _make_change(change_id: str = "chg-1") -> OntologyChange:
    return OntologyChange(
        change_id=change_id,
        contributor_id="contrib-1",
        timestamp=datetime.now(timezone.utc),
        target_ontology_fragment="Class:Person",
        affected_entity="Person",
        operation_type=OperationType.UPDATE,
        proposed_values={"label": "Human"},
    )


def _make_issue(change_id: str, issue_id: str = "iss-1") -> ConflictIssue:
    return ConflictIssue(
        issue_id=issue_id,
        originating_change_id=change_id,
        issue_category=IssueCategory.CONFLICT,
        severity=SeverityLevel.HIGH,
        evidence={"match": "chg-0"},
        current_workflow_state=WorkflowState.OPEN,
    )


def test_model_creation_and_enums() -> None:
    change = _make_change()
    assert change.operation_type is OperationType.UPDATE

    validation = ValidationResult(
        validation_result_id="vr-1",
        change_id=change.change_id,
        rule_id="R-1",
        rule_type=RuleType.STRUCTURAL,
        status=ValidationStatus.FAIL,
        target_node="Person",
        affected_property_path="rdfs:label",
        machine_readable_message="DUPLICATE",
        user_readable_message="Duplicate label",
    )
    assert validation.status is ValidationStatus.FAIL

    decision = ReviewDecision(
        decision_id="dec-1",
        issue_id="iss-1",
        reviewer_id="rev-1",
        decision_type=ReviewerDecisionType.APPROVE,
        rationale="Looks good",
    )
    assert decision.decision_type is ReviewerDecisionType.APPROVE


def test_field_validation() -> None:
    with pytest.raises(ValueError):
        OntologyChange(
            change_id="",
            contributor_id="x",
            timestamp=datetime.now(timezone.utc),
            target_ontology_fragment="frag",
            affected_entity="entity",
            operation_type=OperationType.ADD,
            proposed_values={},
        )

    with pytest.raises(ValueError):
        AIExplanationArtifact(
            explanation_id="ai-1",
            explanation_type=AIArtifactType.EXPLANATION,
            generated_text="text",
        )

    with pytest.raises(ValueError):
        OntologyChange(
            change_id="chg-naive",
            contributor_id="x",
            timestamp=datetime.utcnow(),
            target_ontology_fragment="frag",
            affected_entity="entity",
            operation_type=OperationType.ADD,
            proposed_values={},
        )


def test_registry_create_read_update_and_traceability() -> None:
    registry = InMemoryIssueRegistry()
    change = _make_change()
    registry.create_change(change)

    issue = _make_issue(change.change_id)
    registry.create_issue(issue)

    result = ValidationResult(
        validation_result_id="vr-1",
        change_id=change.change_id,
        rule_id="R-1",
        rule_type=RuleType.SCHEMA,
        status=ValidationStatus.PASS,
        target_node="Person",
        affected_property_path="rdfs:comment",
        machine_readable_message="OK",
        user_readable_message="Valid",
    )
    registry.create_validation_result(result)
    registry.link_validation_to_issue(issue.issue_id, result.validation_result_id)

    artifact = AIExplanationArtifact(
        explanation_id="ai-1",
        explanation_type=AIArtifactType.SUGGESTION,
        related_issue_id=issue.issue_id,
        generated_text="Consider alternative wording",
    )
    registry.record_ai_explanation_artifact(artifact)

    decision = ReviewDecision(
        decision_id="dec-1",
        issue_id=issue.issue_id,
        reviewer_id="reviewer-1",
        decision_type=ReviewerDecisionType.REQUEST_REVISION,
        rationale="Need more evidence",
    )
    registry.record_review_decision(decision)

    registry.update_workflow_state(issue.issue_id, WorkflowState.IN_REVIEW)
    registry.update_workflow_state(issue.issue_id, WorkflowState.RESOLVED)

    fetched_issue = registry.get_issue(issue.issue_id)
    assert fetched_issue.validation_result_ids == ["vr-1"]
    assert fetched_issue.ai_explanation_artifact_ids == ["ai-1"]
    assert fetched_issue.reviewer_action is ReviewerDecisionType.REQUEST_REVISION

    assert registry.get_issues_for_change(change.change_id)[0].issue_id == issue.issue_id
    assert registry.get_validation_results_for_change(change.change_id)[0].validation_result_id == "vr-1"


def test_issue_history_ordering() -> None:
    registry = InMemoryIssueRegistry()
    change = _make_change("chg-2")
    registry.create_change(change)

    issue = _make_issue(change.change_id, "iss-2")
    issue.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    issue.updated_at = issue.created_at
    registry.create_issue(issue)

    t1 = datetime.now(timezone.utc) - timedelta(minutes=1)
    t2 = datetime.now(timezone.utc)

    registry.update_workflow_state(issue.issue_id, WorkflowState.IN_REVIEW, changed_at=t2)
    registry.update_workflow_state(issue.issue_id, WorkflowState.RESOLVED, changed_at=t1)

    history = registry.get_issue_history(issue.issue_id)
    assert [event.timestamp for event in history] == sorted(event.timestamp for event in history)


def test_invalid_state_transition_is_rejected() -> None:
    registry = InMemoryIssueRegistry()
    change = _make_change("chg-3")
    registry.create_change(change)
    issue = _make_issue(change.change_id, "iss-3")
    registry.create_issue(issue)

    with pytest.raises(ValueError):
        registry.update_workflow_state(issue.issue_id, WorkflowState.RESOLVED)


def test_ids_are_immutable_after_creation() -> None:
    issue = _make_issue("chg-immutable", "iss-immutable")
    with pytest.raises(AttributeError):
        issue.issue_id = "iss-new"
