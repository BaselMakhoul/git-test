from datetime import datetime, timezone

import pytest

from thesis_prototype.models import OntologyChange, OperationType, RuleType, ValidationStatus
from thesis_prototype.registry import InMemoryIssueRegistry
from thesis_prototype.validation_service import (
    ValidationAdapter,
    ValidationConfig,
    ValidationRuleDefinition,
    ValidationService,
)


@pytest.fixture
def registry() -> InMemoryIssueRegistry:
    return InMemoryIssueRegistry()


@pytest.fixture
def validation_config() -> ValidationConfig:
    return ValidationConfig(
        expected_domain_by_property={"hasSymptom": "Disease"},
        expected_range_by_property={"hasSymptom": "Symptom"},
    )


def _change(change_id: str, proposed_values: dict) -> OntologyChange:
    return OntologyChange(
        change_id=change_id,
        contributor_id="validator",
        timestamp=datetime.now(timezone.utc),
        target_ontology_fragment="Class:Disease",
        affected_entity="Disease",
        operation_type=OperationType.UPDATE,
        proposed_values=proposed_values,
    )


# VS-01 Required label present
def test_vs01_required_label_present(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs01", {"label": "Heart Disease", "description": "Disease of heart"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    results = service.validate_change(change)
    by_rule = {r.rule_id: r for r in results}

    assert by_rule["VAL-REQ-LABEL"].status is ValidationStatus.PASS


# VS-02 Missing required label
def test_vs02_missing_required_label_fails(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs02", {"description": "Disease of heart"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    result = {r.rule_id: r for r in service.validate_change(change)}["VAL-REQ-LABEL"]
    assert result.status is ValidationStatus.FAIL
    assert result.machine_readable_message == "MISSING_REQUIRED_LABEL"
    assert result.rule_id == "VAL-REQ-LABEL"
    assert "missing" in result.user_readable_message.lower()


# VS-03 Required description present
def test_vs03_required_description_present(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs03", {"label": "Heart Disease", "description": "Disease of heart"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    result = {r.rule_id: r for r in service.validate_change(change)}["VAL-REQ-DESCRIPTION"]
    assert result.status is ValidationStatus.PASS


# VS-04 Missing required description
def test_vs04_missing_required_description_fails(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs04", {"label": "Heart Disease"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    result = {r.rule_id: r for r in service.validate_change(change)}["VAL-REQ-DESCRIPTION"]
    assert result.status is ValidationStatus.FAIL


# VS-05 Cardinality violation
def test_vs05_cardinality_violation_fails(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change(
        "chg-vs05",
        {"label": ["Heart Disease", "Cardiac Disease"], "description": "Disease of heart"},
    )
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    result = {r.rule_id: r for r in service.validate_change(change)}["VAL-CARDINALITY"]
    assert result.status is ValidationStatus.FAIL
    assert result.machine_readable_message == "CARDINALITY_VIOLATION"


# VS-06 Domain/range mismatch
def test_vs06_domain_range_mismatch_fails(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change(
        "chg-vs06",
        {
            "label": "Heart Disease",
            "description": "Disease of heart",
            "property": "hasSymptom",
            "domain": "Drug",
            "range": "Symptom",
        },
    )
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    result = {r.rule_id: r for r in service.validate_change(change)}["VAL-DOMAIN-RANGE"]
    assert result.status is ValidationStatus.FAIL
    assert result.affected_property_path == "hasSymptom"


# VS-07 Naming convention rule
def test_vs07_naming_convention_violation_fails(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs07", {"label": "heart_disease", "description": "Disease of heart"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    result = {r.rule_id: r for r in service.validate_change(change)}["VAL-NAMING-CONVENTION"]
    assert result.status is ValidationStatus.FAIL


# VS-08 Multiple rules on one change
def test_vs08_multiple_rules_one_change(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs08", {"label": "heart_disease"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    results = service.validate_change(change)
    failures = [r for r in results if r.status is ValidationStatus.FAIL]
    assert len(results) == len(validation_config.rule_definitions)
    assert len(failures) >= 2


# VS-09 Clean change full pass
def test_vs09_clean_change_full_pass(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change(
        "chg-vs09",
        {
            "label": "Heart Disease",
            "description": "Disease of heart",
            "property": "hasSymptom",
            "domain": "Disease",
            "range": "Symptom",
        },
    )
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    results = service.validate_change(change)
    assert all(result.status is ValidationStatus.PASS for result in results)


# VS-10 Stable rule ordering
def test_vs10_stable_rule_ordering(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs10", {"label": "Heart Disease", "description": "Disease of heart"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    first = [r.rule_id for r in service.validate_change(change, persist=False)]
    second = [r.rule_id for r in service.validate_change(change, persist=False)]
    assert first == second


# VS-11 Registry traceability
def test_vs11_registry_traceability_by_change_id(
    registry: InMemoryIssueRegistry, validation_config: ValidationConfig
) -> None:
    change = _change("chg-vs11", {"label": "Heart Disease", "description": "Disease of heart"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    service.validate_change(change)
    stored = service.get_results_for_change(change.change_id)
    assert len(stored) == len(validation_config.rule_definitions)
    assert all(result.change_id == change.change_id for result in stored)


# VS-12 Invalid configuration handling
def test_vs12_invalid_configuration_raises_error(registry: InMemoryIssueRegistry) -> None:
    bad_config = ValidationConfig(naming_convention_pattern="(")
    change = _change("chg-vs12", {"label": "Heart Disease", "description": "Disease of heart"})
    registry.create_change(change)

    with pytest.raises(ValueError):
        ValidationService(registry, bad_config)


# VS-13 Empty change payload
def test_vs13_empty_payload_graceful_behavior(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    change = _change("chg-vs13", {})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    results = service.validate_change(change)
    assert len(results) == len(validation_config.rule_definitions)


# VS-14 SHACL adapter boundary
def test_vs14_adapter_boundary_is_modular(registry: InMemoryIssueRegistry, validation_config: ValidationConfig) -> None:
    class MockAdapter(ValidationAdapter):
        def validate(self, change: OntologyChange, config: ValidationConfig):
            return [
                service._build_result(
                    change=change,
                    rule=config.rule_definitions[0],
                    passed=True,
                    property_path="label",
                    machine_code="MOCK_PASS",
                    user_message="Adapter-driven result",
                )
            ]

    change = _change("chg-vs14", {"label": "Heart Disease", "description": "Disease of heart"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)
    service.adapter = MockAdapter()

    results = service.validate_change(change, persist=False)
    assert len(results) == 1
    assert results[0].machine_readable_message == "MOCK_PASS"


# VS-15 Human-readable message quality
def test_vs15_human_readable_message_quality(
    registry: InMemoryIssueRegistry, validation_config: ValidationConfig
) -> None:
    change = _change("chg-vs15", {"label": "heart_disease"})
    registry.create_change(change)
    service = ValidationService(registry, validation_config)

    results = service.validate_change(change)
    messages = [r.user_readable_message for r in results]

    assert all(isinstance(m, str) and len(m.strip()) > 10 for m in messages)
    assert any("missing" in m.lower() for m in messages)
