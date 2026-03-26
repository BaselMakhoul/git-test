from datetime import datetime, timedelta, timezone

import pytest

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


@pytest.fixture
def detector_config() -> ConflictDetectorConfig:
    return ConflictDetectorConfig(
        near_duplicate_threshold=0.88,
        overlap_active_window_minutes=60,
        overlap_sensitive_fields={"label", "definition"},
    )


def _change(
    change_id: str,
    label: str | None,
    entity: str = "Disease",
    operation_type: OperationType = OperationType.UPDATE,
    timestamp: datetime | None = None,
    extra_values: dict | None = None,
) -> OntologyChange:
    values = {} if label is None else {"label": label}
    if extra_values:
        values.update(extra_values)
    return OntologyChange(
        change_id=change_id,
        contributor_id="defense-user",
        timestamp=timestamp or datetime.now(timezone.utc),
        target_ontology_fragment=f"Class:{entity}",
        affected_entity=entity,
        operation_type=operation_type,
        proposed_values=values,
    )


def _registry_with_changes(*changes: OntologyChange) -> InMemoryIssueRegistry:
    registry = InMemoryIssueRegistry()
    for c in changes:
        registry.create_change(c)
    return registry


# CD-01 Exact duplicate label
def test_cd01_exact_duplicate_label(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-incoming", "heart disease")
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    issues = service.detect_direct_duplicates(incoming)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity is SeverityLevel.HIGH
    assert issue.issue_category is IssueCategory.DUPLICATE
    assert issue.evidence["machine_code"] == "DIRECT_DUPLICATE_LABEL"
    assert "exactly matches" in issue.evidence["user_readable_description"]


# CD-02 Duplicate with extra spacing
def test_cd02_duplicate_with_extra_spacing(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-incoming", "  Heart   Disease  ")
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    issues = service.detect_direct_duplicates(incoming)

    assert len(issues) == 1
    assert issues[0].evidence["normalized_label"] == "heart disease"


# CD-03 Materially different labels
def test_cd03_materially_different_labels_no_direct_duplicate(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-incoming", "Kidney Failure")
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    assert service.detect_direct_duplicates(incoming) == []


# CD-04 Near-duplicate singular/plural
def test_cd04_near_duplicate_singular_plural(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Cardiac Disorder")
    incoming = _change("chg-incoming", "Cardiac Disorders")
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    issues = service.detect_near_duplicates(incoming)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity is SeverityLevel.MEDIUM
    assert issue.evidence["machine_code"] == "NEAR_DUPLICATE_LABEL"
    assert float(issue.evidence["similarity_score"]) >= detector_config.near_duplicate_threshold


# CD-05 Near-duplicate below threshold
def test_cd05_near_duplicate_below_threshold_not_flagged(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Cardiac Disorder")
    incoming = _change("chg-incoming", "Kidney Function")
    registry = _registry_with_changes(existing, incoming)

    strict_config = ConflictDetectorConfig(near_duplicate_threshold=0.90)
    service = ConflictDetectionService(registry, strict_config)
    assert service.detect_near_duplicates(incoming) == []


# CD-06 Threshold boundary case (inclusive)
def test_cd06_threshold_boundary_is_inclusive(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Cardiac Disorder")
    incoming = _change("chg-incoming", "Cardiac Disorders")
    registry = _registry_with_changes(existing, incoming)

    service_probe = ConflictDetectionService(registry, detector_config)
    boundary = service_probe.label_similarity("Cardiac Disorder", "Cardiac Disorders")

    boundary_config = ConflictDetectorConfig(near_duplicate_threshold=boundary)
    service = ConflictDetectionService(registry, boundary_config)
    issues = service.detect_near_duplicates(incoming)

    assert len(issues) == 1  # inclusive behavior: score == threshold is flagged


# CD-07 Same entity overlap conflict
def test_cd07_same_entity_overlap_conflict(detector_config: ConflictDetectorConfig) -> None:
    now = datetime.now(timezone.utc)
    existing = _change(
        "chg-existing",
        "Heart Disease",
        entity="Disease",
        timestamp=now - timedelta(minutes=20),
        extra_values={"definition": "Heart-related disease"},
    )
    incoming = _change(
        "chg-incoming",
        "Heart Condition",
        entity="Disease",
        timestamp=now,
        extra_values={"definition": "Condition affecting heart"},
    )
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    issues = service.detect_overlap_conflicts(incoming)

    assert len(issues) == 1
    assert issues[0].issue_category is IssueCategory.CONFLICT


# CD-08 Same entity but different insensitive field
def test_cd08_same_entity_insensitive_field_no_overlap(detector_config: ConflictDetectorConfig) -> None:
    now = datetime.now(timezone.utc)
    existing = _change(
        "chg-existing",
        None,
        entity="Disease",
        timestamp=now - timedelta(minutes=10),
        extra_values={"synonym": "Cardiac illness"},
    )
    incoming = _change(
        "chg-incoming",
        None,
        entity="Disease",
        timestamp=now,
        extra_values={"synonym": "Heart issue"},
    )
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    assert service.detect_overlap_conflicts(incoming) == []


# CD-09 Different entity no overlap
def test_cd09_different_entity_no_overlap(detector_config: ConflictDetectorConfig) -> None:
    now = datetime.now(timezone.utc)
    existing = _change("chg-existing", "Heart Disease", entity="Disease", timestamp=now - timedelta(minutes=10))
    incoming = _change("chg-incoming", "Cardiac Unit", entity="Organization", timestamp=now)
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    assert service.detect_overlap_conflicts(incoming) == []


# CD-10 Unresolved context via open issue
def test_cd10_open_issue_context_triggers_overlap() -> None:
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    existing = _change(
        "chg-existing",
        "Heart Disease",
        entity="Disease",
        timestamp=old_time,
        extra_values={"definition": "Heart-related disease"},
    )
    incoming = _change(
        "chg-incoming",
        "Heart Condition",
        entity="Disease",
        timestamp=datetime.now(timezone.utc),
        extra_values={"definition": "Condition affecting heart"},
    )
    registry = _registry_with_changes(existing, incoming)
    registry.create_issue(
        ConflictIssue(
            issue_id="iss-open",
            originating_change_id=existing.change_id,
            issue_category=IssueCategory.CONFLICT,
            severity=SeverityLevel.MEDIUM,
            evidence={"reason": "open context"},
            current_workflow_state=WorkflowState.OPEN,
        )
    )

    strict_window = ConflictDetectorConfig(overlap_active_window_minutes=5)
    service = ConflictDetectionService(registry, strict_window)
    issues = service.detect_overlap_conflicts(incoming)

    assert len(issues) == 1
    assert issues[0].severity is SeverityLevel.HIGH
    assert issues[0].evidence["has_unresolved_context"] is True


# CD-11 Closed issue context
def test_cd11_closed_issue_context_not_unresolved_by_itself() -> None:
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    existing = _change(
        "chg-existing",
        "Heart Disease",
        entity="Disease",
        timestamp=old_time,
        extra_values={"definition": "Heart-related disease"},
    )
    incoming = _change(
        "chg-incoming",
        "Heart Condition",
        entity="Disease",
        timestamp=datetime.now(timezone.utc),
        extra_values={"definition": "Condition affecting heart"},
    )
    registry = _registry_with_changes(existing, incoming)
    registry.create_issue(
        ConflictIssue(
            issue_id="iss-closed",
            originating_change_id=existing.change_id,
            issue_category=IssueCategory.CONFLICT,
            severity=SeverityLevel.MEDIUM,
            evidence={"reason": "historical"},
            current_workflow_state=WorkflowState.CLOSED,
        )
    )

    strict_window = ConflictDetectorConfig(overlap_active_window_minutes=5)
    service = ConflictDetectionService(registry, strict_window)
    assert service.detect_overlap_conflicts(incoming) == []


# CD-12 Repeated detection idempotency
def test_cd12_repeated_detection_is_idempotent(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-incoming", "heart disease")
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    first = service.detect_all(incoming)
    second = service.detect_all(incoming)

    assert len(first) >= 1
    assert second == []
    assert len(registry.get_issues_for_change(incoming.change_id)) == len(first)


# CD-13 Evidence quality
def test_cd13_evidence_quality_for_each_conflict_type(detector_config: ConflictDetectorConfig) -> None:
    # direct duplicate
    registry_direct = _registry_with_changes(
        _change("chg-a", "Heart Disease"),
        _change("chg-b", "heart disease"),
    )
    direct_issue = ConflictDetectionService(registry_direct, detector_config).detect_direct_duplicates(
        registry_direct.get_change("chg-b")
    )[0]
    assert {"matched_change_id", "machine_code", "user_readable_description"}.issubset(direct_issue.evidence)

    # near duplicate
    registry_near = _registry_with_changes(
        _change("chg-c", "Cardiac Disorder"),
        _change("chg-d", "Cardiac Disorders"),
    )
    near_issue = ConflictDetectionService(registry_near, detector_config).detect_near_duplicates(
        registry_near.get_change("chg-d")
    )[0]
    assert {"similarity_score", "threshold", "machine_code", "user_readable_description"}.issubset(near_issue.evidence)

    # overlap conflict
    now = datetime.now(timezone.utc)
    registry_overlap = _registry_with_changes(
        _change("chg-e", "Heart Disease", timestamp=now - timedelta(minutes=5), extra_values={"definition": "x"}),
        _change("chg-f", "Heart Condition", timestamp=now, extra_values={"definition": "y"}),
    )
    overlap_issue = ConflictDetectionService(registry_overlap, detector_config).detect_overlap_conflicts(
        registry_overlap.get_change("chg-f")
    )[0]
    assert {"affected_entity", "shared_sensitive_fields", "machine_code", "user_readable_description"}.issubset(
        overlap_issue.evidence
    )


# CD-14 Missing label input
def test_cd14_missing_label_input_is_handled_safely(detector_config: ConflictDetectorConfig) -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-incoming", None, extra_values={"definition": "No label present"})
    registry = _registry_with_changes(existing, incoming)

    service = ConflictDetectionService(registry, detector_config)
    assert service.detect_direct_duplicates(incoming) == []
    assert service.detect_near_duplicates(incoming) == []


# CD-15 Case-insensitive and normalization consistency
@pytest.mark.parametrize(
    "variant",
    ["heart disease", " HEART DISEASE ", "Heart   Disease", "  heart    disease   "],
)
def test_cd15_normalization_consistency_across_variants(
    detector_config: ConflictDetectorConfig, variant: str
) -> None:
    existing = _change("chg-existing", "Heart Disease")
    incoming = _change("chg-incoming", variant)
    registry = _registry_with_changes(existing, incoming)
    service = ConflictDetectionService(registry, detector_config)

    normalized_existing = service.normalize_label("Heart Disease")
    normalized_variant = service.normalize_label(variant)
    issues = service.detect_direct_duplicates(incoming)

    assert normalized_existing == normalized_variant == "heart disease"
    assert len(issues) == 1
