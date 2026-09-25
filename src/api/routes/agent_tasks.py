"""
FastAPI REST API Router for Persistent Agent Tasks, Execution History, Audit Trajectories, and Recovery.
Enforces authentication, RBAC authorization, task ownership isolation, and standard response envelopes.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.agents.orchestrator import AgentOrchestrator
from src.agents.recovery import RecoveryManager
from src.api.dependencies import get_agent_orchestrator
from src.api.responses.standard_response import StandardResponse, success_response
from src.auth import (
    User,
    UserRole,
    get_current_user,
    require_permission,
    PERMISSION_AGENT_RUN,
    PERMISSION_AGENT_APPROVE,
    PERMISSION_AGENT_CANCEL,
    PERMISSION_OPERATOR_READ,
    PERMISSION_AUDIT_READ,
)
from src.persistence import (
    AuditRepository,
    ExecutionRepository,
    TaskRepository,
    TaskNotFoundError,
    TaskNotResumableError,
    TaskNotRetryableError,
    RetryLimitExceededError,
    UnauthorizedTaskAccessError,
)
from src.schemas.persistence import (
    AgentAuditEventResponse,
    AgentAuditResponse,
    AgentExecutionListResponse,
    AgentExecutionResponse,
    AgentRecoveryResponse,
    AgentResumeRequest,
    AgentRetryRequest,
    AgentTaskCreateRequest,
    AgentTaskListResponse,
    AgentTaskResponse,
    AgentTimelineResponse,
    TimelineEventItem,
)

router = APIRouter(prefix="/agent/tasks", tags=["Agent Task Management & Persistence"])


def get_task_repo() -> TaskRepository:
    return TaskRepository()


def get_exec_repo() -> ExecutionRepository:
    return ExecutionRepository()


def get_audit_repo() -> AuditRepository:
    return AuditRepository()


def get_recovery_mgr() -> RecoveryManager:
    return RecoveryManager()


@router.post("", response_model=StandardResponse[AgentTaskResponse])
async def create_durable_task(
    payload: AgentTaskCreateRequest,
    user: User = Depends(require_permission(PERMISSION_AGENT_RUN)),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
):
    """
    Create a durable agent task record and generate execution plan.
    """
    state = orchestrator.create_agent_task(
        query=payload.query,
        document_id=payload.document_id,
        force_rag=payload.force_rag or False,
        top_k=payload.top_k,
    )
    # Associate current authenticated user_id
    state.metadata["user_id"] = user.user_id
    state.metadata["session_id"] = payload.session_id or "session_default"
    from src.agents.agent_types import AgentStatus
    from src.persistence.models import DBTask
    task_repo = get_task_repo()

    # Execute immediately if no approval gate is required
    if state.agent_status != AgentStatus.WAITING_FOR_APPROVAL:
        state = await orchestrator.execute(state.task_id)

    # Persist relational DBTask record in SQLite
    status_str = state.agent_status.value if hasattr(state.agent_status, "value") else str(state.agent_status)
    approval_str = state.approval_status.value if hasattr(state.approval_status, "value") else str(state.approval_status)

    db_task = DBTask(
        task_id=state.task_id,
        user_id=user.user_id,
        session_id=payload.session_id or "session_default",
        task_type=state.intent or "GENERAL_CHAT",
        title=payload.query[:60],
        query=payload.query,
        status=status_str,
        risk_level="LOW",
        requires_approval=(state.agent_status == AgentStatus.WAITING_FOR_APPROVAL),
        approval_status=approval_str,
        current_step=state.current_step,
        total_steps=state.total_steps,
        result_status=status_str,
        result_summary=str(state.final_result or ""),
        metadata=state.metadata or {},
    )
    task_repo.create_task(db_task)

    saved_task = task_repo.get_task(state.task_id)
    resp = AgentTaskResponse(**(saved_task or db_task).to_dict())
    return success_response(data=resp, message="Durable agent task created and executed successfully")


@router.get("", response_model=StandardResponse[AgentTaskListResponse])
async def list_agent_tasks(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    task_type_filter: Optional[str] = Query(default=None, alias="task_type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repo),
):
    """
    List durable agent tasks available to the authenticated user/operator.
    Regular users only view their owned tasks; OPERATOR/ADMIN can view all tasks.
    """
    filter_user_id = None
    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        filter_user_id = user.user_id

    tasks, total = task_repo.list_tasks(
        user_id=filter_user_id,
        status=status_filter,
        task_type=task_type_filter,
        limit=limit,
        offset=offset,
    )

    resp_tasks = [AgentTaskResponse(**t.to_dict()) for t in tasks]
    resp = AgentTaskListResponse(
        tasks=resp_tasks,
        total_count=total,
        limit=limit,
        offset=offset,
    )
    return success_response(data=resp, message="Task list retrieved successfully")


@router.get("/{task_id}", response_model=StandardResponse[AgentTaskResponse])
async def get_task_by_id(
    task_id: str,
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repo),
):
    """
    Retrieve state of a specific durable agent task by ID.
    """
    db_task = task_repo.get_task(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR) and db_task.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied to this task.")

    resp = AgentTaskResponse(**db_task.to_dict())
    return success_response(data=resp, message="Task details retrieved")


@router.delete("/{task_id}", response_model=StandardResponse[dict])
async def delete_task_by_id(
    task_id: str,
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repo),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
):
    """
    Delete a durable agent task and its associated execution plan, traces, and state.
    Strictly restricted to Admin role (UserRole.ADMIN).
    """
    if user.role not in (UserRole.ADMIN, UserRole.AI_IT_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to delete agent tasks.",
        )

    db_task = task_repo.get_task(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    task_repo.delete_task(task_id)
    try:
        orchestrator.state_store.delete_state(task_id)
    except Exception:
        pass

    return success_response(
        data={"task_id": task_id, "deleted": True},
        message=f"Agent task '{task_id}' purged successfully",
    )


@router.get("/{task_id}/executions", response_model=StandardResponse[AgentExecutionListResponse])
async def get_task_executions(
    task_id: str,
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repo),
    exec_repo: ExecutionRepository = Depends(get_exec_repo),
):
    """
    Retrieve tool execution history for a target task.
    """
    db_task = task_repo.get_task(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR) and db_task.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied to this task.")

    executions = exec_repo.list_executions_for_task(task_id)
    exec_schemas = [
        AgentExecutionResponse(
            execution_id=e.execution_id,
            task_id=e.task_id,
            step_id=e.step_id,
            attempt_number=e.attempt_number,
            tool_name=e.tool_name,
            status=e.status,
            started_at=e.started_at,
            completed_at=e.completed_at,
            duration_ms=e.duration_ms,
            safe_input_metadata=e.safe_input_metadata,
            safe_output_metadata=e.safe_output_metadata,
            result_excerpt=e.result_excerpt,
            error_code=e.error_code,
            error_message=e.error_message,
        )
        for e in executions
    ]
    resp = AgentExecutionListResponse(task_id=task_id, executions=exec_schemas)
    return success_response(data=resp, message="Execution history retrieved")


@router.get("/{task_id}/audit", response_model=StandardResponse[AgentAuditResponse])
async def get_task_audit(
    task_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_permission(PERMISSION_AUDIT_READ)),
    task_repo: TaskRepository = Depends(get_task_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Retrieve structured audit event trajectory for a target task.
    """
    db_task = task_repo.get_task(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    events, total = audit_repo.list_events_for_task(task_id, limit=limit, offset=offset)
    evt_schemas = [
        AgentAuditEventResponse(
            event_id=e.event_id,
            task_id=e.task_id,
            timestamp=e.timestamp,
            event_type=e.event_type,
            actor_id=e.actor_id,
            actor_role=e.actor_role,
            component=e.component,
            status=e.status,
            tool_name=e.tool_name,
            risk_level=e.risk_level,
            metadata=e.metadata,
            correlation_id=e.correlation_id,
        )
        for e in events
    ]
    resp = AgentAuditResponse(
        task_id=task_id,
        events=evt_schemas,
        total_count=total,
        limit=limit,
        offset=offset,
    )
    return success_response(data=resp, message="Audit trail retrieved")


@router.get("/{task_id}/timeline", response_model=StandardResponse[AgentTimelineResponse])
async def get_task_timeline(
    task_id: str,
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Retrieve chronological task lifecycle timeline.
    """
    db_task = task_repo.get_task(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR) and db_task.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied to this task.")

    events, _ = audit_repo.list_events_for_task(task_id, limit=200, offset=0)
    timeline_items = [
        TimelineEventItem(
            event=e.event_type,
            timestamp=e.timestamp,
            actor_id=e.actor_id,
            status=e.status,
            details={"component": e.component, "tool": e.tool_name},
        )
        for e in events
    ]
    resp = AgentTimelineResponse(task_id=task_id, timeline=timeline_items)
    return success_response(data=resp, message="Lifecycle timeline retrieved")


@router.post("/{task_id}/resume", response_model=StandardResponse[AgentRecoveryResponse])
async def resume_interrupted_task(
    task_id: str,
    payload: Optional[AgentResumeRequest] = None,
    user: User = Depends(require_permission(PERMISSION_AGENT_APPROVE)),
    recovery_mgr: RecoveryManager = Depends(get_recovery_mgr),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
):
    """
    Explicitly resume an INTERRUPTED agent task (Requires OPERATOR / ADMIN role).
    Re-evaluates governance approval gates before continuing execution.
    """
    try:
        updated_task = recovery_mgr.prepare_resume(task_id, actor_id=user.username)
        # If task is now APPROVED, trigger execution
        if updated_task.status == "APPROVED":
            await orchestrator.execute(task_id)
            final_task = recovery_mgr.task_repo.get_task(task_id)
            status_val = final_task.status if final_task else updated_task.status
        else:
            status_val = updated_task.status

        resp = AgentRecoveryResponse(
            status="SUCCESS",
            message=f"Task '{task_id}' resume initiated. Current status: {status_val}",
            task_id=task_id,
            previous_status="INTERRUPTED",
            new_status=status_val,
        )
        return success_response(data=resp, message="Task resume executed")
    except (TaskNotFoundError, TaskNotResumableError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Resume operation failed: {str(exc)}")


@router.post("/{task_id}/retry", response_model=StandardResponse[AgentRecoveryResponse])
async def retry_failed_task(
    task_id: str,
    payload: Optional[AgentRetryRequest] = None,
    user: User = Depends(require_permission(PERMISSION_AGENT_APPROVE)),
    recovery_mgr: RecoveryManager = Depends(get_recovery_mgr),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
):
    """
    Retry a FAILED agent task within bounded MAX_TASK_RETRIES (Requires OPERATOR / ADMIN role).
    """
    try:
        updated_task = recovery_mgr.prepare_retry(task_id, actor_id=user.username)
        await orchestrator.execute(task_id)
        final_task = recovery_mgr.task_repo.get_task(task_id)
        status_val = final_task.status if final_task else updated_task.status

        resp = AgentRecoveryResponse(
            status="SUCCESS",
            message=f"Task '{task_id}' retry initiated (Attempt {updated_task.retry_count}/{updated_task.max_retries}).",
            task_id=task_id,
            previous_status="FAILED",
            new_status=status_val,
        )
        return success_response(data=resp, message="Task retry executed")
    except (TaskNotFoundError, TaskNotRetryableError, RetryLimitExceededError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retry operation failed: {str(exc)}")


@router.post("/{task_id}/cancel", response_model=StandardResponse[AgentTaskResponse])
async def cancel_agent_task(
    task_id: str,
    user: User = Depends(require_permission(PERMISSION_AGENT_CANCEL)),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    task_repo: TaskRepository = Depends(get_task_repo),
):
    """
    Cancel an active, waiting, or interrupted task (Requires CANCEL permission).
    """
    state = orchestrator.cancel(task_id)
    db_task = task_repo.get_task(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    resp = AgentTaskResponse(**db_task.to_dict())
    return success_response(data=resp, message="Task cancelled successfully")
