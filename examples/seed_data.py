from datetime import datetime, timezone

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


def build_seed_registry() -> InMemoryIssueRegistry:
    registry = InMemoryIssueRegistry()

    change = OntologyChange(
        change_id="chg-001",
        contributor_id="user-123",
        timestamp=datetime.now(timezone.utc),
        target_ontology_fragment="Class:Person",
        affected_entity="Person",
        operation_type=OperationType.UPDATE,
        proposed_values={"label": "Human"},
        optional_note="Harmonize naming",
    )
    registry.create_change(change)

    issue = ConflictIssue(
        issue_id="iss-001",
        originating_change_id=change.change_id,
        issue_category=IssueCategory.CONFLICT,
        severity=SeverityLevel.MEDIUM,
        evidence={"matched_change_id": "chg-000"},
        current_workflow_state=WorkflowState.OPEN,
    )
    registry.create_issue(issue)

    result = ValidationResult(
        validation_result_id="vr-001",
        change_id=change.change_id,
        rule_id="RULE-001",
        rule_type=RuleType.STRUCTURAL,
        status=ValidationStatus.FAIL,
        target_node="Person",
        affected_property_path="rdfs:label",
        machine_readable_message="DUPLICATE_LABEL",
        user_readable_message="Label already exists on another class.",
    )
    registry.create_validation_result(result)
    registry.link_validation_to_issue(issue.issue_id, result.validation_result_id)

    decision = ReviewDecision(
        decision_id="dec-001",
        issue_id=issue.issue_id,
        reviewer_id="reviewer-456",
        decision_type=ReviewerDecisionType.REQUEST_REVISION,
        rationale="Needs ontology owner clarification.",
    )
    registry.record_review_decision(decision)

    artifact = AIExplanationArtifact(
        explanation_id="ai-001",
        explanation_type=AIArtifactType.EXPLANATION,
        related_issue_id=issue.issue_id,
        generated_text="Potential overlap with existing concept naming.",
    )
    registry.record_ai_explanation_artifact(artifact)

    return registry


if __name__ == "__main__":
    seeded_registry = build_seed_registry()
    print(f"Seeded changes: {len(seeded_registry.get_issues_for_change('chg-001'))} issue(s)")
