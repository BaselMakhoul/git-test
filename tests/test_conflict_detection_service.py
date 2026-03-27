from datetime import datetime, timedelta, timezone

from thesis_prototype.conflict_detection import ConflictDetectionService, ConflictDetectorConfig
from thesis_prototype.models import (
    ConflictIssue,
    IssueCategory,
    OntologyChange,
    OperationType,
    SeverityLevel,
    WorkflowState,
)
from thesis_prototype.registry import InMemoryIssueRegistry


def _change(
    change_id: str,
    label: str,
    entity: str = "Person",
    operation: OperationType = OperationType.UPDATE,
    timestamp: datetime | None = None,
    extra_values: dict | None = None,
) -> OntologyChange:
    payload = {"label": label}
    if extra_values:
        payload.update(extra_values)
    return OntologyChange(
        change_id=change_id,
        contributor_id="contributor-1",
        timestamp=timestamp or datetime.now(timezone.utc),
        target_ontology_fragment=f"Class:{entity}",
        affected_entity=entity,
        operation_type=operation,
        proposed_values=payload,
    )


def _setup_registry_with_change(change: OntologyChange) -> InMemoryIssueRegistry:
    registry = InMemoryIssueRegistry()
    registry.create_change(change)
    return registry


def test_normalization_behavior() -> None:
    registry = InMemoryIssueRegistry()
    service = ConflictDetectionService(registry)
    assert service.normalize_label("  Human    Being  ") == "human being"


def test_exact_duplicate_found() -> None:
    existing = _change("chg-existing", "Human Being")
    incoming = _change("chg-new", "  human   being ")
    registry = _setup_registry_with_change(existing)
    registry.create_change(incoming)

    service = ConflictDetectionService(registry)
    issues = service.detect_direct_duplicates(incoming)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_category is IssueCategory.DUPLICATE
    assert issue.severity is SeverityLevel.HIGH
    assert issue.originating_change_id == incoming.change_id
    assert issue.evidence["matched_change_id"] == existing.change_id
    assert issue.evidence["machine_code"] == "DIRECT_DUPLICATE_LABEL"


def test_exact_duplicate_not_found_when_materially_different() -> None:
    existing = _change("chg-existing", "Cardiac Disease")
    incoming = _change("chg-new", "Pulmonary Disease")
    registry = _setup_registry_with_change(existing)
    registry.create_change(incoming)

    service = ConflictDetectionService(registry)
    issues = service.detect_direct_duplicates(incoming)

    assert issues == []


def test_near_duplicate_found_above_threshold() -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-new", "Heart Diseases")
    registry = _setup_registry_with_change(existing)
    registry.create_change(incoming)
    service = ConflictDetectionService(registry, ConflictDetectorConfig(near_duplicate_threshold=0.90))

    issues = service.detect_near_duplicates(incoming)

    assert len(issues) == 1
    assert issues[0].issue_category is IssueCategory.DUPLICATE
    assert issues[0].severity is SeverityLevel.MEDIUM
    assert float(issues[0].evidence["similarity_score"]) >= 0.90


def test_near_duplicate_not_found_below_threshold() -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-new", "Lung Condition")
    registry = _setup_registry_with_change(existing)
    registry.create_change(incoming)
    service = ConflictDetectionService(registry, ConflictDetectorConfig(near_duplicate_threshold=0.90))

    issues = service.detect_near_duplicates(incoming)

    assert issues == []


def test_overlap_conflict_for_same_entity() -> None:
    now = datetime.now(timezone.utc)
    existing = _change(
        "chg-existing",
        "Human",
        entity="Person",
        timestamp=now - timedelta(minutes=20),
        extra_values={"definition": "A human person"},
    )
    incoming = _change(
        "chg-new",
        "Person Human",
        entity="Person",
        timestamp=now,
        extra_values={"definition": "A member of Homo sapiens"},
    )

    registry = _setup_registry_with_change(existing)
    # unresolved context created via an existing open issue for the prior change
    registry.create_issue(
        ConflictIssue(
            issue_id="iss-existing-open",
            originating_change_id=existing.change_id,
            issue_category=IssueCategory.CONFLICT,
            severity=SeverityLevel.MEDIUM,
            evidence={"detector": "manual_context"},
            current_workflow_state=WorkflowState.OPEN,
        )
    )
    registry.create_change(incoming)

    service = ConflictDetectionService(registry)
    issues = service.detect_overlap_conflicts(incoming)

    assert len(issues) == 1
    assert issues[0].issue_category is IssueCategory.CONFLICT
    assert issues[0].evidence["matched_change_id"] == existing.change_id
    assert issues[0].evidence["machine_code"] == "OVERLAPPING_CONCURRENT_CHANGE"


def test_overlap_not_triggered_for_unrelated_entities() -> None:
    now = datetime.now(timezone.utc)
    existing = _change("chg-existing", "Human", entity="Person", timestamp=now - timedelta(minutes=10))
    incoming = _change("chg-new", "Hospital", entity="Organization", timestamp=now)
    registry = _setup_registry_with_change(existing)
    registry.create_change(incoming)

    service = ConflictDetectionService(registry)
    issues = service.detect_overlap_conflicts(incoming)

    assert issues == []


def test_issue_creation_traceability_and_deduping() -> None:
    existing = _change("chg-existing", "Human")
    incoming = _change("chg-new", "human")
    registry = _setup_registry_with_change(existing)
    registry.create_change(incoming)
    service = ConflictDetectionService(registry)

    first = service.detect_all(incoming)
    second = service.detect_all(incoming)

    issues_for_change = registry.get_issues_for_change(incoming.change_id)
    assert len(first) >= 1
    assert second == []
    assert len(issues_for_change) == len(first)
    assert all(issue.originating_change_id == incoming.change_id for issue in issues_for_change)
