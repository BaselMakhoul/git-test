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


@pytest.fixture
def linked_registry() -> dict:
    registry = InMemoryIssueRegistry()
    change = OntologyChange(
        change_id="chg-defense-001",
        contributor_id="contrib-defense",
        timestamp=datetime.now(timezone.utc),
        target_ontology_fragment="Class:Person",
        affected_entity="Person",
        operation_type=OperationType.UPDATE,
        proposed_values={"label": "Human"},
    )
    registry.create_change(change)

    issue = ConflictIssue(
        issue_id="iss-defense-001",
        originating_change_id=change.change_id,
        issue_category=IssueCategory.CONFLICT,
        severity=SeverityLevel.MEDIUM,
        evidence={"source": "defense-fixture"},
        current_workflow_state=WorkflowState.OPEN,
    )
    registry.create_issue(issue)

    validation = ValidationResult(
        validation_result_id="val-defense-001",
        change_id=change.change_id,
        rule_id="RULE-DEFENSE-001",
        rule_type=RuleType.STRUCTURAL,
        status=ValidationStatus.FAIL,
        target_node="Person",
        affected_property_path="rdfs:label",
        machine_readable_message="DUPLICATE",
        user_readable_message="Potential duplicate.",
    )
    registry.create_validation_result(validation)
    registry.link_validation_to_issue(issue.issue_id, validation.validation_result_id)

    decision = ReviewDecision(
        decision_id="dec-defense-001",
        issue_id=issue.issue_id,
        reviewer_id="reviewer-defense",
        decision_type=ReviewerDecisionType.REQUEST_REVISION,
        rationale="Need stronger evidence.",
    )
    registry.record_review_decision(decision)

    ai_artifact = AIExplanationArtifact(
        explanation_id="ai-defense-001",
        explanation_type=AIArtifactType.EXPLANATION,
        related_validation_result_id=validation.validation_result_id,
        generated_text="This looks similar to existing terminology.",
    )
    registry.record_ai_explanation_artifact(ai_artifact)

    return {
        "registry": registry,
        "change": change,
        "issue": issue,
        "validation": validation,
        "decision": decision,
        "ai_artifact": ai_artifact,
    }


# DM-01 Immutable identity

def test_dm01_immutable_identity_fields_are_stable() -> None:
    change = OntologyChange(
        change_id="chg-immutable",
        contributor_id="x",
        timestamp=datetime.now(timezone.utc),
        target_ontology_fragment="Class:X",
        affected_entity="X",
        operation_type=OperationType.ADD,
        proposed_values={"label": "X"},
    )
    with pytest.raises(Exception):
        change.change_id = "changed"  # frozen dataclass blocks mutation

    issue = ConflictIssue(
        issue_id="iss-immutable",
        originating_change_id="chg-immutable",
        issue_category=IssueCategory.CONFLICT,
        severity=SeverityLevel.HIGH,
        evidence={"note": "immutable"},
        current_workflow_state=WorkflowState.OPEN,
    )
    with pytest.raises(AttributeError):
        issue.issue_id = "other"


# DM-02 Required field enforcement

@pytest.mark.parametrize(
    "factory",
    [
        lambda: OntologyChange(
            change_id="",
            contributor_id="u",
            timestamp=datetime.now(timezone.utc),
            target_ontology_fragment="f",
            affected_entity="e",
            operation_type=OperationType.ADD,
            proposed_values={},
        ),
        lambda: ConflictIssue(
            issue_id="",
            originating_change_id="chg",
            issue_category=IssueCategory.CONFLICT,
            severity=SeverityLevel.MEDIUM,
            evidence={},
            current_workflow_state=WorkflowState.OPEN,
        ),
        lambda: ValidationResult(
            validation_result_id="",
            change_id="chg",
            rule_id="r",
            rule_type=RuleType.CUSTOM,
            status=ValidationStatus.PASS,
            target_node="n",
            affected_property_path="p",
            machine_readable_message="ok",
            user_readable_message="ok",
        ),
        lambda: ReviewDecision(
            decision_id="dec",
            issue_id="iss",
            reviewer_id="",
            decision_type=ReviewerDecisionType.APPROVE,
            rationale="r",
        ),
        lambda: AIExplanationArtifact(
            explanation_id="ai",
            explanation_type=AIArtifactType.EXPLANATION,
            generated_text="",
            related_issue_id="iss",
        ),
    ],
)
def test_dm02_required_field_enforcement(factory) -> None:
    with pytest.raises(ValueError):
        factory()


# DM-03 Enum correctness

@pytest.mark.parametrize(
    "factory",
    [
        lambda: OntologyChange(
            change_id="chg",
            contributor_id="u",
            timestamp=datetime.now(timezone.utc),
            target_ontology_fragment="f",
            affected_entity="e",
            operation_type="bad",  # type: ignore[arg-type]
            proposed_values={},
        ),
        lambda: ConflictIssue(
            issue_id="iss",
            originating_change_id="chg",
            issue_category="bad",  # type: ignore[arg-type]
            severity=SeverityLevel.MEDIUM,
            evidence={},
            current_workflow_state=WorkflowState.OPEN,
        ),
        lambda: ConflictIssue(
            issue_id="iss",
            originating_change_id="chg",
            issue_category=IssueCategory.CONFLICT,
            severity="bad",  # type: ignore[arg-type]
            evidence={},
            current_workflow_state=WorkflowState.OPEN,
        ),
        lambda: ConflictIssue(
            issue_id="iss",
            originating_change_id="chg",
            issue_category=IssueCategory.CONFLICT,
            severity=SeverityLevel.MEDIUM,
            evidence={},
            current_workflow_state="bad",  # type: ignore[arg-type]
        ),
        lambda: ReviewDecision(
            decision_id="dec",
            issue_id="iss",
            reviewer_id="r",
            decision_type="bad",  # type: ignore[arg-type]
            rationale="text",
        ),
        lambda: AIExplanationArtifact(
            explanation_id="ai",
            explanation_type="bad",  # type: ignore[arg-type]
            generated_text="text",
            related_issue_id="iss",
        ),
    ],
)
def test_dm03_invalid_enum_values_are_rejected(factory) -> None:
    with pytest.raises(ValueError):
        factory()


# DM-04 Timestamp consistency

def test_dm04_timestamp_consistency_and_comparability() -> None:
    t1 = datetime.now(timezone.utc)
    t2 = t1 + timedelta(seconds=5)

    change1 = OntologyChange(
        change_id="chg-ts-1",
        contributor_id="u",
        timestamp=t1,
        target_ontology_fragment="f",
        affected_entity="e1",
        operation_type=OperationType.ADD,
        proposed_values={"label": "A"},
    )
    change2 = OntologyChange(
        change_id="chg-ts-2",
        contributor_id="u",
        timestamp=t2,
        target_ontology_fragment="f",
        affected_entity="e2",
        operation_type=OperationType.ADD,
        proposed_values={"label": "B"},
    )

    assert change1.timestamp.tzinfo is not None
    assert change2.timestamp.tzinfo is not None
    assert change1.timestamp < change2.timestamp


# DM-05 Traceability links

def test_dm05_traceability_links_preserved(linked_registry: dict) -> None:
    registry = linked_registry["registry"]
    change = linked_registry["change"]
    issue = linked_registry["issue"]
    validation = linked_registry["validation"]
    decision = linked_registry["decision"]
    ai_artifact = linked_registry["ai_artifact"]

    assert registry.get_issue(issue.issue_id).originating_change_id == change.change_id
    assert registry.get_validation_result(validation.validation_result_id).change_id == change.change_id
    assert registry.get_review_decision(decision.decision_id).issue_id == issue.issue_id
    assert registry.get_ai_explanation_artifact(ai_artifact.explanation_id).related_validation_result_id == validation.validation_result_id


# DM-06 Ordered issue history

def test_dm06_issue_history_ordering_is_deterministic(linked_registry: dict) -> None:
    registry = linked_registry["registry"]
    issue = linked_registry["issue"]

    t1 = datetime.now(timezone.utc) + timedelta(seconds=1)
    t2 = datetime.now(timezone.utc) + timedelta(seconds=2)
    registry.update_workflow_state(issue.issue_id, WorkflowState.IN_REVIEW, changed_at=t2)
    registry.update_workflow_state(issue.issue_id, WorkflowState.RESOLVED, changed_at=t1)

    history = registry.get_issue_history(issue.issue_id)
    timestamps = [event.timestamp for event in history]
    assert timestamps == sorted(timestamps)


# DM-07 Safe workflow transition guard

def test_dm07_invalid_workflow_transition_rejected(linked_registry: dict) -> None:
    registry = linked_registry["registry"]
    issue_id = linked_registry["issue"].issue_id

    registry.update_workflow_state(issue_id, WorkflowState.IN_REVIEW)
    registry.update_workflow_state(issue_id, WorkflowState.RESOLVED)
    registry.update_workflow_state(issue_id, WorkflowState.CLOSED)

    with pytest.raises(ValueError):
        registry.update_workflow_state(issue_id, WorkflowState.OPEN)


# DM-08 Registry create/read/update flows

def test_dm08_registry_create_read_update_flow_integrity(linked_registry: dict) -> None:
    registry = linked_registry["registry"]
    change = linked_registry["change"]
    issue = linked_registry["issue"]

    fetched_change = registry.get_change(change.change_id)
    fetched_issues = registry.get_issues_for_change(change.change_id)
    registry.update_workflow_state(issue.issue_id, WorkflowState.IN_REVIEW)

    assert fetched_change.change_id == change.change_id
    assert len(fetched_issues) == 1
    assert registry.get_issue(issue.issue_id).current_workflow_state is WorkflowState.IN_REVIEW


# DM-09 Duplicate write protection

def test_dm09_duplicate_writes_are_guarded(linked_registry: dict) -> None:
    registry = linked_registry["registry"]
    change = linked_registry["change"]

    with pytest.raises(ValueError):
        registry.create_change(change)


# DM-10 Advisory-only AI semantics

def test_dm10_ai_artifact_is_advisory_only(linked_registry: dict) -> None:
    artifact = linked_registry["ai_artifact"]
    assert "Advisory only" in artifact.advisory_only_note
    assert "Cannot directly modify ontology content" in artifact.advisory_only_note
