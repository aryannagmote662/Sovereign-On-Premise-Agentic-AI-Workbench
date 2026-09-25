"""
Centralized Attribute-Based Access Control (ABAC) Policy Engine for MRPL AI Workbench.
Enforces multi-attribute evaluation across user identity, workspace boundary, clearance level (1-5), and air-gap posture.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.auth.models import User, UserRole
from src.auth.roles import get_permissions_for_role

logger = logging.getLogger(__name__)


@dataclass
class ResourceAttributes:
    """Attributes associated with a protected resource for ABAC decision making."""
    resource_id: str
    resource_type: str = "DOCUMENT"
    workspace_id: str = "DEFAULT"
    classification_level: int = 1
    owner: str = ""
    sensitivity: str = "INTERNAL"


@dataclass
class AuthorizationDecision:
    """Result of an ABAC evaluation."""
    allowed: bool
    reason: str
    decision_code: str


class ABACPolicyEngine:
    """
    Central Policy Engine evaluating RBAC permissions + ABAC rules:
    - User Status: ACTIVE
    - Role Permission: Role has required permission action
    - Workspace Isolation: user.workspace_id == resource.workspace_id
    - Clearance Level: user.clearance_level >= resource.classification_level
    - Air-Gap Posture: Offline posture validated
    """

    def __init__(self, offline_guard: Optional[Any] = None) -> None:
        self._offline_guard = offline_guard

    @property
    def offline_guard(self) -> Any:
        if self._offline_guard is None:
            from src.security.offline_guard import OfflineGuard
            self._offline_guard = OfflineGuard()
        return self._offline_guard


    def evaluate(
        self,
        user: User,
        action: str,
        resource: Optional[ResourceAttributes] = None,
    ) -> AuthorizationDecision:
        """
        Evaluate full RBAC + ABAC authorization policy.
        """
        # 1. User Status Rule
        if not user.is_active or user.status != "ACTIVE":
            logger.warning(f"[ABAC DENY] User '{user.email}' status is '{user.status}' (active={user.is_active})")
            return AuthorizationDecision(
                allowed=False,
                reason="Access denied: User account is inactive or pending administrator approval.",
                decision_code="DENY_INACTIVE",
            )

        # 2. RBAC Permission Rule
        if not user.has_permission(action):
            logger.warning(f"[ABAC DENY] User '{user.email}' (Role: {user.role}) lacks permission '{action}'")
            return AuthorizationDecision(
                allowed=False,
                reason=f"Access denied: Role '{user.role}' lacks permission '{action}'.",
                decision_code="DENY_NO_PERMISSION",
            )

        # 3. Resource ABAC Rules (Workspace & Clearance Level)
        if resource:
            # Workspace Isolation Rule
            # Note: AI_IT_ADMIN and AUDITOR_DOC_CONTROLLER can inspect cross-workspace resources if authorized
            admin_roles = {UserRole.AI_IT_ADMIN, UserRole.AUDITOR_DOC_CONTROLLER}
            if user.role not in admin_roles:
                user_ws = (user.workspace_id or "").upper().strip()
                res_ws = (resource.workspace_id or "").upper().strip()
                if res_ws and res_ws != "ALL" and user_ws != res_ws:
                    logger.warning(f"[ABAC DENY] Workspace Mismatch: User '{user.email}' ({user_ws}) vs Resource ({res_ws})")
                    return AuthorizationDecision(
                        allowed=False,
                        reason="Access denied: Resource belongs to a different workspace boundary.",
                        decision_code="DENY_WORKSPACE_MISMATCH",
                    )

            # Clearance Level Rule (1 to 5)
            if user.clearance_level < resource.classification_level:
                logger.warning(
                    f"[ABAC DENY] Insufficient Clearance: User '{user.email}' (Level {user.clearance_level}) "
                    f"vs Resource Classification (Level {resource.classification_level})"
                )
                return AuthorizationDecision(
                    allowed=False,
                    reason="Access denied: Insufficient security clearance level for this classified resource.",
                    decision_code="DENY_INSUFFICIENT_CLEARANCE",
                )

        # 4. Air-Gap Policy Rule
        if not self.offline_guard.is_offline_enforced():
            logger.error(f"[ABAC DENY] Air-gap posture violation detected for user '{user.email}'")
            return AuthorizationDecision(
                allowed=False,
                reason="Access denied: Sovereign air-gap security policy violation.",
                decision_code="DENY_AIRGAP_VIOLATION",
            )

        return AuthorizationDecision(
            allowed=True,
            reason="Authorization granted.",
            decision_code="ALLOW",
        )


# Global Policy Engine Singleton Instance
abac_engine = ABACPolicyEngine()
