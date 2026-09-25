"""
Authentication & User Management API Router.
Handles user registration, authentication login/logout, user profile retrieval,
and admin user management workflows.
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.responses.standard_response import StandardResponse, success_response
from src.auth.models import User, UserRole
from src.auth.service import AuthService
from src.schemas.auth import (
    AdminUserUpdateRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.security.authorization_gate import (
    get_auth_service,
    get_current_user,
    require_permission,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


@router.post("/register", response_model=StandardResponse[UserResponse])
async def register(
    req: RegisterRequest,
    auth_svc: AuthService = Depends(get_auth_service),
):
    """
    Register a new platform user account. Status defaults to PENDING for admin approval.
    """
    try:
        db_user = auth_svc.register_user(
            full_name=req.full_name,
            email=req.email,
            password=req.password,
            department=req.department,
            requested_role=req.requested_role,
        )

        resp = UserResponse(
            user_id=db_user.id,
            full_name=db_user.full_name,
            email=db_user.email,
            role=db_user.role,
            department=db_user.department,
            workspace_id=db_user.workspace_id,
            clearance_level=db_user.clearance_level,
            status=db_user.status,
            permissions=[],
            active=False,
        )

        return success_response(
            data=resp,
            message=f"Registration submitted successfully for '{db_user.email}'. Account is PENDING administrator approval.",
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {exc}")


@router.post("/login", response_model=StandardResponse[TokenResponse])
async def login(
    req: LoginRequest,
    auth_svc: AuthService = Depends(get_auth_service),
):
    """
    Authenticate user credentials and issue session access token if status is ACTIVE.
    """
    auth_result = auth_svc.authenticate_user(req.username, req.password)
    if not auth_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password, or account is pending administrator approval.",
        )

    user, token = auth_result
    token_resp = TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=auth_svc.token_expiry,
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department=user.department,
        workspace_id=user.workspace_id,
        clearance_level=user.clearance_level,
        status=user.status,
        permissions=user.permissions,
    )
    return success_response(data=token_resp, message="Login successful")


@router.get("/me", response_model=StandardResponse[UserResponse])
async def get_me(user: User = Depends(get_current_user)):
    """
    Retrieve profile and active permissions for current authenticated user identity.
    """
    resp = UserResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.value,
        department=user.department,
        workspace_id=user.workspace_id,
        clearance_level=user.clearance_level,
        status=user.status,
        permissions=user.permissions,
        active=user.is_active,
    )
    return success_response(data=resp, message="User profile retrieved")


@router.post("/logout", response_model=StandardResponse[dict])
async def logout(
    request: Request,
    auth_svc: AuthService = Depends(get_auth_service),
):
    """
    Invalidate active Bearer session token.
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else None
    if token:
        auth_svc.logout_user(token)

    return success_response(
        data={"revoked": True},
        message="Session logged out successfully",
    )


@router.get("/users", response_model=StandardResponse[List[UserResponse]])
async def list_users(
    user: User = Depends(get_current_user),
    auth_svc: AuthService = Depends(get_auth_service),
):
    """
    Admin endpoint: List all registered platform user accounts.
    """
    if user.role not in {UserRole.AI_IT_ADMIN, UserRole.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for this resource.")

    users = auth_svc.list_all_users()
    user_responses = [
        UserResponse(
            user_id=u.id,
            full_name=u.full_name,
            email=u.email,
            role=u.role,
            department=u.department,
            workspace_id=u.workspace_id,
            clearance_level=u.clearance_level,
            status=u.status,
            permissions=[],
            active=(u.status == "ACTIVE"),
        )
        for u in users
    ]
    return success_response(data=user_responses, message="User catalog retrieved successfully")


@router.post("/users/update", response_model=StandardResponse[UserResponse])
async def update_user_account(
    req: AdminUserUpdateRequest,
    user: User = Depends(get_current_user),
    auth_svc: AuthService = Depends(get_auth_service),
):
    """
    Admin endpoint: Approve pending account, change role, workspace, clearance level (1-5), or status.
    """
    try:
        updated = auth_svc.update_user_status_or_role(
            admin_user=user,
            target_user_id=req.user_id,
            new_role=req.role,
            new_workspace_id=req.workspace_id,
            new_clearance_level=req.clearance_level,
            new_status=req.status,
        )

        resp = UserResponse(
            user_id=updated.id,
            full_name=updated.full_name,
            email=updated.email,
            role=updated.role,
            department=updated.department,
            workspace_id=updated.workspace_id,
            clearance_level=updated.clearance_level,
            status=updated.status,
            permissions=[],
            active=(updated.status == "ACTIVE"),
        )
        return success_response(data=resp, message=f"User account '{updated.email}' updated successfully.")
    except PermissionError as perm_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(perm_err))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
