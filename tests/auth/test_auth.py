"""
Unit & Integration Tests for Authentication & RBAC Authorization Subsystem.
"""

import pytest
from fastapi.testclient import TestClient

from config.settings import settings
from src.api.app import app
from src.auth.models import User, UserRole
from src.auth.roles import PERMISSION_OPERATOR_READ, PERMISSION_SYSTEM_ADMIN
from src.auth.security import constant_time_compare, hash_password
from src.auth.service import AuthService


@pytest.fixture
def auth_service():
    return AuthService()


@pytest.fixture
def client():
    return TestClient(app)


def test_password_hashing_and_constant_time_compare():
    h1 = hash_password("secret123")
    h2 = hash_password("secret123")
    h3 = hash_password("wrong123")

    assert h1 == h2
    assert constant_time_compare(h1, h2) is True
    assert constant_time_compare(h1, h3) is False


def test_auth_service_user_login(auth_service):
    # Valid login using seeded admin account
    res = auth_service.authenticate_user("admin@mrpl.local", "admin123")
    assert res is not None
    user, token = res
    assert user.email == "admin@mrpl.local"
    assert user.role == UserRole.AI_IT_ADMIN
    assert token.startswith("mrpl_tok_")

    # Validate token
    validated_user = auth_service.validate_token(token)
    assert validated_user is not None
    assert validated_user.email == "admin@mrpl.local"

    # Invalid password login
    invalid_res = auth_service.authenticate_user("admin@mrpl.local", "wrongpassword")
    assert invalid_res is None

    # Invalid email login
    nonexistent_res = auth_service.authenticate_user("nonexistent@mrpl.local", "pass")
    assert nonexistent_res is None


def test_auth_service_token_revocation(auth_service):
    res = auth_service.authenticate_user("operator@mrpl.local", "mrpl123")
    assert res is not None
    _, token = res

    assert auth_service.validate_token(token) is not None
    revoked = auth_service.logout_user(token)
    assert revoked is True
    assert auth_service.validate_token(token) is None


def test_rbac_permissions():
    admin = User(user_id="1", full_name="Admin", email="admin@mrpl.local", role=UserRole.AI_IT_ADMIN)
    operator = User(
        user_id="2",
        full_name="Operator",
        email="operator@mrpl.local",
        role=UserRole.PLANT_OPERATOR,
        permissions=[PERMISSION_OPERATOR_READ],
    )
    user = User(user_id="3", full_name="Operator 2", email="op2@mrpl.local", role=UserRole.PLANT_OPERATOR, permissions=[])

    assert admin.has_permission(PERMISSION_SYSTEM_ADMIN) is True
    assert operator.has_permission(PERMISSION_OPERATOR_READ) is True
    assert operator.has_permission(PERMISSION_SYSTEM_ADMIN) is False
    assert user.has_permission(PERMISSION_OPERATOR_READ) is False


def test_api_auth_login_and_me_endpoints(client):
    # 1. Login Endpoint
    login_res = client.post("/auth/login", json={"username": "operator@mrpl.local", "password": "mrpl123"})
    assert login_res.status_code == 200
    data = login_res.json()["data"]
    assert data["role"] == "PLANT_OPERATOR"
    token = data["access_token"]

    # 2. Get /auth/me with valid Bearer Token
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == "operator@mrpl.local"

    # 3. Missing Token -> 401
    unauth_res = client.get("/auth/me")
    assert unauth_res.status_code == 401

    # 4. Invalid/Malformed Token -> 401
    invalid_res = client.get("/auth/me", headers={"Authorization": "Bearer invalid_token_xyz"})
    assert invalid_res.status_code == 401


def test_rbac_authorization_endpoint_restrictions(client):
    from src.security.request_security import get_security_service
    get_security_service().rate_limiter.reset()

    # Operator user login
    res_operator = client.post("/auth/login", json={"username": "operator@mrpl.local", "password": "mrpl123"})
    operator_token = res_operator.json()["data"]["access_token"]

    # Operator accessing /auth/users without admin role -> 403 Forbidden
    forbidden_res = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert forbidden_res.status_code == 403

    # Admin user login
    res_admin = client.post("/auth/login", json={"username": "admin@mrpl.local", "password": "admin123"})
    admin_token = res_admin.json()["data"]["access_token"]

    # Admin accessing /auth/users -> 200 OK
    allowed_res = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed_res.status_code == 200

