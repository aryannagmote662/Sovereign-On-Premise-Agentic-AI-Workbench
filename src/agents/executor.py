"""
Agent Task Execution Engine.
Executes task graphs sequentially in dependency order, validating policies, approval gates, tool limits, and timeouts.
Stops immediately on failure or required approval gate. Never executes rejected tasks.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List, Optional

from src.agents.agent_plan import AgentPlan
from src.agents.agent_state import AgentState
from src.agents.agent_task import AgentTask
from src.agents.agent_types import AgentStatus, ApprovalStatus, TaskStatus
from src.agents.approval_gate import ApprovalGate
from src.agents.audit import AgentAuditLogger
from src.agents.policies import AgentPolicy
from src.agents.tool_registry import ToolRegistry
from src.agents.tool_result import ToolResult

logger = logging.getLogger("MRPL.Agents.Executor")


class AgentExecutor:
    """
    Sequential, deterministic task graph execution engine.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        policy: Optional[AgentPolicy] = None,
        approval_gate: Optional[ApprovalGate] = None,
        audit_logger: Optional[AgentAuditLogger] = None,
    ) -> None:
        self.registry = tool_registry
        self.policy = policy or AgentPolicy()
        self.approval_gate = approval_gate or ApprovalGate(policy=self.policy)
        self.audit_logger = audit_logger or AgentAuditLogger()

    async def execute_plan(
        self,
        plan: AgentPlan,
        state: AgentState,
    ) -> AgentState:
        """
        Execute tasks in plan sequentially based on dependency order and approval status.

        Args:
            plan: AgentPlan object.
            state: AgentState object to update during execution.

        Returns:
            Updated AgentState object.
        """
        start_time = time.perf_counter()
        state.plan = plan.to_dict()
        state.total_steps = len(plan.tasks)
        completed_task_ids: List[str] = [t.task_id for t in plan.tasks if t.status == TaskStatus.COMPLETED]
        tool_call_count = 0

        # Check if state/plan is already REJECTED or CANCELLED
        if state.agent_status in (AgentStatus.REJECTED, AgentStatus.CANCELLED):
            logger.warning(f"[EXECUTOR] Aborting execution. State status is '{state.agent_status.value}'.")
            return state

        state.agent_status = AgentStatus.EXECUTING
        self.audit_logger.log_event(
            request_id=state.request_id,
            task_id=state.task_id,
            event_type="AGENT_EXECUTING",
            status="EXECUTING",
        )

        for step_idx, task in enumerate(plan.tasks, start=1):
            state.current_step = step_idx

            if task.status == TaskStatus.COMPLETED:
                continue

            # 1. Enforce Execution Limits (Timeouts, Tool Calls, Task Count)
            elapsed_time = time.perf_counter() - start_time
            if elapsed_time > self.policy.max_execution_time:
                err_msg = f"Execution timeout exceeded ({elapsed_time:.1f}s > {self.policy.max_execution_time}s)"
                logger.error(f"[EXECUTOR] {err_msg}")
                state.agent_status = AgentStatus.FAILED
                state.error = err_msg
                self.audit_logger.log_event(
                    request_id=state.request_id,
                    task_id=task.task_id,
                    event_type="EXECUTION_TIMEOUT",
                    status="FAILED",
                    metadata={"elapsed_seconds": elapsed_time},
                )
                break

            if tool_call_count >= self.policy.max_tool_calls:
                err_msg = f"Maximum tool call limit reached ({tool_call_count} >= {self.policy.max_tool_calls})"
                logger.error(f"[EXECUTOR] {err_msg}")
                state.agent_status = AgentStatus.FAILED
                state.error = err_msg
                break

            # 2. Check Task Status & Dependencies
            if task.status == TaskStatus.REJECTED:
                logger.warning(f"[EXECUTOR] Task '{task.task_id}' is REJECTED. Halting plan execution.")
                state.agent_status = AgentStatus.REJECTED
                state.error = f"Task '{task.task_id}' was rejected by approver."
                self.audit_logger.log_event(
                    request_id=state.request_id,
                    task_id=task.task_id,
                    event_type="TASK_REJECTED",
                    status="REJECTED",
                )
                break

            # Verify dependencies
            if not task.is_ready(completed_task_ids) and task.dependencies:
                err_msg = f"Task '{task.task_id}' dependencies not satisfied: {task.dependencies}"
                logger.error(f"[EXECUTOR] {err_msg}")
                state.agent_status = AgentStatus.FAILED
                state.error = err_msg
                break

            # 3. Check Approval Gate Requirement
            approval_requirement = self.approval_gate.evaluate_task(task, self.policy)
            if approval_requirement == ApprovalStatus.PENDING and task.approval_status != ApprovalStatus.APPROVED:
                logger.info(
                    f"[EXECUTOR] Task '{task.task_id}' requires approval. Pausing execution pipeline."
                )
                task.status = TaskStatus.WAITING_FOR_APPROVAL
                task.approval_status = ApprovalStatus.PENDING
                task.approval_required = True
                state.agent_status = AgentStatus.WAITING_FOR_APPROVAL
                state.approval_status = ApprovalStatus.PENDING
                self.audit_logger.log_event(
                    request_id=state.request_id,
                    task_id=task.task_id,
                    event_type="APPROVAL_REQUIRED",
                    status="WAITING_FOR_APPROVAL",
                    tool_name=task.tool_name,
                )
                # Pause workflow for user approval endpoint
                break

            # 4. Check Tool Availability & Policies
            if not self.policy.is_tool_allowed(task.tool_name):
                err_msg = f"Tool '{task.tool_name}' is blocked by security policy."
                logger.error(f"[EXECUTOR] {err_msg}")
                task.status = TaskStatus.FAILED
                task.error = err_msg
                state.agent_status = AgentStatus.FAILED
                state.error = err_msg
                self.audit_logger.log_event(
                    request_id=state.request_id,
                    task_id=task.task_id,
                    event_type="TOOL_BLOCKED",
                    status="FAILED",
                    tool_name=task.tool_name,
                )
                break

            if not self.registry.has(task.tool_name):
                if "external" in task.tool_name or "communication" in task.tool_name or "send" in task.tool_name:
                    err_msg = f"External communication tool '{task.tool_name}' is not available."
                else:
                    err_msg = f"Tool '{task.tool_name}' is not registered in ToolRegistry."
                logger.warning(f"[EXECUTOR] {err_msg}")
                task.status = TaskStatus.FAILED
                task.error = err_msg
                state.agent_status = AgentStatus.FAILED
                state.error = err_msg
                self.audit_logger.log_event(
                    request_id=state.request_id,
                    task_id=task.task_id,
                    event_type="TOOL_NOT_FOUND",
                    status="FAILED",
                    tool_name=task.tool_name,
                )
                break

            # 5. Execute Tool Task
            tool = self.registry.get(task.tool_name)
            task.status = TaskStatus.RUNNING
            self.audit_logger.log_event(
                request_id=state.request_id,
                task_id=task.task_id,
                event_type="TOOL_STARTED",
                status="RUNNING",
                tool_name=task.tool_name,
            )

            # Resolve parameters from previous task results if needed
            params = self._resolve_task_parameters(task, state.task_results)

            try:
                t_exec_start = time.perf_counter()
                tool_result: ToolResult = await tool.execute(task.task_id, params)
                t_exec_dur = (time.perf_counter() - t_exec_start) * 1000.0
                tool_call_count += 1
                task.set_result(tool_result)

                # Persist DBExecution record
                from src.persistence import ExecutionRepository, DBExecution
                exec_repo = ExecutionRepository()
                exec_rec = DBExecution(
                    execution_id=f"exec_{uuid.uuid4().hex[:10]}",
                    task_id=state.task_id,
                    step_id=task.task_id,
                    attempt_number=1,
                    tool_name=task.tool_name,
                    status=task.status.value,
                    duration_ms=t_exec_dur,
                    safe_input_metadata=params,
                    safe_output_metadata=tool_result.data if isinstance(tool_result.data, dict) else {"result": str(tool_result.data)},
                    result_excerpt=str(tool_result.data) if tool_result.data else tool_result.error,
                    error_message=tool_result.error,
                )
                try:
                    exec_repo.record_execution(exec_rec)
                except Exception as ex_db:
                    logger.warning(f"Could not record execution attempt: {ex_db}")

                # Append to state task_results
                res_dict = tool_result.to_dict()
                state.task_results.append(res_dict)

                if tool_result.success:
                    completed_task_ids.append(task.task_id)
                    self.audit_logger.log_event(
                        request_id=state.request_id,
                        task_id=task.task_id,
                        event_type="TOOL_COMPLETED",
                        status="COMPLETED",
                        tool_name=task.tool_name,
                    )
                    # Extract final answer candidate if last step
                    if step_idx == len(plan.tasks) and isinstance(tool_result.data, dict):
                        state.final_result = (
                            tool_result.data.get("answer")
                            or tool_result.data.get("response")
                            or tool_result.data.get("code_output")
                            or tool_result.data.get("visual_analysis")
                            or str(tool_result.data)
                        )
                else:
                    self.audit_logger.log_event(
                        request_id=state.request_id,
                        task_id=task.task_id,
                        event_type="TOOL_FAILED",
                        status="FAILED",
                        tool_name=task.tool_name,
                        metadata={"error": tool_result.error},
                    )
                    state.agent_status = AgentStatus.FAILED
                    state.error = tool_result.error or f"Tool '{task.tool_name}' execution failed."
                    break

            except Exception as exc:
                err_msg = f"Unexpected exception executing tool '{task.tool_name}': {str(exc)}"
                logger.exception(f"[EXECUTOR] {err_msg}")
                task.status = TaskStatus.FAILED
                task.error = err_msg
                state.agent_status = AgentStatus.FAILED
                state.error = err_msg
                self.audit_logger.log_event(
                    request_id=state.request_id,
                    task_id=task.task_id,
                    event_type="TOOL_EXCEPTION",
                    status="FAILED",
                    tool_name=task.tool_name,
                    metadata={"error": str(exc)},
                )
                break

        # 6. Update Final State Status
        state.plan = plan.to_dict()
        if len(completed_task_ids) == len(plan.tasks):
            state.agent_status = AgentStatus.COMPLETED
            self.audit_logger.log_event(
                request_id=state.request_id,
                task_id=state.task_id,
                event_type="AGENT_COMPLETED",
                status="COMPLETED",
            )
            try:
                from src.observability.telemetry_service import get_telemetry_service
                telemetry = get_telemetry_service()
                telemetry.update_workflow_stage("VERIFICATION", "ACTIVE")
                telemetry.update_workflow_stage("RESPONSE", "COMPLETED")
            except Exception:
                pass
        elif state.agent_status not in (AgentStatus.WAITING_FOR_APPROVAL, AgentStatus.REJECTED, AgentStatus.CANCELLED, AgentStatus.FAILED):
            state.agent_status = AgentStatus.FAILED

        return state

    def _resolve_task_parameters(
        self,
        task: AgentTask,
        previous_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Pass context or output from prior dependency tasks into current task parameters.
        """
        params = dict(task.parameters or {})
        ctx = params.get("context", {})
        if isinstance(ctx, dict) and "use_previous_task_result" in ctx:
            dep_id = ctx["use_previous_task_result"]
            for prev_res in previous_results:
                if prev_res.get("task_id") == dep_id and prev_res.get("data"):
                    prev_data = prev_res["data"]
                    # If prior task produced text context or document answer, fold it into query parameter
                    if isinstance(prev_data, dict):
                        context_str = prev_data.get("answer") or prev_data.get("chunks") or str(prev_data)
                        params["query"] = f"Context from previous task:\n{context_str}\n\nUser Question:\n{params.get('query', '')}"
        return params
