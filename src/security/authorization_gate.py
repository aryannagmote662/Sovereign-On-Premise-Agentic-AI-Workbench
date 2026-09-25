"""
Centralized FastAPI Authorization Gate & Security Dependencies.
Extracts authenticated user context and enforces RBAC/ABAC authorization rules.
"""

from typing import Annotated, Callable, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.models import User
from src.auth.service import AuthService
from src.security.abac.policy_engine import ResourceAttributes, abac_engine

# HTTP Bearer Security Scheme (Optional=True to allow custom header / cookie fallback)
security_scheme = HTTPBearer(auto_error=False)

# Singleton AuthService provider
_auth_service_instance: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service_instance
    if _auth_service_instance is None:
        _auth_service_instance = AuthService()
    return _auth_service_instance


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    FastAPI dependency extracting and validating authenticated User identity.
    Checks HTTP Bearer token or X-Auth-Token header.
    """
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif x_auth_token:
        token = x_auth_token

    user = auth_service.validate_token(token or "")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing or invalid. Please login.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for this resource.",
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    FastAPI dependency extracting User identity. If unauthenticated or token missing/invalid,
    falls back to default System Administrator account for seamless local workbench interaction.
    """
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif x_auth_token:
        token = x_auth_token

    user = auth_service.validate_token(token or "")
    if user and user.is_active and user.status == "ACTIVE":
        return user

    # Fallback to default seeded admin account
    admin_rec = auth_service.user_repo.get_user_by_email("admin@mrpl.local")
    if admin_rec:
        return auth_service._record_to_domain_user(admin_rec)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication token missing or invalid. Please login.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_permission(permission: str) -> Callable:
    """
    Factory dependency requiring specific RBAC permission.
    """
    async def permission_dependency(user: User = Depends(get_current_user)) -> User:
        decision = abac_engine.evaluate(user=user, action=permission)
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this resource.",
            )
        return user

    return permission_dependency


def authorize_action(
    action: str,
    resource_type: str = "document",
    workspace_id: Optional[str] = None,
    classification_level: int = 1,
) -> Callable:
    """
    Factory dependency requiring full ABAC resource authorization evaluation.
    """
    async def abac_dependency(user: User = Depends(get_current_user)) -> User:
        target_ws = workspace_id or user.workspace_id
        res_attrs = ResourceAttributes(
            resource_id="req_resource",
            resource_type=resource_type,
            workspace_id=target_ws,
            classification_level=classification_level,
        )
        decision = abac_engine.evaluate(user=user, action=action, resource=res_attrs)
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this resource.",
            )
        return user

    return abac_dependency
