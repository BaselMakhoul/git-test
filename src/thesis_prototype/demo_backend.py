from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .conflict_detection import ConflictDetectionService
from .models import OntologyChange, OperationType
from .registry import InMemoryIssueRegistry
from .validation_service import ValidationConfig, ValidationService


class DemoBackend:
    """Thin orchestration layer for demo API/UI interactions."""

    def __init__(self) -> None:
        self.registry = InMemoryIssueRegistry()
        self.conflicts = ConflictDetectionService(self.registry)
        self.validation = ValidationService(
            self.registry,
            ValidationConfig(
                expected_domain_by_property={"hasSymptom": "Disease"},
                expected_range_by_property={"hasSymptom": "Symptom"},
            ),
        )

    def create_change(
        self,
        contributor_id: str,
        affected_entity: str,
        operation_type: str,
        label: Optional[str],
        description: Optional[str],
        optional_note: Optional[str] = None,
        scenario_id: Optional[str] = None,
        revision_reference: Optional[str] = None,
        proposed_values_extra: Optional[Dict[str, Any]] = None,
    ) -> OntologyChange:
        op = OperationType(operation_type)
        proposed_values: Dict[str, Any] = {}
        if label is not None:
            proposed_values["label"] = label
        if description is not None:
            proposed_values["description"] = description
        if proposed_values_extra:
            proposed_values.update(proposed_values_extra)

        change = OntologyChange(
            change_id=f"chg-{uuid4().hex[:10]}",
            contributor_id=contributor_id,
            timestamp=datetime.now(timezone.utc),
            target_ontology_fragment=f"Class:{affected_entity}",
            affected_entity=affected_entity,
            operation_type=op,
            proposed_values=proposed_values,
            optional_note=optional_note,
            scenario_id=scenario_id,
            revision_reference=revision_reference,
        )
        self.registry.create_change(change)
        return change

    def list_changes(self) -> List[OntologyChange]:
        return sorted(self.registry.list_changes(), key=lambda c: (c.timestamp, c.change_id))

    def get_change(self, change_id: str) -> OntologyChange:
        return self.registry.get_change(change_id)

    def detect_conflicts(self, change_id: str, mode: str = "all") -> List[Dict[str, Any]]:
        change = self.registry.get_change(change_id)
        if mode == "direct":
            issues = self.conflicts.detect_direct_duplicates(change)
        elif mode == "near":
            issues = self.conflicts.detect_near_duplicates(change)
        elif mode == "overlap":
            issues = self.conflicts.detect_overlap_conflicts(change)
        elif mode == "all":
            issues = self.conflicts.detect_all(change)
        else:
            raise ValueError("mode must be one of: direct, near, overlap, all")
        return [to_jsonable(issue) for issue in issues]

    def validate_change(self, change_id: str) -> List[Dict[str, Any]]:
        change = self.registry.get_change(change_id)
        results = self.validation.validate_change(change)
        return [to_jsonable(result) for result in results]

    def get_issues_for_change(self, change_id: str) -> List[Dict[str, Any]]:
        return [to_jsonable(issue) for issue in self.registry.get_issues_for_change(change_id)]

    def get_validation_results_for_change(self, change_id: str) -> List[Dict[str, Any]]:
        return [to_jsonable(result) for result in self.registry.get_validation_results_for_change(change_id)]

    def get_registry_summary(self) -> Dict[str, Any]:
        changes = self.list_changes()
        summary = {
            "changes": [to_jsonable(change) for change in changes],
            "issues_by_change": {},
            "validation_by_change": {},
            "history_by_issue": {},
        }
        for change in changes:
            issues = self.registry.get_issues_for_change(change.change_id)
            vals = self.registry.get_validation_results_for_change(change.change_id)
            summary["issues_by_change"][change.change_id] = [to_jsonable(issue) for issue in issues]
            summary["validation_by_change"][change.change_id] = [to_jsonable(v) for v in vals]
            for issue in issues:
                summary["history_by_issue"][issue.issue_id] = [
                    to_jsonable(event) for event in self.registry.get_issue_history(issue.issue_id)
                ]
        return summary


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value
