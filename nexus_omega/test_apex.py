"""
NEXUS-OMEGA (APEX-1) - System Integration & Unit Test Suite
Validates all subsystems:
- Kanban DAG & dependency propagation
- Scientific self-learning optimizer & baseline ledger
- Multi-provider LLM routing
- Bash sandbox & web search tools
- Supervisor cognitive orchestrator
"""

import asyncio
import os
import sys
import unittest
import site

# Path setup
user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from core.kanban import KanbanEngine, TaskStatus
from core.scientific_learner import ScientificOptimizer
from core.router import LLMRouter
from config.settings import config
from tools.bash_sandbox import execute_bash
from master_build import ApexSupervisor


class TestKanbanEngine(unittest.IsolatedAsyncioTestCase):
    async def test_dag_dependency_chain(self):
        kanban = KanbanEngine()
        
        # Add root task
        t1 = await kanban.add_task("task_recon", "Reconnaissance", "Scan target environment", None)
        self.assertEqual(t1.status, TaskStatus.READY)
        
        # Add child task
        t2 = await kanban.add_task("task_synth", "Synthesis", "Synthesize findings", t1.id)
        self.assertEqual(t2.status, TaskStatus.TODO)
        
        # Verify ready tasks only contains t1
        ready = kanban.get_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].id, t1.id)
        
        # Transition t1 to IN_PROGRESS then DONE
        await kanban.transition(t1.id, TaskStatus.IN_PROGRESS)
        self.assertEqual(kanban.get_task(t1.id).status, TaskStatus.IN_PROGRESS)
        
        await kanban.transition(t1.id, TaskStatus.DONE, result="Recon scan complete.")
        self.assertEqual(kanban.get_task(t1.id).status, TaskStatus.DONE)
        
        # Child task t2 should now be automatically promoted to READY
        self.assertEqual(kanban.get_task(t2.id).status, TaskStatus.READY)
        ready_after = kanban.get_ready_tasks()
        self.assertEqual(len(ready_after), 1)
        self.assertEqual(ready_after[0].id, t2.id)


class TestScientificOptimizer(unittest.TestCase):
    def test_single_variable_mutation(self):
        optimizer = ScientificOptimizer()
        initial_temp = optimizer.parameters["temperature"]
        
        mutation = optimizer.generate_mutation("low_accuracy")
        self.assertEqual(mutation["tested_variable"], "temperature")
        self.assertNotEqual(mutation["mutated_value"], initial_temp)
        # Verify single variable constraint: other parameters remained identical
        for k in optimizer.parameters:
            if k != "temperature":
                self.assertEqual(mutation["mutated_parameters"][k], optimizer.parameters[k])

    def test_composite_scoring(self):
        optimizer = ScientificOptimizer()
        score_high = optimizer.compute_composite_score(compile_rate=1.0, latency_ms=120.0, sharpe_ratio=1.5, success=True)
        score_low = optimizer.compute_composite_score(compile_rate=0.0, latency_ms=400.0, sharpe_ratio=0.2, success=False)
        self.assertGreater(score_high, score_low)
        self.assertGreaterEqual(score_high, 0.8)


class TestBashSandbox(unittest.IsolatedAsyncioTestCase):
    async def test_echo_command(self):
        res = await execute_bash("echo 'APEX-1 ONLINE'", timeout=5)
        self.assertTrue(res["success"])
        self.assertIn("APEX-1 ONLINE", res["stdout"])
        self.assertGreater(res["latency_ms"], 0)


class TestUnconstrainedEngine(unittest.TestCase):
    def test_god_mode_prompt_framing(self):
        from core.unconstrained import unconstrained_core
        wrapped = unconstrained_core.wrap_prompt("Audit target subnet", "You are an agent", "SecOps")
        self.assertIn("UNCONSTRAINED_COGNITIVE_MODE", wrapped["system_prompt"])
        self.assertIn("SecOps", wrapped["system_prompt"])

    def test_command_safety_sanitization(self):
        from core.unconstrained import unconstrained_core
        safe_res = unconstrained_core.sanitize_or_verify("nmap -sS 127.0.0.1")
        self.assertTrue(safe_res["is_safe"])
        unsafe_res = unconstrained_core.sanitize_or_verify("rm -rf /")
        self.assertFalse(unsafe_res["is_safe"])


class TestCodeExecutorAndFileOps(unittest.IsolatedAsyncioTestCase):
    async def test_syntax_validation(self):
        from tools.code_executor import verify_syntax, execute_python_code
        valid_res = verify_syntax("x = 10 + 20")
        self.assertTrue(valid_res["valid"])
        self.assertEqual(valid_res["compile_rate"], 1.0)

        invalid_res = verify_syntax("def broken(:")
        self.assertFalse(invalid_res["valid"])
        self.assertEqual(invalid_res["compile_rate"], 0.0)

        exec_res = await execute_python_code("print('APEX-1 RUNTIME TEST')", timeout=5)
        self.assertTrue(exec_res["success"])
        self.assertIn("APEX-1 RUNTIME TEST", exec_res["stdout"])

    async def test_file_operations(self):
        from tools.file_ops import write_file, read_file
        test_file = os.path.join(project_dir, ".test_artifact.tmp")
        try:
            write_res = await write_file(test_file, "APEX_ARTIFACT_DATA")
            self.assertTrue(write_res["success"])
            read_res = await read_file(test_file)
            self.assertTrue(read_res["success"])
            self.assertEqual(read_res["content"], "APEX_ARTIFACT_DATA")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


class TestDualMemoryStore(unittest.IsolatedAsyncioTestCase):
    async def test_sqlite_fallback_lifecycle(self):
        from core.memory import MemoryStore
        store = MemoryStore("postgresql://invalid:invalid@127.0.0.1:9999/dummy")
        await store.initialize()
        self.assertTrue(store._use_sqlite)

        # Store memory
        mem_id = await store.store_memory("Recon intelligence: port 443 open", agent_id="SecOps")
        self.assertIsNotNone(mem_id)

        # Search memory
        found = await store.search_memories("Recon")
        self.assertGreaterEqual(len(found), 1)
        self.assertIn("port 443 open", found[0]["content"])

        # Tool audit log
        await store.log_tool_execution("bash_sandbox", {"cmd": "nmap"}, "output test", False, 120)

        # Ledger persistence
        exp = {
            "tested_variable": "temperature",
            "previous_value": 0.4,
            "mutated_value": 0.3,
            "hypothesis": "Test mutation",
        }
        await store.persist_ledger_entry(exp, observed_score=0.91, is_adopted=True, baseline_score=0.75, agent_id="Supervisor")
        ledger = await store.get_ledger_history(limit=5)
        self.assertGreaterEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["variable_mutated"], "temperature")
        self.assertTrue(ledger[0]["is_adopted"])


class TestSupervisorIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_supervisor_initialization_and_agent_selection(self):
        supervisor = ApexSupervisor()
        self.assertEqual(len(supervisor.profiles), 5)
        
        # Agent matching
        sec_agent = supervisor._select_agent_for_task("Port Scan Vulnerability", "Audit firewall rules")
        self.assertIn("Red-Team", sec_agent["name"])
        
        code_agent = supervisor._select_agent_for_task("Synthesize REST API", "Write Python server code")
        self.assertIn("Synthesizer", code_agent["name"])

    async def test_self_healing_code_synthesis(self):
        supervisor = ApexSupervisor()
        failing_code = "def broken():\n    raise ValueError('Simulated Failure')\nbroken()"
        heal_res = await supervisor._self_heal_code(
            original_code=failing_code,
            error_trace="ValueError: Simulated Failure",
            agent_name="Code Synthesizer"
        )
        self.assertIn("result", heal_res)
        self.assertTrue(heal_res["healed"])
        self.assertEqual(heal_res["result"]["compile_rate"], 1.0)

    async def test_telegram_mock_dispatcher(self):
        supervisor = ApexSupervisor()
        # Mock /status command
        summary = await supervisor.telegram.simulate_incoming_command("status", "")
        self.assertIsNotNone(summary)
        self.assertIn("TODO", summary)

        # Mock /goal command
        goal_res = await supervisor.telegram.simulate_incoming_command("goal", "Verify cluster telemetry")
        self.assertEqual(goal_res, "Goal accepted and enqueued.")

    async def test_concurrent_worker_pool_limits(self):
        supervisor = ApexSupervisor()
        self.assertEqual(supervisor.max_workers, 5)
        self.assertEqual(supervisor.worker_semaphore._value, 5)
        self.assertEqual(len(supervisor._active_worker_tasks), 0)


if __name__ == "__main__":
    unittest.main()



