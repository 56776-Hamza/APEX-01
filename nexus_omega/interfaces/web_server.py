"""
NEXUS-OMEGA (APEX-1) - FastAPI Web Server
Exposes REST + WebSocket API for the Kanban dashboard.
Serves the static web dashboard and provides real-time event streaming.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger("APEX1.WebServer")

# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------
class GoalRequest(BaseModel):
    title: str
    description: str = ""
    success_criteria: Dict[str, Any] = {}


class TaskActionRequest(BaseModel):
    task_id: str
    action: str  # resume | block | retry
    reason: Optional[str] = None


class CommandRequest(BaseModel):
    command: str


# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        payload = json.dumps(message)
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------
def create_app(supervisor=None) -> FastAPI:
    app = FastAPI(
        title="NEXUS-OMEGA APEX-1",
        description="Autonomous Multi-Agent Cognitive System Dashboard API",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store supervisor reference on app state
    app.state.supervisor = supervisor

    # -----------------------------------------------------------------------
    # Static Files — Web Dashboard
    # -----------------------------------------------------------------------
    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
    if os.path.exists(web_dir):
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

    # -----------------------------------------------------------------------
    # Routes: Dashboard
    # -----------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
    async def dashboard():
        index_path = os.path.join(web_dir, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>APEX-1 API Online</h1>")

    # -----------------------------------------------------------------------
    # Routes: Goals
    # -----------------------------------------------------------------------
    @app.get("/api/goals", tags=["Goals"])
    async def list_goals():
        sv = app.state.supervisor
        if not sv:
            return {"goals": []}
        return {"goals": [g.to_dict() for g in sv.kanban.get_goals()]}

    @app.post("/api/goals", tags=["Goals"])
    async def create_goal(req: GoalRequest, background_tasks: BackgroundTasks):
        sv = app.state.supervisor
        if not sv:
            raise HTTPException(status_code=503, detail="Supervisor not initialized")
        background_tasks.add_task(sv.ingest_high_level_goal, f"{req.title}: {req.description}")
        return {"status": "queued", "message": f"Goal '{req.title}' dispatched to supervisor."}

    # -----------------------------------------------------------------------
    # Routes: Tasks (Kanban)
    # -----------------------------------------------------------------------
    @app.get("/api/tasks", tags=["Tasks"])
    async def list_tasks():
        sv = app.state.supervisor
        if not sv:
            return {"tasks": [], "summary": {}}
        tasks = [t.to_dict() for t in sv.kanban.get_all_tasks()]
        return {"tasks": tasks, "summary": sv.kanban.kanban_summary()}

    @app.post("/api/tasks/action", tags=["Tasks"])
    async def task_action(req: TaskActionRequest, background_tasks: BackgroundTasks):
        sv = app.state.supervisor
        if not sv:
            raise HTTPException(status_code=503, detail="Supervisor not initialized")

        task = sv.kanban.get_task(req.task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found")

        if req.action == "resume":
            background_tasks.add_task(sv.kanban.resume_task, req.task_id)
            return {"status": "ok", "message": f"Task {req.task_id} resuming."}
        elif req.action == "block":
            background_tasks.add_task(sv.kanban.block_task, req.task_id, req.reason or "Manual block")
            return {"status": "ok", "message": f"Task {req.task_id} blocked."}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    # -----------------------------------------------------------------------
    # Routes: System Metrics
    # -----------------------------------------------------------------------
    @app.get("/api/metrics", tags=["Metrics"])
    async def system_metrics():
        sv = app.state.supervisor
        if not sv:
            return {}

        mem_count = 0
        if hasattr(sv, "memory") and sv.memory:
            mem_count = await sv.memory.get_memory_count()

        return {
            "kanban_summary": sv.kanban.kanban_summary(),
            "optimizer_stats": sv.optimizer.get_stats(),
            "memory_entries": mem_count,
            "uptime_since": sv.started_at,
            "model": sv.config.BASE_MODEL,
            "status": "ACTIVE",
        }

    @app.get("/api/optimizer/ledger", tags=["Optimizer"])
    async def optimizer_stats():
        sv = app.state.supervisor
        if not sv:
            return {}
        return sv.optimizer.get_stats()

    @app.get("/api/ledger/history", tags=["Optimizer"])
    async def ledger_history():
        sv = app.state.supervisor
        if not sv or not hasattr(sv, "memory") or not sv.memory:
            return {"history": []}
        history = await sv.memory.get_ledger_history(limit=25)
        return {"history": history}

    @app.get("/api/agents", tags=["Swarm"])
    async def list_agent_profiles():
        sv = app.state.supervisor
        if not sv:
            return {"agents": []}
        return {"agents": getattr(sv, "profiles", [])}

    # -----------------------------------------------------------------------
    # Routes: Quick Command
    # -----------------------------------------------------------------------
    @app.post("/api/command", tags=["Control"])
    async def dispatch_command(req: CommandRequest, background_tasks: BackgroundTasks):
        sv = app.state.supervisor
        if not sv:
            raise HTTPException(status_code=503, detail="Supervisor not initialized")
        background_tasks.add_task(sv.ingest_high_level_goal, req.command)
        return {"status": "dispatched", "command": req.command}

    # -----------------------------------------------------------------------
    # WebSocket: Real-Time Kanban Events
    # -----------------------------------------------------------------------
    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        await ws_manager.connect(websocket)
        # Register kanban broadcast on supervisor
        sv = app.state.supervisor
        if sv:
            sv.kanban.on_state_change(
                lambda event, data: asyncio.create_task(
                    ws_manager.broadcast({"event": event, "data": data})
                )
            )
        try:
            while True:
                data = await websocket.receive_text()
                # Echo heartbeat
                if data == "ping":
                    await websocket.send_text(json.dumps({"event": "pong", "ts": datetime.now(timezone.utc).isoformat()}))
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    # -----------------------------------------------------------------------
    # WebSocket: Live Agent Log Stream
    # -----------------------------------------------------------------------
    @app.websocket("/ws/logs")
    async def websocket_logs(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                await asyncio.sleep(30)  # Keep alive
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return app


async def broadcast_log_event(message: str, level: str = "INFO"):
    """Called by supervisor to broadcast live log messages to dashboard."""
    await ws_manager.broadcast({
        "event": "log",
        "level": level,
        "message": message,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
