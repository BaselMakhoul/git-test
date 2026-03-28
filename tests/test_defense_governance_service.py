from datetime import datetime, timezone

import pytest

from thesis_prototype.governance_service import GovernanceReviewService, ReviewWorkflowState
from thesis_prototype.models import (
    ConflictIssue,
    IssueCategory,
    OntologyChange,
    OperationType,
    ReviewerDecisionType,
    RuleType,
    SeverityLevel,
    ValidationResult,
    ValidationStatus,
    WorkflowState,
)
from thesis_prototype.registry import InMemoryIssueRegistry


def _change(change_id: str, label: str = "Heart Disease", description: str = "Disease of heart") -> OntologyChange:
    return OntologyChange(
        change_id=change_id,
        contributor_id="u1",
        timestamp=datetime.now(timezone.utc),
        target_ontology_fragment="Class:Disease",
        affected_entity="Disease",
        operation_type=OperationType.UPDATE,
        proposed_values={"label": label, "description": description},
    )


def _issue(change_id: str, issue_id: str) -> ConflictIssue:
    return ConflictIssue(
        issue_id=issue_id,
        originating_change_id=change_id,
        issue_category=IssueCategory.CONFLICT,
        severity=SeverityLevel.MEDIUM,
        evidence={"machine_code": "DIRECT_DUPLICATE_LABEL", "user_readable_description": "Duplicate label"},
        current_workflow_state=WorkflowState.OPEN,
    )


def _validation(change_id: str, result_id: str, status: ValidationStatus) -> ValidationResult:
    return ValidationResult(
        validation_result_id=result_id,
        change_id=change_id,
        rule_id="VAL-REQ-LABEL",
        rule_type=RuleType.STRUCTURAL,
        status=status,
        target_node="Disease",
        affected_property_path="label",
        machine_readable_message="OK" if status is ValidationStatus.PASS else "MISSING_REQUIRED_LABEL",
        user_readable_message="ok" if status is ValidationStatus.PASS else "Required label is missing",
    )


@pytest.fixture
def setup_context():
    registry = InMemoryIssueRegistry()
    change = _change("chg-gw-1")
    registry.create_change(change)
    issue = _issue(change.change_id, "iss-gw-1")
    registry.create_issue(issue)
    service = GovernanceReviewService(registry)
    return registry, service, change, issue


# GW-01
def test_gw01_route_flagged_issue_to_reviewer(setup_context):
    registry, service, _, issue = setup_context
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    assert service.get_assigned_reviewer(case.review_case_id) == "reviewer-a"


# GW-02
def test_gw02_unflagged_change_bypass_behavior(setup_context):
    registry, service, change, _ = setup_context
    val = _validation(change.change_id, "val-pass", ValidationStatus.PASS)
    registry.create_validation_result(val)
    with pytest.raises(ValueError):
        service.open_review_for_failed_validation(val.validation_result_id)


# GW-03
def test_gw03_reviewer_approval_traceability(setup_context):
    registry, service, change, issue = setup_context
    registry.create_validation_result(_validation(change.change_id, "val-pass2", ValidationStatus.PASS))
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    decision = service.approve(case.review_case_id, "reviewer-a", "All checks pass")
    assert decision.decision_type is ReviewerDecisionType.APPROVE
    assert service.get_review_case(case.review_case_id).workflow_state is ReviewWorkflowState.APPROVED


# GW-04
def test_gw04_reviewer_rejection_traceability(setup_context):
    _, service, _, issue = setup_context
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    decision = service.reject(case.review_case_id, "reviewer-a", "Semantic mismatch")
    assert decision.decision_type is ReviewerDecisionType.REJECT
    assert service.get_review_case(case.review_case_id).workflow_state is ReviewWorkflowState.REJECTED


# GW-05
def test_gw05_request_revision_state(setup_context):
    _, service, _, issue = setup_context
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    service.request_revision(case.review_case_id, "reviewer-a", "Please refine the label")
    assert service.get_review_case(case.review_case_id).workflow_state is ReviewWorkflowState.REVISION_REQUESTED


# GW-06
def test_gw06_correction_and_resubmission_linkage(setup_context):
    registry, service, _, issue = setup_context
    revised = _change("chg-gw-1-rev")
    registry.create_change(revised)

    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    service.request_revision(case.review_case_id, "reviewer-a", "Need correction")
    service.resubmit_with_correction(case.review_case_id, revised.change_id, actor_id="contributor-x")

    case = service.get_review_case(case.review_case_id)
    assert revised.change_id in case.linked_resubmissions
    assert case.current_change_id == revised.change_id


# GW-07
def test_gw07_history_preserved_in_order(setup_context):
    _, service, _, issue = setup_context
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    service.request_revision(case.review_case_id, "reviewer-a", "Revise")
    history = service.get_review_history(case.review_case_id)
    assert len(history) >= 3
    assert [h.timestamp for h in history] == sorted(h.timestamp for h in history)


# GW-08
def test_gw08_unauthorized_reviewer_action_blocked(setup_context):
    _, service, _, issue = setup_context
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    with pytest.raises(PermissionError):
        service.reject(case.review_case_id, "reviewer-b", "Not assigned")


# GW-09
def test_gw09_approve_without_validation_guard_blocked(setup_context):
    registry, service, change, issue = setup_context
    registry.create_validation_result(_validation(change.change_id, "val-fail", ValidationStatus.FAIL))
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    with pytest.raises(ValueError):
        service.approve(case.review_case_id, "reviewer-a", "approve")


# GW-10
def test_gw10_duplicate_decision_protection(setup_context):
    registry, service, change, issue = setup_context
    registry.create_validation_result(_validation(change.change_id, "val-pass3", ValidationStatus.PASS))
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    service.approve(case.review_case_id, "reviewer-a", "ok")
    service.close_review_case(case.review_case_id)
    with pytest.raises(ValueError):
        service.reject(case.review_case_id, "reviewer-a", "late reject")


# GW-11
def test_gw11_rationale_required(setup_context):
    _, service, _, issue = setup_context
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    with pytest.raises(ValueError):
        service.request_revision(case.review_case_id, "reviewer-a", "   ")


# GW-12
def test_gw12_multi_issue_change_traceability() -> None:
    registry = InMemoryIssueRegistry()
    change = _change("chg-gw-12")
    registry.create_change(change)
    i1 = _issue(change.change_id, "iss-gw-12-a")
    i2 = _issue(change.change_id, "iss-gw-12-b")
    registry.create_issue(i1)
    registry.create_issue(i2)
    service = GovernanceReviewService(registry)

    c1 = service.open_review_for_issue(i1.issue_id)
    c2 = service.open_review_for_issue(i2.issue_id)
    assert c1.originating_change_id == change.change_id
    assert c2.originating_change_id == change.change_id
    assert len(service.list_review_cases_for_change(change.change_id)) == 2


# GW-13
def test_gw13_state_transition_safety(setup_context):
    _, service, _, issue = setup_context
    case = service.open_review_for_issue(issue.issue_id)
    with pytest.raises(ValueError):
        service.resubmit_with_correction(case.review_case_id, "non-existent", actor_id="x")


# GW-14
def test_gw14_decision_traceability_links(setup_context):
    registry, service, change, issue = setup_context
    registry.create_validation_result(_validation(change.change_id, "val-pass4", ValidationStatus.PASS))
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    decision = service.approve(case.review_case_id, "reviewer-a", "clear")

    assert decision.issue_id == issue.issue_id
    assert decision.reviewer_id == "reviewer-a"
    assert decision.rationale == "clear"


# GW-15
def test_gw15_review_completion_closure(setup_context):
    registry, service, change, issue = setup_context
    registry.create_validation_result(_validation(change.change_id, "val-pass5", ValidationStatus.PASS))
    case = service.open_review_for_issue(issue.issue_id)
    service.assign_reviewer(case.review_case_id, "reviewer-a")
    service.approve(case.review_case_id, "reviewer-a", "ok")
    case = service.close_review_case(case.review_case_id)
    assert case.workflow_state is ReviewWorkflowState.CLOSED
