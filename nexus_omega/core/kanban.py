"""
NEXUS-OMEGA (APEX-1) - Asynchronous Kanban Task Graph Engine
Manages task DAGs across states: TODO → READY → IN_PROGRESS → BLOCKED/DONE/FAILED.
Publishes state change events via Redis pub/sub for real-time dashboard updates.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger("APEX1.Kanban")


class TaskStatus(str, Enum):
    TODO = "TODO"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class Task:
    id: str
    title: str
    instruction: str
    status: TaskStatus = TaskStatus.TODO
    parent_id: Optional[str] = None
    assigned_agent: Optional[str] = None
    input_payload: Dict[str, Any] = field(default_factory=dict)
    output_payload: Dict[str, Any] = field(default_factory=dict)
    execution_order: int = 1
    requires_human_auth: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    goal_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Goal:
    id: str
    title: str
    description: str
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    is_completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KanbanEngine:
    """
    Async Kanban DAG Engine managing task state transitions.
    - Supports dependency chains (parent → child auto-promotion).
    - Broadcasts real-time state change events.
    - Thread-safe via asyncio.Lock.
    """

    def __init__(self, redis_client=None):
        self._tasks: Dict[str, Task] = {}
        self._goals: Dict[str, Goal] = {}
        self._children: Dict[str, List[str]] = {}   # parent_id → [child_ids]
        self._lock = asyncio.Lock()
        self._redis = redis_client
        self._state_change_callbacks: List[Callable] = []

    # ------------------------------------------------------------------
    # Goal Management
    # ------------------------------------------------------------------
    def create_goal(self, title: str, description: str, success_criteria: Dict = None) -> Goal:
        goal = Goal(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            success_criteria=success_criteria or {},
        )
        self._goals[goal.id] = goal
        logger.info(f"Goal created: [{goal.id}] {goal.title}")
        return goal

    def get_goals(self) -> List[Goal]:
        return list(self._goals.values())

    # ------------------------------------------------------------------
    # Task Management
    # ------------------------------------------------------------------
    async def add_task(
        self,
        task_id: str,
        title: str,
        instruction: str,
        parent_id: Optional[str] = None,
        goal_id: Optional[str] = None,
        execution_order: int = 1,
        requires_human_auth: bool = False,
    ) -> Task:
        async with self._lock:
            status = TaskStatus.TODO if parent_id else TaskStatus.READY
            task = Task(
                id=task_id,
                title=title,
                instruction=instruction,
                status=status,
                parent_id=parent_id,
                goal_id=goal_id,
                execution_order=execution_order,
                requires_human_auth=requires_human_auth,
            )
            self._tasks[task_id] = task

            # Register child relationship
            if parent_id:
                self._children.setdefault(parent_id, []).append(task_id)

            logger.info(f"Task enqueued: #{task_id} [{title}] -> {status.value}")
            await self._publish_event("task_created", task.to_dict())
            return task

    async def transition(self, task_id: str, new_status: TaskStatus, **kwargs) -> Optional[Task]:
        """Move a task to a new status with optional metadata."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.warning(f"Transition failed: Task #{task_id} not found.")
                return None

            old_status = task.status
            task.status = new_status

            if new_status in (TaskStatus.DONE, TaskStatus.FAILED):
                task.completed_at = datetime.now(timezone.utc).isoformat()

            if "result" in kwargs:
                task.output_payload["result"] = kwargs["result"]
            if "error" in kwargs:
                task.error_message = kwargs["error"]
            if "agent" in kwargs:
                task.assigned_agent = kwargs["agent"]

            logger.info(f"Task #{task_id}: {old_status.value} -> {new_status.value}")
            await self._publish_event("task_updated", task.to_dict())

            # On DONE, promote children
            if new_status == TaskStatus.DONE:
                await self._promote_children(task_id)

            return task

    async def block_task(self, task_id: str, reason: str):
        """Move task to BLOCKED and trigger human notification."""
        await self.transition(task_id, TaskStatus.BLOCKED, error=reason)
        logger.warning(f"Task #{task_id} BLOCKED: {reason}")

    async def resume_task(self, task_id: str):
        """Resume a BLOCKED task back to IN_PROGRESS."""
        await self.transition(task_id, TaskStatus.IN_PROGRESS)

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------
    def get_ready_tasks(self) -> List[Task]:
        return sorted(
            [t for t in self._tasks.values() if t.status == TaskStatus.READY],
            key=lambda t: t.execution_order,
        )

    def get_all_tasks(self) -> List[Task]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == status]

    def kanban_summary(self) -> Dict[str, int]:
        summary = {s.value: 0 for s in TaskStatus}
        for task in self._tasks.values():
            summary[task.status.value] += 1
        return summary

    def is_all_done(self) -> bool:
        if not self._tasks:
            return False
        return all(t.status in (TaskStatus.DONE, TaskStatus.FAILED) for t in self._tasks.values())

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------
    async def _promote_children(self, parent_id: str):
        """Promote child tasks to READY when their parent completes."""
        children = self._children.get(parent_id, [])
        for child_id in children:
            child = self._tasks.get(child_id)
            if child and child.status == TaskStatus.TODO:
                child.status = TaskStatus.READY
                logger.info(f"Dependency resolved: Task #{child_id} promoted to READY")
                await self._publish_event("task_updated", child.to_dict())

    async def _publish_event(self, event_type: str, payload: Dict[str, Any]):
        """Publish state change to Redis channel for real-time dashboard."""
        if self._redis:
            try:
                message = json.dumps({"event": event_type, "data": payload, "ts": datetime.now(timezone.utc).isoformat()})
                await self._redis.publish("apex1:kanban_events", message)
            except Exception as exc:
                logger.debug(f"Redis publish skipped (not connected): {exc}")

        # Call registered local callbacks (e.g., WebSocket broadcast)
        for cb in self._state_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event_type, payload)
                else:
                    cb(event_type, payload)
            except Exception as exc:
                logger.error(f"Kanban callback error: {exc}")

    def on_state_change(self, callback: Callable):
        """Register a callback for state change events."""
        self._state_change_callbacks.append(callback)
