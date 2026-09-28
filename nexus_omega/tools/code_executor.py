"""
NEXUS-OMEGA (APEX-1) - Tool: Code Execution & Synthesis Engine
Compiles, lints, and executes Python code snippets.
Measures compilation rates and execution telemetry for the scientific learner.
"""

import ast
import asyncio
import logging
import os
import sys
import tempfile
import time
from typing import Dict, Any

logger = logging.getLogger("APEX1.Tool.CodeExecutor")


def verify_syntax(code: str) -> Dict[str, Any]:
    """
    Statically analyzes code syntax using AST parsing.
    Returns compile_rate = 1.0 on success, 0.0 on SyntaxError.
    """
    try:
        ast.parse(code)
        compile(code, "<apex_snippet>", "exec")
        return {"valid": True, "compile_rate": 1.0, "error": None}
    except SyntaxError as err:
        return {
            "valid": False,
            "compile_rate": 0.0,
            "error": f"SyntaxError at line {err.lineno}: {err.msg}",
        }
    except Exception as exc:
        return {"valid": False, "compile_rate": 0.0, "error": str(exc)}


async def execute_python_code(code: str, timeout: int = 20) -> Dict[str, Any]:
    """
    Executes Python code in an isolated subprocess.
    Captures stdout, stderr, execution latency, and compilation rate.
    """
    # 1. First verify static syntax
    syntax_check = verify_syntax(code)
    if not syntax_check["valid"]:
        logger.warning(f"[CodeExecutor] Syntax verification failed: {syntax_check['error']}")
        return {
            "success": False,
            "stdout": "",
            "stderr": syntax_check["error"],
            "compile_rate": 0.0,
            "latency_ms": 0,
        }

    # 2. Write to temporary script
    start = time.monotonic()
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            temp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "stdout": "",
                "stderr": f"[TIMEOUT] Code execution timed out after {timeout}s",
                "compile_rate": 1.0,
                "latency_ms": elapsed_ms,
            }

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        success = process.returncode == 0

        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": process.returncode,
            "compile_rate": 1.0 if success else 0.5,
            "latency_ms": elapsed_ms,
        }

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "stdout": "",
            "stderr": str(exc),
            "compile_rate": 0.0,
            "latency_ms": elapsed_ms,
        }
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
