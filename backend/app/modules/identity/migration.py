"""Stable public imports for the legacy identity migration workflow."""

from app.modules.identity.migration_planner import LegacyIdentityPlanner
from app.modules.identity.migration_service import IdentityMigrationService
from app.modules.identity.migration_types import (
    IdentityMigrationPlan,
    IdentityMigrationResult,
    InvalidIdentityMigrationPlanError,
    LegacyIdentityRecord,
    TargetIdentityNotEmptyError,
)

__all__ = [
    "IdentityMigrationPlan",
    "IdentityMigrationResult",
    "IdentityMigrationService",
    "InvalidIdentityMigrationPlanError",
    "LegacyIdentityPlanner",
    "LegacyIdentityRecord",
    "TargetIdentityNotEmptyError",
]
