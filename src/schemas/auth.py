"""
Authentication & Authorization API Pydantic Schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for POST /auth/register."""

    full_name: str = Field(..., description="User full name", min_length=2)
    email: str = Field(..., description="Valid corporate email address")
    password: str = Field(..., description="Secret credential password", min_length=6)
    department: str = Field(default="Operations", description="Refinery department")
    requested_role: str = Field(default="PLANT_OPERATOR", description="Requested initial role")


class LoginRequest(BaseModel):
    """Payload for POST /auth/login."""

    username: str = Field(..., description="Email address or username handle", min_length=1)
    password: str = Field(..., description="User secret credential", min_length=1)


class TokenResponse(BaseModel):
    """Token response model for POST /auth/login."""

    access_token: str = Field(..., description="Bearer access token string")
    token_type: str = Field(default="bearer", description="Token type identifier")
    expires_in: int = Field(..., description="Token expiration duration in seconds")
    user_id: str = Field(..., description="Authenticated user ID")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    role: str = Field(..., description="Assigned authorization role")
    department: str = Field(..., description="User department")
    workspace_id: str = Field(..., description="Assigned workspace boundary")
    clearance_level: int = Field(..., description="User security clearance level (1-5)")
    status: str = Field(..., description="User account status")
    permissions: List[str] = Field(default_factory=list, description="Granted permissions list")


class UserResponse(BaseModel):
    """Authenticated user info response model for GET /auth/me and admin user management."""

    user_id: str = Field(..., description="Unique user identifier")
    full_name: str = Field(..., description="User full name")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User assigned role")
    department: str = Field(..., description="User department")
    workspace_id: str = Field(..., description="Assigned workspace boundary")
    clearance_level: int = Field(..., description="User security clearance level (1-5)")
    status: str = Field(..., description="Account status (PENDING, ACTIVE, DISABLED)")
    permissions: List[str] = Field(default_factory=list, description="List of authorized permissions")
    active: bool = Field(default=True, description="Account active status")


class AdminUserUpdateRequest(BaseModel):
    """Payload for admin updating user account role, workspace, clearance, or status."""

    user_id: str = Field(..., description="Target user ID")
    role: Optional[str] = Field(None, description="Updated role code")
    workspace_id: Optional[str] = Field(None, description="Updated workspace boundary ID")
    clearance_level: Optional[int] = Field(None, description="Updated clearance level (1-5)", ge=1, le=5)
    status: Optional[str] = Field(None, description="Updated status: PENDING, ACTIVE, DISABLED")
