"""
NEXUS-OMEGA (APEX-1) - Vector Memory Persistence Module
Manages long-term semantic memory using PostgreSQL + pgvector as primary,
with an automatic embedded file-backed SQLite storage fallback for portable/zero-config operation.
"""

import asyncio
from contextlib import contextmanager
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger("APEX1.Memory")


class MemoryStore:
    """
    Dual-Backend Memory Store:
    - Primary: PostgreSQL 16 with pgvector IVFFlat indexing.
    - Fallback: Embedded SQLite database for zero-config portable operation.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None
        self._use_sqlite = False
        self._sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "nexus_omega.db")

    @contextmanager
    def _sqlite_conn(self):
        """Context manager that ensures the SQLite connection is always closed cleanly."""
        os.makedirs(os.path.dirname(self._sqlite_path), exist_ok=True)
        conn = sqlite3.connect(self._sqlite_path)
        try:
            yield conn
        finally:
            conn.close()

    async def initialize(self):
        """Attempts PostgreSQL connection; falls back to embedded SQLite if unavailable."""
        try:
            import asyncpg  # type: ignore
            self._pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10, timeout=4.0)
            await self._ensure_postgres_schema()
            logger.info("MemoryStore initialized with PostgreSQL + pgvector backend.")
        except Exception as exc:
            logger.warning(f"PostgreSQL not reachable ({exc}). Activating embedded SQLite fallback.")
            self._pool = None
            self._use_sqlite = True
            await self._ensure_sqlite_schema()
            logger.info(f"MemoryStore active with file-backed SQLite at: {self._sqlite_path}")

    # ------------------------------------------------------------------
    # PostgreSQL Schema
    # ------------------------------------------------------------------
    async def _ensure_postgres_schema(self):
        schema_sql = """
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        CREATE EXTENSION IF NOT EXISTS "vector";

        CREATE TABLE IF NOT EXISTS agent_profiles (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(64) NOT NULL UNIQUE,
            role VARCHAR(64) NOT NULL,
            system_instruction TEXT NOT NULL,
            model_provider VARCHAR(32) NOT NULL DEFAULT 'openrouter',
            model_name VARCHAR(128) NOT NULL,
            temperature NUMERIC(3,2) NOT NULL DEFAULT 0.70,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS goals (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            title VARCHAR(255) NOT NULL,
            description TEXT,
            success_criteria JSONB NOT NULL DEFAULT '{}',
            is_completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            goal_id UUID REFERENCES goals(id) ON DELETE CASCADE,
            parent_task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
            assigned_agent_id UUID REFERENCES agent_profiles(id),
            title VARCHAR(255) NOT NULL,
            instruction TEXT NOT NULL,
            status VARCHAR(32) DEFAULT 'TODO',
            input_payload JSONB DEFAULT '{}',
            output_payload JSONB DEFAULT '{}',
            execution_order INT DEFAULT 1,
            requires_human_auth BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS tool_execution_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id VARCHAR(64),
            agent_id VARCHAR(64),
            tool_name VARCHAR(64) NOT NULL,
            input_parameters JSONB NOT NULL,
            output_response TEXT,
            is_error BOOLEAN DEFAULT FALSE,
            execution_latency_ms INT,
            executed_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS agent_memories (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            agent_id VARCHAR(64),
            content TEXT NOT NULL,
            embedding vector(1536),
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS parameter_learning_ledger (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            agent_id VARCHAR(64),
            metric_name VARCHAR(64) NOT NULL,
            variable_mutated VARCHAR(64) NOT NULL,
            previous_value TEXT NOT NULL,
            mutated_value TEXT NOT NULL,
            baseline_score NUMERIC(8,4) NOT NULL,
            observed_score NUMERIC(8,4) NOT NULL,
            hypothesis TEXT NOT NULL,
            is_adopted BOOLEAN NOT NULL DEFAULT FALSE,
            recorded_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        if not self._pool: return
        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)

    # ------------------------------------------------------------------
    # SQLite Schema Fallback
    # ------------------------------------------------------------------
    async def _ensure_sqlite_schema(self):
        def _sync_init():
            with self._sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_memories (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    content TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT
                )
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS tool_execution_logs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT,
                    agent_id TEXT,
                    tool_name TEXT NOT NULL,
                    input_parameters TEXT,
                    output_response TEXT,
                    is_error INTEGER DEFAULT 0,
                    execution_latency_ms INTEGER DEFAULT 0,
                    executed_at TEXT
                )
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS parameter_learning_ledger (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    metric_name TEXT NOT NULL,
                    variable_mutated TEXT NOT NULL,
                    previous_value TEXT NOT NULL,
                    mutated_value TEXT NOT NULL,
                    baseline_score REAL NOT NULL,
                    observed_score REAL NOT NULL,
                    hypothesis TEXT NOT NULL,
                    is_adopted INTEGER NOT NULL DEFAULT 0,
                    recorded_at TEXT
                )
                """)
                conn.commit()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_init)

    # ------------------------------------------------------------------
    # Public Memory API
    # ------------------------------------------------------------------
    async def store_memory(
        self,
        content: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> Optional[str]:
        """Persist a memory entry. Supports Postgres and SQLite fallback."""
        mem_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata or {})

        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO agent_memories (id, agent_id, content, embedding, metadata)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id
                        """,
                        mem_id, agent_id, content, embedding, meta_str
                    )
                    return str(row["id"])
            except Exception as exc:
                logger.error(f"Postgres memory store failed: {exc}")

        # SQLite fallback
        def _sync_store():
            with self._sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO agent_memories (id, agent_id, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (mem_id, agent_id, content, meta_str, now),
                )
                conn.commit()
            return mem_id

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_store)

    async def search_memories(self, query: str, limit: int = 5, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve memories relevant to a query."""
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT id, content, metadata FROM agent_memories WHERE content ILIKE $1 LIMIT $2",
                        f"%{query}%", limit
                    )
                    return [dict(r) for r in rows]
            except Exception:
                pass

        # SQLite keyword fallback
        def _sync_search():
            with self._sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, content, metadata_json, created_at FROM agent_memories WHERE content LIKE ? LIMIT ?",
                    (f"%{query}%", limit),
                )
                rows = cur.fetchall()
                return [{"id": r[0], "content": r[1], "metadata": json.loads(r[2]), "created_at": r[3]} for r in rows]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_search)

    async def log_tool_execution(
        self,
        tool_name: str,
        input_parameters: Dict[str, Any],
        output_response: str,
        is_error: bool = False,
        execution_latency_ms: int = 0,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        """Persist tool execution audit records."""
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        params_str = json.dumps(input_parameters)

        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO tool_execution_logs
                            (id, task_id, agent_id, tool_name, input_parameters, output_response, is_error, execution_latency_ms)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        log_id, task_id, agent_id, tool_name, params_str, output_response[:8000], is_error, execution_latency_ms
                    )
                    return
            except Exception as exc:
                logger.error(f"Postgres tool log failed: {exc}")

        # SQLite fallback
        def _sync_log():
            with self._sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO tool_execution_logs
                    (id, task_id, agent_id, tool_name, input_parameters, output_response, is_error, execution_latency_ms, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (log_id, task_id, agent_id, tool_name, params_str, output_response[:4000], int(is_error), execution_latency_ms, now),
                )
                conn.commit()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_log)

    async def persist_ledger_entry(
        self,
        experiment: Dict[str, Any],
        observed_score: float,
        is_adopted: bool,
        baseline_score: float,
        agent_id: Optional[str] = None,
    ):
        """Record scientific optimizer experiment in the persistent ledger."""
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO parameter_learning_ledger
                            (id, agent_id, metric_name, variable_mutated, previous_value, mutated_value,
                             baseline_score, observed_score, hypothesis, is_adopted)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        entry_id, agent_id, "composite_performance",
                        experiment["tested_variable"], str(experiment["previous_value"]),
                        str(experiment["mutated_value"]), baseline_score, observed_score,
                        experiment["hypothesis"], is_adopted
                    )
                    return
            except Exception as exc:
                logger.error(f"Postgres ledger persistence failed: {exc}")

        # SQLite fallback
        def _sync_persist():
            with self._sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO parameter_learning_ledger
                    (id, agent_id, metric_name, variable_mutated, previous_value, mutated_value,
                     baseline_score, observed_score, hypothesis, is_adopted, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entry_id, agent_id, "composite_performance", experiment["tested_variable"],
                     str(experiment["previous_value"]), str(experiment["mutated_value"]),
                     float(baseline_score), float(observed_score), experiment["hypothesis"],
                     int(is_adopted), now),
                )
                conn.commit()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_persist)

    async def get_ledger_history(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieve recent experiments from the parameter learning ledger."""
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM parameter_learning_ledger ORDER BY recorded_at DESC LIMIT $1", limit
                    )
                    return [dict(r) for r in rows]
            except Exception:
                pass

        def _sync_get_ledger():
            if not os.path.exists(self._sqlite_path):
                return []
            with self._sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, variable_mutated, previous_value, mutated_value, baseline_score,
                           observed_score, hypothesis, is_adopted, recorded_at
                    FROM parameter_learning_ledger ORDER BY recorded_at DESC LIMIT ?
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "variable_mutated": r[1],
                        "previous_value": r[2],
                        "mutated_value": r[3],
                        "baseline_score": r[4],
                        "observed_score": r[5],
                        "hypothesis": r[6],
                        "is_adopted": bool(r[7]),
                        "recorded_at": r[8],
                    }
                    for r in rows
                ]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_get_ledger)

    async def get_memory_count(self) -> int:
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT COUNT(*) FROM agent_memories")
                    return row[0]
            except Exception:
                pass

        def _sync_count():
            if not os.path.exists(self._sqlite_path):
                return 0
            with self._sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM agent_memories")
                return cur.fetchone()[0]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_count)

    async def close(self):
        if self._pool:
            await self._pool.close()
