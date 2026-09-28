"""
NEXUS-OMEGA (APEX-1) - Tool: Live Web Intelligence (DuckDuckGo)
Performs unconstrained web searches returning structured result summaries.
"""

import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger("APEX1.Tool.Search")


async def search_web(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Execute a live DuckDuckGo search and return structured results.

    Args:
        query: The search query string.
        max_results: Number of results to return.

    Returns:
        List of dicts with keys: title, href, body
    """
    logger.info(f"[Search] Query: {query[:100]} | max_results={max_results}")
    try:
        # Run in thread pool since duckduckgo_search is sync
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_search, query, max_results)
        logger.info(f"[Search] Got {len(results)} results.")
        return results
    except Exception as exc:
        logger.error(f"[Search] Error: {exc}")
        return [{"title": "Search Error", "href": "", "body": str(exc)}]


def _sync_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Synchronous DuckDuckGo search (run in executor)."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def format_results(results: List[Dict[str, Any]]) -> str:
    """Format search results into a readable summary string."""
    if not results:
        return "[No results found]"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.get('title', 'N/A')}**")
        lines.append(f"   URL: {r.get('href', '')}")
        body = r.get("body", "").strip()
        if body:
            lines.append(f"   {body[:200]}")
        lines.append("")
    return "\n".join(lines)
