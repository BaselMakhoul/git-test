from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class OperationType(str, Enum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    RENAME = "rename"
    ANNOTATE = "annotate"


class IssueCategory(str, Enum):
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    POLICY = "policy"
    CONSISTENCY = "consistency"
    OTHER = "other"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowState(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ReviewerDecisionType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


class ValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class RuleType(str, Enum):
    SHACL = "shacl"
    STRUCTURAL = "structural"
    SCHEMA = "schema"
    CUSTOM = "custom"


class AIArtifactType(str, Enum):
    EXPLANATION = "explanation"
    SUGGESTION = "suggestion"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware and in UTC")
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class OntologyChange:
    change_id: str
    contributor_id: str
    timestamp: datetime
    target_ontology_fragment: str
    affected_entity: str
    operation_type: OperationType
    proposed_values: Dict[str, Any]
    optional_note: Optional[str] = None
    scenario_id: Optional[str] = None
    revision_reference: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _normalize_utc(self.timestamp, "timestamp"))
        if not isinstance(self.operation_type, OperationType):
            raise ValueError("operation_type must be a valid OperationType")
        if not self.change_id.strip():
            raise ValueError("change_id is required")
        if not self.contributor_id.strip():
            raise ValueError("contributor_id is required")
        if not self.target_ontology_fragment.strip():
            raise ValueError("target_ontology_fragment is required")
        if not self.affected_entity.strip():
            raise ValueError("affected_entity is required")
        if not isinstance(self.proposed_values, dict):
            raise ValueError("proposed_values must be a dictionary")


@dataclass(frozen=True)
class ValidationResult:
    validation_result_id: str
    change_id: str
    rule_id: str
    rule_type: RuleType
    status: ValidationStatus
    target_node: str
    affected_property_path: str
    machine_readable_message: str
    user_readable_message: str
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", _normalize_utc(self.created_at, "created_at"))
        if not isinstance(self.rule_type, RuleType):
            raise ValueError("rule_type must be a valid RuleType")
        if not isinstance(self.status, ValidationStatus):
            raise ValueError("status must be a valid ValidationStatus")
        if not self.validation_result_id.strip():
            raise ValueError("validation_result_id is required")
        if not self.change_id.strip():
            raise ValueError("change_id is required")
        if not self.rule_id.strip():
            raise ValueError("rule_id is required")


@dataclass(frozen=True)
class ReviewDecision:
    decision_id: str
    issue_id: str
    reviewer_id: str
    decision_type: ReviewerDecisionType
    rationale: str
    decided_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decided_at", _normalize_utc(self.decided_at, "decided_at"))
        if not isinstance(self.decision_type, ReviewerDecisionType):
            raise ValueError("decision_type must be a valid ReviewerDecisionType")
        if not self.decision_id.strip():
            raise ValueError("decision_id is required")
        if not self.issue_id.strip():
            raise ValueError("issue_id is required")
        if not self.reviewer_id.strip():
            raise ValueError("reviewer_id is required")
        if not self.rationale.strip():
            raise ValueError("rationale is required")


@dataclass(frozen=True)
class AIExplanationArtifact:
    explanation_id: str
    explanation_type: AIArtifactType
    generated_text: str
    created_at: datetime = field(default_factory=_utc_now)
    related_issue_id: Optional[str] = None
    related_validation_result_id: Optional[str] = None
    advisory_only_note: str = "Advisory only. Cannot directly modify ontology content."

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", _normalize_utc(self.created_at, "created_at"))
        if not isinstance(self.explanation_type, AIArtifactType):
            raise ValueError("explanation_type must be a valid AIArtifactType")
        if not self.explanation_id.strip():
            raise ValueError("explanation_id is required")
        if not self.generated_text.strip():
            raise ValueError("generated_text is required")
        if not (self.related_issue_id or self.related_validation_result_id):
            raise ValueError("Artifact must reference issue_id or validation_result_id")


@dataclass
class ConflictIssue:
    issue_id: str
    originating_change_id: str
    issue_category: IssueCategory
    severity: SeverityLevel
    evidence: Dict[str, Any]
    current_workflow_state: WorkflowState
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    assigned_reviewer: Optional[str] = None
    reviewer_action: Optional[ReviewerDecisionType] = None
    final_outcome: Optional[str] = None
    validation_result_ids: List[str] = field(default_factory=list)
    ai_explanation_artifact_ids: List[str] = field(default_factory=list)
    _initialized: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        self.created_at = _normalize_utc(self.created_at, "created_at")
        self.updated_at = _normalize_utc(self.updated_at, "updated_at")
        if not isinstance(self.issue_category, IssueCategory):
            raise ValueError("issue_category must be a valid IssueCategory")
        if not isinstance(self.severity, SeverityLevel):
            raise ValueError("severity must be a valid SeverityLevel")
        if not isinstance(self.current_workflow_state, WorkflowState):
            raise ValueError("current_workflow_state must be a valid WorkflowState")
        if self.reviewer_action is not None and not isinstance(self.reviewer_action, ReviewerDecisionType):
            raise ValueError("reviewer_action must be a valid ReviewerDecisionType when provided")
        if not self.issue_id.strip():
            raise ValueError("issue_id is required")
        if not self.originating_change_id.strip():
            raise ValueError("originating_change_id is required")
        if not isinstance(self.evidence, dict):
            raise ValueError("evidence must be a dictionary")
        self._initialized = True

    def __setattr__(self, key: str, value: Any) -> None:
        if getattr(self, "_initialized", False) and key in {"issue_id", "originating_change_id"}:
            raise AttributeError(f"{key} is immutable after creation")
        super().__setattr__(key, value)
