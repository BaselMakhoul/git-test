from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from .models import OntologyChange, RuleType, ValidationResult, ValidationStatus
from .registry import InMemoryIssueRegistry


class ValidationAdapter(Protocol):
    """Boundary interface for future SHACL/engine-backed validation adapters."""

    def validate(self, change: OntologyChange, config: "ValidationConfig") -> Sequence[ValidationResult]:
        ...


@dataclass(frozen=True)
class ValidationRuleDefinition:
    rule_id: str
    rule_type: RuleType
    description: str
    fail_message_template: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationConfig:
    required_label_field: str = "label"
    required_description_field: str = "description"
    naming_convention_pattern: str = r"^[A-Z][A-Za-z0-9\-\s]*$"
    cardinality_constraints: Dict[str, Tuple[int, int]] = field(
        default_factory=lambda: {"label": (1, 1), "description": (1, 1)}
    )
    expected_domain_by_property: Dict[str, str] = field(default_factory=dict)
    expected_range_by_property: Dict[str, str] = field(default_factory=dict)
    rule_definitions: List[ValidationRuleDefinition] = field(
        default_factory=lambda: [
            ValidationRuleDefinition(
                rule_id="VAL-REQ-LABEL",
                rule_type=RuleType.STRUCTURAL,
                description="Label is required.",
                fail_message_template="Required label is missing or empty.",
                metadata={"field": "label"},
            ),
            ValidationRuleDefinition(
                rule_id="VAL-REQ-DESCRIPTION",
                rule_type=RuleType.STRUCTURAL,
                description="Description is required.",
                fail_message_template="Required description is missing or empty.",
                metadata={"field": "description"},
            ),
            ValidationRuleDefinition(
                rule_id="VAL-CARDINALITY",
                rule_type=RuleType.SCHEMA,
                description="Configured property cardinality must be respected.",
                fail_message_template="Cardinality violation for property '{property_path}'.",
                metadata={"constraint_source": "cardinality_constraints"},
            ),
            ValidationRuleDefinition(
                rule_id="VAL-DOMAIN-RANGE",
                rule_type=RuleType.SCHEMA,
                description="Configured property domain/range must match expected values.",
                fail_message_template=(
                    "Domain/range mismatch for property '{property_path}' "
                    "(expected domain={expected_domain}, range={expected_range})."
                ),
                metadata={"constraint_source": "expected_domain/range_by_property"},
            ),
            ValidationRuleDefinition(
                rule_id="VAL-NAMING-CONVENTION",
                rule_type=RuleType.CUSTOM,
                description="Label must follow configured naming convention regex.",
                fail_message_template="Label '{value}' does not match naming convention.",
                metadata={"pattern_key": "naming_convention_pattern"},
            ),
        ]
    )

    def validate(self) -> None:
        rule_ids = [rule.rule_id for rule in self.rule_definitions]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule_definitions must use unique rule_id values")
        if not (self.required_label_field and self.required_description_field):
            raise ValueError("required field names cannot be empty")
        try:
            re.compile(self.naming_convention_pattern)
        except re.error as exc:
            raise ValueError("naming_convention_pattern is invalid") from exc


class LightweightValidationAdapter:
    """Deterministic in-process rule evaluator for thesis T35."""

    def validate(self, change: OntologyChange, config: ValidationConfig) -> Sequence[ValidationResult]:
        service = ValidationService(registry=None, config=config, adapter=self)
        return service._evaluate_rules(change)


class ValidationService:
    def __init__(
        self,
        registry: Optional[InMemoryIssueRegistry],
        config: Optional[ValidationConfig] = None,
        adapter: Optional[ValidationAdapter] = None,
    ) -> None:
        self.registry = registry
        self.config = config or ValidationConfig()
        self.config.validate()
        self.adapter = adapter or LightweightValidationAdapter()

    def validate_change(self, change: OntologyChange, persist: bool = True) -> List[ValidationResult]:
        results = list(self.adapter.validate(change, self.config))
        if persist:
            if self.registry is None:
                raise ValueError("registry is required when persist=True")
            return [self._persist_or_get_existing(result) for result in results]
        return results

    def get_results_for_change(self, change_id: str) -> List[ValidationResult]:
        if self.registry is None:
            raise ValueError("registry is required for result retrieval")
        return sorted(
            self.registry.get_validation_results_for_change(change_id),
            key=lambda result: (result.rule_id, result.validation_result_id),
        )

    def _evaluate_rules(self, change: OntologyChange) -> List[ValidationResult]:
        proposed = change.proposed_values or {}
        rule_lookup = {rule.rule_id: rule for rule in self.config.rule_definitions}
        ordered_rule_ids = [rule.rule_id for rule in self.config.rule_definitions]
        evaluated: List[ValidationResult] = []

        for rule_id in ordered_rule_ids:
            rule = rule_lookup[rule_id]
            result = self._evaluate_single_rule(change, proposed, rule)
            evaluated.append(result)

        return evaluated

    def _evaluate_single_rule(
        self,
        change: OntologyChange,
        proposed: Dict[str, Any],
        rule: ValidationRuleDefinition,
    ) -> ValidationResult:
        if rule.rule_id == "VAL-REQ-LABEL":
            value = proposed.get(self.config.required_label_field)
            passed = isinstance(value, str) and bool(value.strip())
            return self._build_result(
                change=change,
                rule=rule,
                passed=passed,
                property_path=self.config.required_label_field,
                machine_code="VALIDATION_PASS" if passed else "MISSING_REQUIRED_LABEL",
                user_message="Label is present." if passed else rule.fail_message_template,
            )

        if rule.rule_id == "VAL-REQ-DESCRIPTION":
            value = proposed.get(self.config.required_description_field)
            passed = isinstance(value, str) and bool(value.strip())
            return self._build_result(
                change=change,
                rule=rule,
                passed=passed,
                property_path=self.config.required_description_field,
                machine_code="VALIDATION_PASS" if passed else "MISSING_REQUIRED_DESCRIPTION",
                user_message="Description is present." if passed else rule.fail_message_template,
            )

        if rule.rule_id == "VAL-CARDINALITY":
            violations = []
            for key, (minimum, maximum) in self.config.cardinality_constraints.items():
                value = proposed.get(key)
                count = len(value) if isinstance(value, list) else (1 if value not in (None, "") else 0)
                if count < minimum or count > maximum:
                    violations.append((key, minimum, maximum, count))

            passed = not violations
            if passed:
                return self._build_result(
                    change=change,
                    rule=rule,
                    passed=True,
                    property_path="*",
                    machine_code="VALIDATION_PASS",
                    user_message="Cardinality constraints satisfied.",
                )

            key, minimum, maximum, count = violations[0]
            return self._build_result(
                change=change,
                rule=rule,
                passed=False,
                property_path=key,
                machine_code="CARDINALITY_VIOLATION",
                user_message=(
                    rule.fail_message_template.format(property_path=key)
                    + f" Expected {minimum}..{maximum}, found {count}."
                ),
            )

        if rule.rule_id == "VAL-DOMAIN-RANGE":
            prop = proposed.get("property")
            domain = proposed.get("domain")
            range_ = proposed.get("range")

            expected_domain = self.config.expected_domain_by_property.get(str(prop), "")
            expected_range = self.config.expected_range_by_property.get(str(prop), "")
            mismatch = bool(prop) and ((expected_domain and domain != expected_domain) or (expected_range and range_ != expected_range))

            if mismatch:
                return self._build_result(
                    change=change,
                    rule=rule,
                    passed=False,
                    property_path=str(prop),
                    machine_code="DOMAIN_RANGE_MISMATCH",
                    user_message=rule.fail_message_template.format(
                        property_path=prop,
                        expected_domain=expected_domain,
                        expected_range=expected_range,
                    ),
                )

            return self._build_result(
                change=change,
                rule=rule,
                passed=True,
                property_path=str(prop) if prop else "*",
                machine_code="VALIDATION_PASS",
                user_message="Domain/range expectations satisfied or not applicable.",
            )

        if rule.rule_id == "VAL-NAMING-CONVENTION":
            value = proposed.get(self.config.required_label_field)
            pattern = re.compile(self.config.naming_convention_pattern)
            passed = isinstance(value, str) and bool(pattern.match(value.strip()))
            return self._build_result(
                change=change,
                rule=rule,
                passed=passed,
                property_path=self.config.required_label_field,
                machine_code="VALIDATION_PASS" if passed else "NAMING_CONVENTION_VIOLATION",
                user_message=(
                    "Naming convention satisfied."
                    if passed
                    else rule.fail_message_template.format(value=value)
                ),
            )

        raise ValueError(f"Unknown validation rule_id: {rule.rule_id}")

    def _build_result(
        self,
        change: OntologyChange,
        rule: ValidationRuleDefinition,
        passed: bool,
        property_path: str,
        machine_code: str,
        user_message: str,
    ) -> ValidationResult:
        status = ValidationStatus.PASS if passed else ValidationStatus.FAIL
        result_id = self._result_id(change.change_id, rule.rule_id, property_path)
        return ValidationResult(
            validation_result_id=result_id,
            change_id=change.change_id,
            rule_id=rule.rule_id,
            rule_type=rule.rule_type,
            status=status,
            target_node=change.affected_entity,
            affected_property_path=property_path,
            machine_readable_message=machine_code,
            user_readable_message=user_message,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _result_id(change_id: str, rule_id: str, property_path: str) -> str:
        payload = {"change_id": change_id, "rule_id": rule_id, "property_path": property_path}
        digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return f"val-{digest[:12]}"

    def _persist_or_get_existing(self, result: ValidationResult) -> ValidationResult:
        assert self.registry is not None
        try:
            self.registry.create_validation_result(result)
            return result
        except ValueError:
            return self.registry.get_validation_result(result.validation_result_id)
