"""
Authentication & User Management Service for MRPL AI Workbench.
Handles user registration, admin approvals, SQLite credential persistence,
session token management, 6-role permission resolution, and dev seed accounts.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from config.settings import settings
from src.audit.hash_ledger import AuditLedger
from src.auth.models import User, UserRole
from src.auth.roles import get_permissions_for_role
from src.auth.security import constant_time_compare, hash_password
from src.persistence.models import DBSession, DBUser
from src.persistence.repositories import (
    RoleRepository,
    SessionRepository,
    UserRepository,
)

logger = logging.getLogger("MRPL.Auth.Service")


class AuthService:
    """
    Local-first authentication, user registration, and session token management service.
    Persists state in SQLite `workbench.db` and logs audit events to SHA-256 ledger.
    """

    def __init__(
        self,
        user_repo: Optional[UserRepository] = None,
        role_repo: Optional[RoleRepository] = None,
        session_repo: Optional[SessionRepository] = None,
        audit_ledger: Optional[AuditLedger] = None,
    ) -> None:
        self.enabled = settings.AUTH_ENABLED
        self.default_token = settings.AUTH_TOKEN
        self.token_expiry = settings.AUTH_TOKEN_EXPIRY_SECONDS

        self.user_repo = user_repo or UserRepository()
        self.role_repo = role_repo or RoleRepository()
        self.session_repo = session_repo or SessionRepository()
        self.audit_ledger = audit_ledger or AuditLedger()

        # Seed roles & development test accounts on startup
        self._seed_database_if_empty()

    def _seed_database_if_empty(self) -> None:
        """Seed default roles and 6 development test accounts if database is empty."""
        try:
            self.role_repo.seed_default_roles()
            
            # Seed dev accounts with specific engineering positions
            dev_accounts = [
                ("usr_admin_001", "System Administrator", "admin@mrpl.local", "admin123", UserRole.AI_IT_ADMIN.value, "IT-OT", "AI/IT Administrator", "IT-OT", 5, "ACTIVE"),
                ("usr_op_001", "Plant Operator 1", "operator@mrpl.local", "mrpl123", UserRole.PLANT_OPERATOR.value, "Operations", "Console Operator", "Operations", 1, "ACTIVE"),
                ("usr_eng_001", "Process Engineer", "engineer@mrpl.local", "mrpl123", UserRole.ENGINEER.value, "Process Engineering", "Process Engineer", "Engineering", 3, "ACTIVE"),
                ("usr_rel_001", "Reliability Engineer", "reliability_engineer@mrpl.local", "mrpl123", UserRole.ENGINEER.value, "Reliability / Maintenance", "Reliability Engineer", "Engineering", 3, "ACTIVE"),
                ("usr_proc_001", "Process Engineer 2", "process_engineer@mrpl.local", "mrpl123", UserRole.ENGINEER.value, "Process Engineering", "Process Engineer", "Engineering", 3, "ACTIVE"),
                ("usr_mech_001", "Mechanical Engineer", "mechanical_engineer@mrpl.local", "mrpl123", UserRole.ENGINEER.value, "Mechanical", "Mechanical Engineer", "Engineering", 3, "ACTIVE"),
                ("usr_inst_001", "Instrumentation Engineer", "instrumentation_engineer@mrpl.local", "mrpl123", UserRole.ENGINEER.value, "Instrumentation", "Instrumentation Engineer", "Engineering", 3, "ACTIVE"),
                ("usr_hse_001", "HSE Engineer", "hse_engineer@mrpl.local", "mrpl123", UserRole.ENGINEER.value, "HSE", "HSE Engineer", "Safety", 3, "ACTIVE"),
                ("usr_insp_001", "Inspection Engineer", "inspection_engineer@mrpl.local", "mrpl123", UserRole.ENGINEER.value, "Inspection", "Inspection Engineer", "Inspection", 3, "ACTIVE"),
                ("usr_sup_001", "Shift Supervisor 1", "supervisor@mrpl.local", "mrpl123", UserRole.SHIFT_SUPERVISOR.value, "Operations", "Shift Supervisor", "Operations", 3, "ACTIVE"),
                ("usr_mgr_001", "Plant Manager", "manager@mrpl.local", "mrpl123", UserRole.PLANT_MANAGER.value, "Management", "Plant Manager", "Management", 4, "ACTIVE"),
                ("usr_aud_001", "Document Auditor", "auditor@mrpl.local", "mrpl123", UserRole.AUDITOR_DOC_CONTROLLER.value, "Audit", "Document Auditor", "Audit", 5, "ACTIVE"),
            ]

            now_iso = datetime.now(timezone.utc).isoformat()
            for uid, name, email, pwd, role_code, dept, pos, ws, clearance, status in dev_accounts:
                existing = self.user_repo.get_user_by_email(email)
                if not existing:
                    user_record = DBUser(
                        id=uid,
                        full_name=name,
                        email=email,
                        password_hash=hash_password(pwd),
                        role=role_code,
                        department=dept,
                        position=pos,
                        workspace_id=ws,
                        clearance_level=clearance,
                        status=status,
                        created_at=now_iso,
                        updated_at=now_iso,
                    )
                    self.user_repo.create_user(user_record)
                    logger.info(f"Seeded dev account: {email} ({role_code}, Position: {pos})")

        except Exception as exc:
            logger.warning(f"Database seeding check encountered error: {exc}")

    def register_user(
        self,
        full_name: str,
        email: str,
        password: str,
        department: str = "Operations",
        requested_role: str = "PLANT_OPERATOR",
    ) -> DBUser:
        """
        Register a new user account. Status defaults to PENDING for admin approval.
        """
        clean_email = email.lower().strip()
        existing = self.user_repo.get_user_by_email(clean_email)
        if existing:
            raise ValueError(f"User with email '{clean_email}' already exists.")

        # Validate role string against UserRole enum
        try:
            target_role = UserRole(requested_role)
        except ValueError:
            target_role = UserRole.PLANT_OPERATOR

        # Restrict direct registration of AI_IT_ADMIN
        assigned_role_code = target_role.value
        if target_role == UserRole.AI_IT_ADMIN:
            assigned_role_code = UserRole.ENGINEER.value

        user_id = f"usr_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Set default workspace based on role primary workspace
        role_obj = self.role_repo.get_role_by_code(assigned_role_code)
        primary_ws = role_obj.primary_workspace if role_obj else "Operations"

        user_record = DBUser(
            id=user_id,
            full_name=full_name.strip(),
            email=clean_email,
            password_hash=hash_password(password),
            role=assigned_role_code,
            department=department.strip(),
            workspace_id=primary_ws,
            clearance_level=1,  # Default clearance 1 until approved
            status="PENDING",   # Must be approved by AI_IT_ADMIN
            created_at=now_iso,
            updated_at=now_iso,
        )

        created = self.user_repo.create_user(user_record)

        # Audit Event
        self.audit_ledger.append_event(
            event_type="USER_REGISTERED",
            request_id=f"req_reg_{user_id}",
            user_id=user_id,
            workspace_id=primary_ws,
            operation="REGISTER",
            result="PENDING",
            metadata={
                "email": clean_email,
                "requested_role": assigned_role_code,
                "department": department,
            },
        )

        logger.info(f"User '{clean_email}' registered with status PENDING.")
        return created

    def authenticate_user(self, email_or_username: str, password: str) -> Optional[Tuple[User, str]]:
        """
        Verify credentials and issue session token if user status is ACTIVE.
        """
        user_rec = self.user_repo.get_user_by_email(email_or_username)
        if not user_rec or user_rec.status != "ACTIVE":
            logger.warning(f"Authentication failed: user '{email_or_username}' not found or not ACTIVE.")
            return None

        target_hash = hash_password(password)
        if not constant_time_compare(user_rec.password_hash or "", target_hash):
            logger.warning(f"Authentication failed: invalid password for user '{email_or_username}'.")
            return None

        # Issue active session token
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        token = f"mrpl_tok_{uuid.uuid4().hex}"
        now_iso = datetime.now(timezone.utc).isoformat()
        expire_at = time.time() + self.token_expiry
        expire_iso = datetime.fromtimestamp(expire_at, timezone.utc).isoformat()

        session_record = DBSession(
            session_id=session_id,
            user_id=user_rec.id,
            token=token,
            created_at=now_iso,
            expires_at=expire_iso,
            is_active=True,
        )
        self.session_repo.create_session(session_record)

        # Update last login
        user_rec.last_login = now_iso
        self.user_repo.update_user(user_rec)

        domain_user = self._record_to_domain_user(user_rec)

        # Audit Event
        self.audit_ledger.append_event(
            event_type="LOGIN",
            request_id=f"req_login_{session_id}",
            user_id=user_rec.id,
            workspace_id=user_rec.workspace_id,
            operation="LOGIN",
            result="SUCCESS",
            metadata={"email": user_rec.email, "role": user_rec.role},
        )

        return domain_user, token

    def validate_token(self, token: str) -> Optional[User]:
        """
        Validate session token and return domain User identity.
        """
        if not token:
            return None

        # Dev admin override token
        if constant_time_compare(token, self.default_token):
            admin_rec = self.user_repo.get_user_by_email("admin@mrpl.local")
            if admin_rec:
                return self._record_to_domain_user(admin_rec)

        session = self.session_repo.get_session_by_token(token)
        if session:
            if not session.is_active:
                return None

            # Check expiry
            try:
                exp_dt = datetime.fromisoformat(session.expires_at)
                if datetime.now(timezone.utc) > exp_dt:
                    self.session_repo.deactivate_session(token)
                    return None
            except Exception:
                pass

            user_rec = self.user_repo.get_user_by_id(session.user_id)
            if not user_rec or user_rec.status != "ACTIVE":
                return None

            return self._record_to_domain_user(user_rec)

        return None

    def logout_user(self, token: str) -> bool:
        """Revoke active session token."""
        session = self.session_repo.get_session_by_token(token)
        if session:
            self.session_repo.deactivate_session(token)
            self.audit_ledger.append_event(
                event_type="LOGOUT",
                request_id=f"req_logout_{session.session_id}",
                user_id=session.user_id,
                operation="LOGOUT",
                result="SUCCESS",
            )
            return True
        return False

    def update_user_status_or_role(
        self,
        admin_user: User,
        target_user_id: str,
        new_role: Optional[str] = None,
        new_workspace_id: Optional[str] = None,
        new_clearance_level: Optional[int] = None,
        new_status: Optional[str] = None,
    ) -> DBUser:
        """
        Admin workflow to approve, update role/workspace/clearance, or deactivate user.
        """
        if admin_user.role not in {UserRole.AI_IT_ADMIN, UserRole.ADMIN}:
            raise PermissionError("Only AI/IT Administrators can modify user accounts.")

        user_rec = self.user_repo.get_user_by_id(target_user_id)
        if not user_rec:
            raise ValueError(f"User with ID '{target_user_id}' not found.")

        old_role = user_rec.role
        old_status = user_rec.status

        if new_role:
            user_rec.role = UserRole(new_role).value
        if new_workspace_id:
            user_rec.workspace_id = new_workspace_id.strip()
        if new_clearance_level is not None:
            user_rec.clearance_level = max(1, min(5, int(new_clearance_level)))
        if new_status:
            user_rec.status = new_status.upper().strip()

        user_rec.updated_at = datetime.now(timezone.utc).isoformat()
        updated = self.user_repo.update_user(user_rec)

        # Audit Event
        self.audit_ledger.append_event(
            event_type="USER_ROLE_CHANGED",
            request_id=f"req_admin_upd_{target_user_id}",
            user_id=admin_user.user_id,
            workspace_id=updated.workspace_id,
            operation="UPDATE_USER_ACCOUNT",
            result="SUCCESS",
            metadata={
                "target_user_id": target_user_id,
                "old_role": old_role,
                "new_role": updated.role,
                "old_status": old_status,
                "new_status": updated.status,
                "new_clearance": updated.clearance_level,
            },
        )

        return updated

    def list_all_users(self) -> List[DBUser]:
        return self.user_repo.list_users()

    def _record_to_domain_user(self, rec: DBUser) -> User:
        try:
            role_enum = UserRole(rec.role)
        except ValueError:
            role_enum = UserRole.PLANT_OPERATOR

        permissions = get_permissions_for_role(role_enum)

        return User(
            user_id=rec.id,
            full_name=rec.full_name,
            email=rec.email,
            role=role_enum,
            department=rec.department,
            position=getattr(rec, "position", None),
            workspace_id=rec.workspace_id,
            clearance_level=rec.clearance_level,
            status=rec.status,
            permissions=permissions,
            password_hash=rec.password_hash,
            is_active=(rec.status == "ACTIVE"),
        )
