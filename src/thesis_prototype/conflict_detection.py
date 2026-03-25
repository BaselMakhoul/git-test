from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Set

from .models import (
    ConflictIssue,
    IssueCategory,
    OntologyChange,
    OperationType,
    SeverityLevel,
    WorkflowState,
)
from .registry import InMemoryIssueRegistry


@dataclass(frozen=True)
class ConflictDetectorConfig:
    near_duplicate_threshold: float = 0.88
    trim_whitespace: bool = True
    lowercase: bool = True
    collapse_repeated_spaces: bool = True
    overlap_active_window_minutes: int = 120
    overlap_sensitive_operation_types: Set[OperationType] = field(
        default_factory=lambda: {OperationType.ADD, OperationType.UPDATE, OperationType.RENAME}
    )
    overlap_sensitive_fields: Set[str] = field(default_factory=lambda: {"label", "definition", "comment"})


class ConflictDetectionService:
    """Lightweight, deterministic conflict detector for thesis Step 2."""

    def __init__(self, registry: InMemoryIssueRegistry, config: Optional[ConflictDetectorConfig] = None) -> None:
        self.registry = registry
        self.config = config or ConflictDetectorConfig()

    def normalize_label(self, raw_label: str) -> str:
        normalized = raw_label
        if self.config.trim_whitespace:
            normalized = normalized.strip()
        if self.config.lowercase:
            normalized = normalized.lower()
        if self.config.collapse_repeated_spaces:
            normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def label_similarity(self, left_label: str, right_label: str) -> float:
        return SequenceMatcher(None, self.normalize_label(left_label), self.normalize_label(right_label)).ratio()

    def detect_direct_duplicates(self, change: OntologyChange) -> List[ConflictIssue]:
        proposed_label = self._get_label(change)
        if not proposed_label:
            return []

        normalized_target = self.normalize_label(proposed_label)
        issues: List[ConflictIssue] = []

        for existing_change in self._candidate_changes(change):
            existing_label = self._get_label(existing_change)
            if not existing_label:
                continue
            if normalized_target != self.normalize_label(existing_label):
                continue

            evidence = {
                "detector": "direct_duplicate",
                "fingerprint": self._fingerprint(change.change_id, existing_change.change_id, "direct_duplicate"),
                "matched_change_id": existing_change.change_id,
                "matched_entity": existing_change.affected_entity,
                "proposed_label": proposed_label,
                "matched_label": existing_label,
                "normalized_label": normalized_target,
                "similarity_score": 1.0,
                "machine_code": "DIRECT_DUPLICATE_LABEL",
                "user_readable_description": (
                    f"Proposed label '{proposed_label}' exactly matches existing label on change "
                    f"'{existing_change.change_id}' after normalization."
                ),
            }
            created_issue = self._create_issue_if_new(
                change,
                IssueCategory.DUPLICATE,
                SeverityLevel.HIGH,
                evidence,
            )
            if created_issue:
                issues.append(created_issue)

        return issues

    def detect_near_duplicates(self, change: OntologyChange) -> List[ConflictIssue]:
        proposed_label = self._get_label(change)
        if not proposed_label:
            return []

        issues: List[ConflictIssue] = []
        for existing_change in self._candidate_changes(change):
            existing_label = self._get_label(existing_change)
            if not existing_label:
                continue

            score = self.label_similarity(proposed_label, existing_label)
            if score < self.config.near_duplicate_threshold or score >= 1.0:
                continue

            evidence = {
                "detector": "near_duplicate",
                "fingerprint": self._fingerprint(change.change_id, existing_change.change_id, "near_duplicate"),
                "matched_change_id": existing_change.change_id,
                "matched_entity": existing_change.affected_entity,
                "proposed_label": proposed_label,
                "matched_label": existing_label,
                "normalized_proposed": self.normalize_label(proposed_label),
                "normalized_matched": self.normalize_label(existing_label),
                "similarity_score": round(score, 4),
                "threshold": self.config.near_duplicate_threshold,
                "machine_code": "NEAR_DUPLICATE_LABEL",
                "user_readable_description": (
                    f"Proposed label '{proposed_label}' is highly similar to label '{existing_label}' "
                    f"(score={score:.3f})."
                ),
            }
            created_issue = self._create_issue_if_new(
                change,
                IssueCategory.DUPLICATE,
                SeverityLevel.MEDIUM,
                evidence,
            )
            if created_issue:
                issues.append(created_issue)

        return issues

    def detect_overlap_conflicts(self, change: OntologyChange) -> List[ConflictIssue]:
        if change.operation_type not in self.config.overlap_sensitive_operation_types:
            return []

        issues: List[ConflictIssue] = []
        change_fields = set(change.proposed_values.keys())

        for existing_change in self._candidate_changes(change):
            if existing_change.affected_entity != change.affected_entity:
                continue
            if existing_change.operation_type not in self.config.overlap_sensitive_operation_types:
                continue

            shared_sensitive_fields = (
                set(existing_change.proposed_values.keys())
                .intersection(change_fields)
                .intersection(self.config.overlap_sensitive_fields)
            )
            if not shared_sensitive_fields:
                continue

            has_unresolved_context = self._has_unresolved_issue(existing_change.change_id)
            within_window = self._is_within_active_window(change, existing_change)
            if not (has_unresolved_context or within_window):
                continue

            severity = SeverityLevel.HIGH if has_unresolved_context else SeverityLevel.MEDIUM
            evidence = {
                "detector": "overlap_conflict",
                "fingerprint": self._fingerprint(change.change_id, existing_change.change_id, "overlap_conflict"),
                "matched_change_id": existing_change.change_id,
                "affected_entity": change.affected_entity,
                "shared_sensitive_fields": sorted(shared_sensitive_fields),
                "within_active_window": within_window,
                "has_unresolved_context": has_unresolved_context,
                "active_window_minutes": self.config.overlap_active_window_minutes,
                "machine_code": "OVERLAPPING_CONCURRENT_CHANGE",
                "user_readable_description": (
                    f"Change overlaps with existing active/unresolved change '{existing_change.change_id}' "
                    f"on entity '{change.affected_entity}' and fields {sorted(shared_sensitive_fields)}."
                ),
            }
            created_issue = self._create_issue_if_new(
                change,
                IssueCategory.CONFLICT,
                severity,
                evidence,
            )
            if created_issue:
                issues.append(created_issue)

        return issues

    def detect_all(self, change: OntologyChange) -> List[ConflictIssue]:
        issues: List[ConflictIssue] = []
        issues.extend(self.detect_direct_duplicates(change))
        issues.extend(self.detect_near_duplicates(change))
        issues.extend(self.detect_overlap_conflicts(change))
        return issues

    def _candidate_changes(self, change: OntologyChange) -> Iterable[OntologyChange]:
        return sorted(
            [c for c in self.registry.list_changes() if c.change_id != change.change_id],
            key=lambda c: (c.timestamp, c.change_id),
        )

    @staticmethod
    def _get_label(change: OntologyChange) -> Optional[str]:
        label = change.proposed_values.get("label")
        return str(label) if isinstance(label, str) else None

    def _has_unresolved_issue(self, change_id: str) -> bool:
        for issue in self.registry.get_issues_for_change(change_id):
            if issue.current_workflow_state != WorkflowState.CLOSED:
                return True
        return False

    def _is_within_active_window(self, source: OntologyChange, target: OntologyChange) -> bool:
        delta_seconds = abs((source.timestamp - target.timestamp).total_seconds())
        return delta_seconds <= self.config.overlap_active_window_minutes * 60

    def _create_issue_if_new(
        self,
        change: OntologyChange,
        issue_category: IssueCategory,
        severity: SeverityLevel,
        evidence: Dict[str, object],
    ) -> Optional[ConflictIssue]:
        fingerprint = str(evidence["fingerprint"])
        existing = self.registry.get_issues_for_change(change.change_id)
        for issue in existing:
            if issue.issue_category == issue_category and str(issue.evidence.get("fingerprint")) == fingerprint:
                return None

        issue_id = f"iss-{fingerprint[:12]}"
        issue = ConflictIssue(
            issue_id=issue_id,
            originating_change_id=change.change_id,
            issue_category=issue_category,
            severity=severity,
            evidence=evidence,
            current_workflow_state=WorkflowState.OPEN,
        )
        self.registry.create_issue(issue)
        return issue

    @staticmethod
    def _fingerprint(change_id: str, matched_change_id: str, detector_name: str) -> str:
        payload = {"change_id": change_id, "matched_change_id": matched_change_id, "detector": detector_name}
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha1(encoded).hexdigest()
