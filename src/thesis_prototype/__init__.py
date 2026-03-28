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
from .governance_service import GovernanceReviewService, ReviewCase, ReviewHistoryEvent, ReviewWorkflowState
from .auth_service import AuthService, User
from .permissions import Role, ROLE_PERMISSIONS
from .demo_backend import DemoBackend
from .registry import InMemoryIssueRegistry, IssueHistoryEvent

__all__ = [
    "ConflictDetectionService",
    "ConflictDetectorConfig",
    "ValidationService",
    "ValidationConfig",
    "ValidationRuleDefinition",
    "ValidationAdapter",
    "LightweightValidationAdapter",
    "DemoBackend",
    "GovernanceReviewService",
    "ReviewCase",
    "ReviewHistoryEvent",
    "ReviewWorkflowState",
    "AuthService",
    "User",
    "Role",
    "ROLE_PERMISSIONS",
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
