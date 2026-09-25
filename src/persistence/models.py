"""
Data Transfer Models for SQLite Relational Persistence Layer.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DBTask:
    """
    Relational record representation for an AgentTask in SQLite.
    """

    task_id: str
    user_id: str
    session_id: str
    task_type: str
    title: str
    query: str
    status: str
    risk_level: str
    requires_approval: bool
    approval_status: str
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    failed_at: Optional[str] = None
    current_step: int = 0
    total_steps: int = 0
    retry_count: int = 0
    max_retries: int = 2
    result_status: str = "PENDING"
    result_summary: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    recovery_status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary representation."""
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "task_type": self.task_type,
            "title": self.title,
            "query": self.query,
            "status": self.status,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "approval_status": self.approval_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
            "failed_at": self.failed_at,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "result_status": self.result_status,
            "result_summary": self.result_summary,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "recovery_status": self.recovery_status,
            "metadata": self.metadata,
        }


@dataclass
class DBPlan:
    """
    Relational record representation for an AgentPlan and its step graph.
    """

    plan_id: str
    task_id: str
    plan_version: int
    intent: str
    selected_model: str
    total_tasks: int
    requires_approval: bool
    status: str
    created_at: str = field(default_factory=_utc_now_iso)
    tasks_graph: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DBExecution:
    """
    Relational record for individual tool execution attempt.
    """

    execution_id: str
    task_id: str
    step_id: str
    attempt_number: int
    tool_name: str
    status: str
    started_at: str = field(default_factory=_utc_now_iso)
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    safe_input_metadata: Dict[str, Any] = field(default_factory=dict)
    safe_output_metadata: Dict[str, Any] = field(default_factory=dict)
    result_excerpt: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class DBAuditEvent:
    """
    Relational record for structured audit trajectory event.
    """

    event_id: str
    task_id: str
    timestamp: str = field(default_factory=_utc_now_iso)
    event_type: str = "GENERAL"
    actor_id: str = "system"
    actor_role: str = "USER"
    component: str = "orchestrator"
    status: str = "SUCCESS"
    tool_name: Optional[str] = None
    risk_level: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None


@dataclass
class DBRole:
    """
    Relational record for platform RBAC role.
    """
    id: str
    name: str
    code: str
    primary_workspace: str
    description: str = ""
    is_active: bool = True


@dataclass
class DBUser:
    """
    Relational record for platform User account.
    """
    id: str
    full_name: str
    email: str
    password_hash: str
    role: str
    department: str
    workspace_id: str
    position: Optional[str] = None
    clearance_level: int = 1
    status: str = "PENDING"
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    last_login: Optional[str] = None


@dataclass
class DBSession:
    """
    Relational record for authenticated user token session.
    """
    session_id: str
    user_id: str
    token: str
    created_at: str = field(default_factory=_utc_now_iso)
    expires_at: str = field(default_factory=_utc_now_iso)
    is_active: bool = True

