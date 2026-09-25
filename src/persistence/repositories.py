"""
Data Repository implementations for Agent Tasks, Plans, Tool Executions, and Audit Events.
Enforces safe serialization, secret redaction, output truncation, and parameterized SQL queries.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings
from src.persistence.database import DatabaseManager, get_db_manager
from src.persistence.exceptions import PersistenceError, TaskNotFoundError
from src.persistence.models import DBAuditEvent, DBExecution, DBPlan, DBTask, DBRole, DBUser, DBSession


logger = logging.getLogger("MRPL.Persistence.Repositories")

SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "secret",
    "api_key",
    "authorization",
    "bearer",
    "private_key",
    "reasoning",
    "chain_of_thought",
    "thought",
}


def redact_sensitive_data(data: Any) -> Any:
    """
    Recursively redact sensitive key-value pairs from dictionary/list payloads.
    """
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k.lower() in SENSITIVE_KEYS:
                cleaned[k] = "[REDACTED_SECRET]"
            else:
                cleaned[k] = redact_sensitive_data(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


def truncate_excerpt(text: Optional[str], max_len: Optional[int] = None) -> Optional[str]:
    """
    Truncate text excerpts to MAX_PERSISTED_RESULT_CHARS.
    """
    if text is None:
        return None
    limit = max_len or settings.MAX_PERSISTED_RESULT_CHARS
    if len(text) > limit:
        return text[:limit] + f"... [TRUNCATED at {limit} chars]"
    return text


class TaskRepository:
    """
    Repository providing durable CRUD operations for AgentTask records and Plans.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or get_db_manager()

    def create_task(self, task: DBTask) -> DBTask:
        """Persist a new AgentTask record."""
        safe_meta = redact_sensitive_data(task.metadata)
        meta_json = json.dumps(safe_meta)

        sql = """
            INSERT OR REPLACE INTO agent_tasks (
                task_id, user_id, session_id, task_type, title, query, status,
                risk_level, requires_approval, approval_status, created_at, updated_at,
                started_at, completed_at, cancelled_at, failed_at, current_step,
                total_steps, retry_count, max_retries, result_status, result_summary,
                error_code, error_message, recovery_status, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            task.task_id,
            task.user_id,
            task.session_id,
            task.task_type,
            task.title,
            task.query,
            task.status,
            task.risk_level,
            1 if task.requires_approval else 0,
            task.approval_status,
            task.created_at,
            task.updated_at,
            task.started_at,
            task.completed_at,
            task.cancelled_at,
            task.failed_at,
            task.current_step,
            task.total_steps,
            task.retry_count,
            task.max_retries,
            task.result_status,
            truncate_excerpt(task.result_summary),
            task.error_code,
            task.error_message,
            task.recovery_status,
            meta_json,
        )

        with self.db.transaction() as conn:
            conn.execute(sql, params)
        return task

    def get_task(self, task_id: str) -> Optional[DBTask]:
        """Retrieve task by ID."""
        sql = "SELECT * FROM agent_tasks WHERE task_id = ?;"
        conn = self.db.get_raw_connection()
        cursor = conn.execute(sql, (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def update_task(self, task: DBTask) -> DBTask:
        """Update existing task state fields."""
        safe_meta = redact_sensitive_data(task.metadata)
        meta_json = json.dumps(safe_meta)

        sql = """
            UPDATE agent_tasks SET
                status = ?, approval_status = ?, updated_at = ?, started_at = ?,
                completed_at = ?, cancelled_at = ?, failed_at = ?, current_step = ?,
                total_steps = ?, retry_count = ?, result_status = ?, result_summary = ?,
                error_code = ?, error_message = ?, recovery_status = ?, metadata_json = ?
            WHERE task_id = ?;
        """
        params = (
            task.status,
            task.approval_status,
            task.updated_at,
            task.started_at,
            task.completed_at,
            task.cancelled_at,
            task.failed_at,
            task.current_step,
            task.total_steps,
            task.retry_count,
            task.result_status,
            truncate_excerpt(task.result_summary),
            task.error_code,
            task.error_message,
            task.recovery_status,
            meta_json,
            task.task_id,
        )

        with self.db.transaction() as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount == 0:
                raise TaskNotFoundError(task.task_id)
        return task

    def list_tasks(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[DBTask], int]:
        """List tasks with filtering and pagination."""
        clauses = []
        params = []

        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)

        if status:
            clauses.append("status = ?")
            params.append(status)

        if task_type:
            clauses.append("task_type = ?")
            params.append(task_type)

        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)

        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        count_sql = f"SELECT COUNT(*) as total FROM agent_tasks {where_str};"
        conn = self.db.get_raw_connection()
        total_count = conn.execute(count_sql, tuple(params)).fetchone()["total"]

        bounded_limit = min(max(1, limit), settings.TASK_LIST_MAX_LIMIT)
        query_sql = f"SELECT * FROM agent_tasks {where_str} ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        query_params = list(params) + [bounded_limit, max(0, offset)]

        cursor = conn.execute(query_sql, tuple(query_params))
        rows = cursor.fetchall()
        tasks = [self._row_to_task(row) for row in rows]
        return tasks, total_count

    def save_plan(self, plan: DBPlan) -> DBPlan:
        """Persist or replace an AgentPlan record."""
        safe_graph = redact_sensitive_data(plan.tasks_graph)
        graph_json = json.dumps(safe_graph)

        sql = """
            INSERT OR REPLACE INTO agent_plans (
                plan_id, task_id, plan_version, intent, selected_model,
                total_tasks, requires_approval, status, created_at, tasks_graph_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            plan.plan_id,
            plan.task_id,
            plan.plan_version,
            plan.intent,
            plan.selected_model,
            plan.total_tasks,
            1 if plan.requires_approval else 0,
            plan.status,
            plan.created_at,
            graph_json,
        )

        with self.db.transaction() as conn:
            conn.execute(sql, params)
        return plan

    def get_plan(self, plan_id: str) -> Optional[DBPlan]:
        """Retrieve plan by ID."""
        sql = "SELECT * FROM agent_plans WHERE plan_id = ?;"
        conn = self.db.get_raw_connection()
        cursor = conn.execute(sql, (plan_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return DBPlan(
            plan_id=row["plan_id"],
            task_id=row["task_id"],
            plan_version=row["plan_version"],
            intent=row["intent"],
            selected_model=row["selected_model"],
            total_tasks=row["total_tasks"],
            requires_approval=bool(row["requires_approval"]),
            status=row["status"],
            created_at=row["created_at"],
            tasks_graph=json.loads(row["tasks_graph_json"] or "[]"),
        )

    def get_plan_by_task_id(self, task_id: str) -> Optional[DBPlan]:
        """Retrieve plan for a given task ID."""
        sql = "SELECT * FROM agent_plans WHERE task_id = ? ORDER BY created_at DESC LIMIT 1;"
        conn = self.db.get_raw_connection()
        cursor = conn.execute(sql, (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return DBPlan(
            plan_id=row["plan_id"],
            task_id=row["task_id"],
            plan_version=row["plan_version"],
            intent=row["intent"],
            selected_model=row["selected_model"],
            total_tasks=row["total_tasks"],
            requires_approval=bool(row["requires_approval"]),
            status=row["status"],
            created_at=row["created_at"],
            tasks_graph=json.loads(row["tasks_graph_json"] or "[]"),
        )

    def delete_task(self, task_id: str) -> bool:
        """Delete task, associated plan, executions, and audit records from SQLite."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM agent_executions WHERE task_id = ?;", (task_id,))
            conn.execute("DELETE FROM agent_audit_events WHERE task_id = ?;", (task_id,))
            conn.execute("DELETE FROM agent_plans WHERE task_id = ?;", (task_id,))
            cursor = conn.execute("DELETE FROM agent_tasks WHERE task_id = ?;", (task_id,))
            return cursor.rowcount > 0

    def _row_to_task(self, row: Any) -> DBTask:
        return DBTask(
            task_id=row["task_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            task_type=row["task_type"],
            title=row["title"],
            query=row["query"],
            status=row["status"],
            risk_level=row["risk_level"],
            requires_approval=bool(row["requires_approval"]),
            approval_status=row["approval_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            cancelled_at=row["cancelled_at"],
            failed_at=row["failed_at"],
            current_step=row["current_step"],
            total_steps=row["total_steps"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            result_status=row["result_status"],
            result_summary=row["result_summary"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            recovery_status=row["recovery_status"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


class ExecutionRepository:
    """
    Repository for tool execution attempt records.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or get_db_manager()

    def record_execution(self, exec_rec: DBExecution) -> DBExecution:
        """Persist a tool execution record."""
        safe_in = json.dumps(redact_sensitive_data(exec_rec.safe_input_metadata))
        safe_out = json.dumps(redact_sensitive_data(exec_rec.safe_output_metadata))
        excerpt = truncate_excerpt(exec_rec.result_excerpt)

        sql = """
            INSERT OR REPLACE INTO agent_executions (
                execution_id, task_id, step_id, attempt_number, tool_name, status,
                started_at, completed_at, duration_ms, safe_input_json, safe_output_json,
                result_excerpt, error_code, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            exec_rec.execution_id,
            exec_rec.task_id,
            exec_rec.step_id,
            exec_rec.attempt_number,
            exec_rec.tool_name,
            exec_rec.status,
            exec_rec.started_at,
            exec_rec.completed_at,
            exec_rec.duration_ms,
            safe_in,
            safe_out,
            excerpt,
            exec_rec.error_code,
            exec_rec.error_message,
        )

        with self.db.transaction() as conn:
            conn.execute(sql, params)
        return exec_rec

    def list_executions_for_task(self, task_id: str) -> List[DBExecution]:
        """List execution records for a target task."""
        sql = "SELECT * FROM agent_executions WHERE task_id = ? ORDER BY started_at ASC;"
        conn = self.db.get_raw_connection()
        cursor = conn.execute(sql, (task_id,))
        rows = cursor.fetchall()
        return [
            DBExecution(
                execution_id=r["execution_id"],
                task_id=r["task_id"],
                step_id=r["step_id"],
                attempt_number=r["attempt_number"],
                tool_name=r["tool_name"],
                status=r["status"],
                started_at=r["started_at"],
                completed_at=r["completed_at"],
                duration_ms=r["duration_ms"],
                safe_input_metadata=json.loads(r["safe_input_json"] or "{}"),
                safe_output_metadata=json.loads(r["safe_output_json"] or "{}"),
                result_excerpt=r["result_excerpt"],
                error_code=r["error_code"],
                error_message=r["error_message"],
            )
            for r in rows
        ]


class AuditRepository:
    """
    Repository for persistent audit event trajectory records.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or get_db_manager()

    def record_event(self, evt: DBAuditEvent) -> DBAuditEvent:
        """Persist a structured audit log event."""
        safe_meta = redact_sensitive_data(evt.metadata)
        meta_json = json.dumps(safe_meta)

        sql = """
            INSERT INTO agent_audit_events (
                event_id, task_id, timestamp, event_type, actor_id, actor_role,
                component, status, tool_name, risk_level, metadata_json, correlation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            evt.event_id,
            evt.task_id,
            evt.timestamp,
            evt.event_type,
            evt.actor_id,
            evt.actor_role,
            evt.component,
            evt.status,
            evt.tool_name,
            evt.risk_level,
            meta_json,
            evt.correlation_id,
        )

        with self.db.transaction() as conn:
            conn.execute(sql, params)
        return evt

    def list_events_for_task(self, task_id: str, limit: int = 50, offset: int = 0) -> Tuple[List[DBAuditEvent], int]:
        """Retrieve audit log events for a task."""
        count_sql = "SELECT COUNT(*) as total FROM agent_audit_events WHERE task_id = ?;"
        conn = self.db.get_raw_connection()
        total = conn.execute(count_sql, (task_id,)).fetchone()["total"]

        bounded_limit = min(max(1, limit), settings.AUDIT_PAGE_MAX_LIMIT)
        query_sql = """
            SELECT * FROM agent_audit_events
            WHERE task_id = ?
            ORDER BY timestamp ASC
            LIMIT ? OFFSET ?;
        """
        cursor = conn.execute(query_sql, (task_id, bounded_limit, max(0, offset)))
        rows = cursor.fetchall()

        events = [
            DBAuditEvent(
                event_id=r["event_id"],
                task_id=r["task_id"],
                timestamp=r["timestamp"],
                event_type=r["event_type"],
                actor_id=r["actor_id"],
                actor_role=r["actor_role"],
                component=r["component"],
                status=r["status"],
                tool_name=r["tool_name"],
                risk_level=r["risk_level"],
                metadata=json.loads(r["metadata_json"] or "{}"),
                correlation_id=r["correlation_id"],
            )
            for r in rows
        ]
        return events, total


class RoleRepository:
    """Repository managing platform RBAC roles."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db_manager()

    def create_role(self, role: DBRole) -> DBRole:
        sql = """
            INSERT OR REPLACE INTO roles (id, name, code, primary_workspace, description, is_active)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            conn.execute(
                sql,
                (
                    role.id,
                    role.name,
                    role.code,
                    role.primary_workspace,
                    role.description,
                    1 if role.is_active else 0,
                ),
            )
        return role

    def get_role_by_code(self, code: str) -> Optional[DBRole]:
        conn = self.db.get_raw_connection()
        row = conn.execute("SELECT * FROM roles WHERE code = ?;", (code,)).fetchone()
        if not row:
            return None
        return DBRole(
            id=row["id"],
            name=row["name"],
            code=row["code"],
            primary_workspace=row["primary_workspace"],
            description=row["description"] or "",
            is_active=bool(row["is_active"]),
        )

    def list_roles() -> List[DBRole]:
        conn = self.db.get_raw_connection()
        rows = conn.execute("SELECT * FROM roles WHERE is_active = 1 ORDER BY name ASC;").fetchall()
        return [
            DBRole(
                id=r["id"],
                name=r["name"],
                code=r["code"],
                primary_workspace=r["primary_workspace"],
                description=r["description"] or "",
                is_active=bool(r["is_active"]),
            )
            for r in rows
        ]

    def seed_default_roles(self) -> None:
        """Seed exact 6 application roles."""
        default_roles = [
            DBRole("role_op_001", "Plant Operator", "PLANT_OPERATOR", "Operations", "Operational monitoring & document inspection"),
            DBRole("role_eng_001", "Engineer", "ENGINEER", "Engineering", "Refinery process & technical engineering operations"),
            DBRole("role_sup_001", "Shift Supervisor", "SHIFT_SUPERVISOR", "Operations", "Operational sign-off and approval management"),
            DBRole("role_mgr_001", "Plant Manager", "PLANT_MANAGER", "Management", "High-level analytics & refinery executive management"),
            DBRole("role_admin_001", "AI/IT Administrator", "AI_IT_ADMIN", "IT-OT", "Platform, AI model, security & user administration"),
            DBRole("role_aud_001", "Auditor / Document Controller", "AUDITOR_DOC_CONTROLLER", "Audit", "Document control & compliance auditing"),
        ]
        for r in default_roles:
            self.create_role(r)


class UserRepository:
    """Repository managing platform User records."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db_manager()

    def create_user(self, user: DBUser) -> DBUser:
        sql = """
            INSERT INTO users (id, full_name, email, password_hash, role, department, workspace_id, clearance_level, status, created_at, updated_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            conn.execute(
                sql,
                (
                    user.id,
                    user.full_name,
                    user.email.lower().strip(),
                    user.password_hash,
                    user.role,
                    user.department,
                    user.workspace_id,
                    user.clearance_level,
                    user.status,
                    user.created_at,
                    user.updated_at,
                    user.last_login,
                ),
            )
        return user

    def update_user(self, user: DBUser) -> DBUser:
        sql = """
            UPDATE users
            SET full_name = ?, email = ?, password_hash = ?, role = ?, department = ?,
                workspace_id = ?, clearance_level = ?, status = ?, updated_at = ?, last_login = ?
            WHERE id = ?;
        """
        with self.db.transaction() as conn:
            conn.execute(
                sql,
                (
                    user.full_name,
                    user.email.lower().strip(),
                    user.password_hash,
                    user.role,
                    user.department,
                    user.workspace_id,
                    user.clearance_level,
                    user.status,
                    user.updated_at,
                    user.last_login,
                    user.id,
                ),
            )
        return user

    def get_user_by_id(self, user_id: str) -> Optional[DBUser]:
        conn = self.db.get_raw_connection()
        row = conn.execute("SELECT * FROM users WHERE id = ?;", (user_id,)).fetchone()
        if not row:
            return None
        return self._row_to_user(row)

    def get_user_by_email(self, email: str) -> Optional[DBUser]:
        conn = self.db.get_raw_connection()
        row = conn.execute("SELECT * FROM users WHERE lower(email) = lower(?);", (email.strip(),)).fetchone()
        if not row:
            return None
        return self._row_to_user(row)

    def list_users(self, limit: int = 100, offset: int = 0) -> List[DBUser]:
        conn = self.db.get_raw_connection()
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?;", (limit, offset)).fetchall()
        return [self._row_to_user(r) for r in rows]

    def _row_to_user(self, row: Any) -> DBUser:
        return DBUser(
            id=row["id"],
            full_name=row["full_name"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=row["role"],
            department=row["department"],
            workspace_id=row["workspace_id"],
            clearance_level=int(row["clearance_level"]),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_login=row["last_login"],
        )


class SessionRepository:
    """Repository managing user session tokens."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db_manager()

    def create_session(self, session: DBSession) -> DBSession:
        sql = """
            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            conn.execute(
                sql,
                (
                    session.session_id,
                    session.user_id,
                    session.token,
                    session.created_at,
                    session.expires_at,
                    1 if session.is_active else 0,
                ),
            )
        return session

    def get_session_by_token(self, token: str) -> Optional[DBSession]:
        conn = self.db.get_raw_connection()
        row = conn.execute("SELECT * FROM user_sessions WHERE token = ? AND is_active = 1;", (token,)).fetchone()
        if not row:
            return None
        return DBSession(
            session_id=row["session_id"],
            user_id=row["user_id"],
            token=row["token"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            is_active=bool(row["is_active"]),
        )

    def deactivate_session(self, token: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE user_sessions SET is_active = 0 WHERE token = ?;", (token,))

    def deactivate_all_user_sessions(self, user_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE user_sessions SET is_active = 0 WHERE user_id = ?;", (user_id,))

