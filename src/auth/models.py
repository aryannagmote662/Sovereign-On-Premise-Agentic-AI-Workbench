"""
Authentication & Authorization Domain Dataclasses.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class UserRole(str, Enum):
    """Exact 6 Platform Application Roles."""

    PLANT_OPERATOR = "PLANT_OPERATOR"
    ENGINEER = "ENGINEER"
    SHIFT_SUPERVISOR = "SHIFT_SUPERVISOR"
    PLANT_MANAGER = "PLANT_MANAGER"
    AI_IT_ADMIN = "AI_IT_ADMIN"
    AUDITOR_DOC_CONTROLLER = "AUDITOR_DOC_CONTROLLER"

    # Backward compatibility aliases
    ADMIN = "AI_IT_ADMIN"
    OPERATOR = "PLANT_OPERATOR"
    ANALYST = "ENGINEER"
    VIEWER = "PLANT_OPERATOR"
    USER = "PLANT_OPERATOR"


@dataclass
class User:
    """Dataclass representing an authenticated platform user identity."""

    user_id: str
    full_name: str
    email: str
    role: UserRole
    department: str = "Operations"
    position: Optional[str] = None
    workspace_id: str = "Operations"
    clearance_level: int = 1
    status: str = "ACTIVE"
    permissions: Optional[List[str]] = None
    password_hash: Optional[str] = None
    is_active: bool = True

    def __post_init__(self):
        if self.permissions is None:
            if self.role:
                try:
                    from src.auth.roles import get_permissions_for_role
                    self.permissions = get_permissions_for_role(self.role)
                except Exception:
                    self.permissions = []
            else:
                self.permissions = []

    def get_effective_position(self) -> str:
        """Return explicit position or infer position from department/role."""
        if self.position:
            return self.position
        if self.department:
            return self.department
        if self.role in {UserRole.PLANT_OPERATOR, UserRole.OPERATOR}:
            return "Console Operator"
        return "Engineer"

    @property
    def username(self) -> str:
        """Alias username to email or full_name for backward compatibility."""
        return self.email or self.user_id

    def has_permission(self, permission: str) -> bool:
        """Check if user possesses specified permission."""
        if self.role in {UserRole.AI_IT_ADMIN, UserRole.ADMIN}:
            return True
        return permission in self.permissions
