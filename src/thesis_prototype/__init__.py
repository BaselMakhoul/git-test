"""Foundational data model and issue registry for thesis prototype (Step 1)."""

from .models import (
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
from .conflict_detection import ConflictDetectionService, ConflictDetectorConfig
from .validation_service import (
    LightweightValidationAdapter,
    ValidationAdapter,
    ValidationConfig,
    ValidationRuleDefinition,
    ValidationService,
)
from .registry import InMemoryIssueRegistry, IssueHistoryEvent

__all__ = [
    "ConflictDetectionService",
    "ConflictDetectorConfig",
    "ValidationService",
    "ValidationConfig",
    "ValidationRuleDefinition",
    "ValidationAdapter",
    "LightweightValidationAdapter",
    "AIArtifactType",
    "AIExplanationArtifact",
    "ConflictIssue",
    "InMemoryIssueRegistry",
    "IssueCategory",
    "IssueHistoryEvent",
    "OntologyChange",
    "OperationType",
    "ReviewDecision",
    "ReviewerDecisionType",
    "RuleType",
    "SeverityLevel",
    "ValidationResult",
    "ValidationStatus",
    "WorkflowState",
]
