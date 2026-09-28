"""
NEXUS-OMEGA (APEX-1) - Tool Execution Suite: Bash Sandbox
Executes arbitrary shell commands in an isolated subprocess.
Captures stdout, stderr, exit code, and execution latency.
"""

import asyncio
import logging
import time
from typing import Dict, Any

logger = logging.getLogger("APEX1.Tool.Bash")


async def execute_bash(command: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Executes a shell command asynchronously.

    Args:
        command: Shell command string to execute.
        timeout: Max execution seconds before termination.

    Returns:
        Dict with keys: stdout, stderr, exit_code, latency_ms, success
    """
    logger.info(f"[Bash] Executing: {command[:120]}")
    start = time.monotonic()

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(f"[Bash] Command timed out after {timeout}s: {command[:60]}")
            return {
                "stdout": "",
                "stderr": f"[TIMEOUT] Command exceeded {timeout}s",
                "exit_code": -1,
                "latency_ms": elapsed_ms,
                "success": False,
            }

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        exit_code = process.returncode

        success = exit_code == 0
        if not success:
            logger.warning(f"[Bash] Non-zero exit ({exit_code}): {stderr[:200]}")

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "latency_ms": elapsed_ms,
            "success": success,
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"[Bash] Execution error: {exc}")
        return {
            "stdout": "",
            "stderr": str(exc),
            "exit_code": -1,
            "latency_ms": elapsed_ms,
            "success": False,
        }


def format_result(result: Dict[str, Any]) -> str:
    """Human-readable summary of bash execution output."""
    if result["success"]:
        return result["stdout"] or "[SUCCESS: No output]"
    return f"[EXIT {result['exit_code']}] {result['stderr'] or result['stdout'] or 'Unknown error'}"
