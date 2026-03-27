from thesis_prototype.demo_backend import DemoBackend


def test_api_path_create_change_works() -> None:
    backend = DemoBackend()
    change = backend.create_change(
        contributor_id="u1",
        affected_entity="Disease",
        operation_type="update",
        label="Heart Disease",
        description="Disease of heart",
    )

    fetched = backend.get_change(change.change_id)
    assert fetched.change_id == change.change_id


def test_api_path_conflict_detection_trigger_works() -> None:
    backend = DemoBackend()
    existing = backend.create_change(
        contributor_id="u1",
        affected_entity="Disease",
        operation_type="update",
        label="Heart Disease",
        description="Disease of heart",
    )
    incoming = backend.create_change(
        contributor_id="u2",
        affected_entity="Disease",
        operation_type="update",
        label="heart disease",
        description="Disease of heart",
    )

    issues = backend.detect_conflicts(incoming.change_id, mode="direct")
    assert len(issues) == 1
    assert issues[0]["originating_change_id"] == incoming.change_id
    assert issues[0]["evidence"]["matched_change_id"] == existing.change_id


def test_api_path_validation_trigger_works() -> None:
    backend = DemoBackend()
    change = backend.create_change(
        contributor_id="u1",
        affected_entity="Disease",
        operation_type="update",
        label="heart_disease",
        description="",
    )

    results = backend.validate_change(change.change_id)
    assert len(results) >= 1
    assert any(result["change_id"] == change.change_id for result in results)


def test_api_path_registry_traceability_summary_works() -> None:
    backend = DemoBackend()
    change = backend.create_change(
        contributor_id="u1",
        affected_entity="Disease",
        operation_type="update",
        label="Heart Disease",
        description="Disease of heart",
    )
    backend.detect_conflicts(change.change_id, mode="all")
    backend.validate_change(change.change_id)

    summary = backend.get_registry_summary()
    assert any(c["change_id"] == change.change_id for c in summary["changes"])
    assert change.change_id in summary["validation_by_change"]
