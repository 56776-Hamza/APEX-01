"""
NEXUS-OMEGA (APEX-1) - Tool: Autonomous File Operations
Provides local filesystem exploration, file reading, code writing,
and file search capabilities for swarm workers.
"""

import asyncio
import os
import glob
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("APEX1.Tool.FileOps")


async def read_file(filepath: str, max_bytes: int = 50000) -> Dict[str, Any]:
    """Reads content from a local file."""
    try:
        if not os.path.exists(filepath):
            return {"success": False, "content": "", "error": f"File '{filepath}' does not exist"}

        def _sync_read():
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read(max_bytes)

        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, _sync_read)
        return {"success": True, "content": content, "error": None}
    except Exception as exc:
        return {"success": False, "content": "", "error": str(exc)}


async def write_file(filepath: str, content: str, mode: str = "w") -> Dict[str, Any]:
    """Writes or appends content to a local file, creating parent directories if needed."""
    try:
        def _sync_write():
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, mode, encoding="utf-8") as f:
                f.write(content)
            return os.path.getsize(filepath)

        loop = asyncio.get_event_loop()
        size = await loop.run_in_executor(None, _sync_write)
        logger.info(f"[FileOps] Wrote {size} bytes to '{filepath}'")
        return {"success": True, "bytes_written": size, "filepath": filepath}
    except Exception as exc:
        logger.error(f"[FileOps] Write error for '{filepath}': {exc}")
        return {"success": False, "bytes_written": 0, "error": str(exc)}


async def list_files(directory: str = ".", pattern: str = "*.*", recursive: bool = False) -> List[str]:
    """Lists files matching a pattern in a directory."""
    try:
        def _sync_list():
            search_path = os.path.join(directory, "**" if recursive else "", pattern)
            return glob.glob(search_path, recursive=recursive)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_list)
    except Exception as exc:
        logger.error(f"[FileOps] List error: {exc}")
        return []
