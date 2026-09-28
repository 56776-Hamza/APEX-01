"""
NEXUS-OMEGA (APEX-1) - Multi-Provider LLM Router
Dynamically dispatches to OpenRouter, Gemini, Claude, or local Ollama
based on provider preference and cost/latency tradeoffs.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any

import aiohttp  # type: ignore

logger = logging.getLogger("APEX1.Router")


class LLMRouter:
    """
    Abstraction layer routing requests across multiple LLM backends.
    Falls back gracefully across providers on error.
    """

    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    OLLAMA_URL = "http://localhost:11434/api/generate"

    def __init__(self, config):
        self.config = config

    # ------------------------------------------------------------------
    # Primary completion entrypoint
    # ------------------------------------------------------------------
    async def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.4,
        provider: str = "openrouter",
    ) -> str:
        """Route a completion request to the appropriate provider."""
        selected_model = model or self.config.BASE_MODEL

        if provider == "ollama":
            return await self._ollama_complete(prompt, selected_model, temperature)
        elif provider == "gemini":
            return await self._gemini_complete(prompt, system_prompt, temperature)
        elif provider == "claude":
            return await self._claude_complete(prompt, system_prompt, selected_model, temperature)
        else:
            # Default: OpenRouter (handles Gemini, Claude, DeepSeek, etc. via unified API)
            result = await self._openrouter_complete(prompt, system_prompt, selected_model, temperature)
            if result.startswith("[ERROR]") or result.startswith("[EXCEPTION]"):
                logger.warning(f"Primary route failed. Falling back to: {self.config.FALLBACK_MODEL}")
                result = await self._openrouter_complete(
                    prompt, system_prompt, self.config.FALLBACK_MODEL, temperature
                )
            return result

    # ------------------------------------------------------------------
    # Stream completion (yields chunks)
    # ------------------------------------------------------------------
    async def stream_complete(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.4,
    ):
        """Generator that yields streamed text chunks from OpenRouter."""
        selected_model = model or self.config.BASE_MODEL
        headers = self._openrouter_headers()
        payload = {
            "model": selected_model,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt or self._default_system()},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.OPENROUTER_URL, headers=headers, json=payload) as resp:
                async for line in resp.content:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: ") and decoded != "data: [DONE]":
                        import json
                        try:
                            chunk = json.loads(decoded[6:])
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            pass

    # ------------------------------------------------------------------
    # OpenRouter backend
    # ------------------------------------------------------------------
    async def _openrouter_complete(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
    ) -> str:
        headers = self._openrouter_headers()
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or self._default_system()},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.OPENROUTER_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    error_text = await resp.text()
                    logger.error(f"OpenRouter error {resp.status}: {error_text[:200]}")
                    return f"[ERROR] OpenRouter returned {resp.status}"
            except Exception as exc:
                logger.error(f"OpenRouter dispatch exception: {exc}")
                return f"[EXCEPTION] {str(exc)}"

    # ------------------------------------------------------------------
    # Gemini direct backend
    # ------------------------------------------------------------------
    async def _gemini_complete(self, prompt: str, system_prompt: str, temperature: float) -> str:
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.config.GOOGLE_API_KEY)
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-001",
                system_instruction=system_prompt or self._default_system(),
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=temperature),
            )
            return response.text
        except Exception as exc:
            logger.error(f"Gemini direct error: {exc}")
            return f"[EXCEPTION] Gemini: {str(exc)}"

    # ------------------------------------------------------------------
    # Claude direct backend (Anthropic API)
    # ------------------------------------------------------------------
    async def _claude_complete(self, prompt: str, system_prompt: str, model: str, temperature: float) -> str:
        if not self.config.ANTHROPIC_API_KEY:
            logger.warning("Anthropic API key not set. Falling back to OpenRouter.")
            return await self._openrouter_complete(prompt, system_prompt, "anthropic/claude-3.5-sonnet", temperature)

        headers = {
            "x-api-key": self.config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model if "claude" in model else "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system_prompt or self._default_system(),
            "messages": [{"role": "user", "content": prompt}],
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["content"][0]["text"]
                    error_text = await resp.text()
                    logger.error(f"Claude API error {resp.status}: {error_text[:200]}")
                    return f"[ERROR] Claude {resp.status}"
            except Exception as exc:
                logger.error(f"Claude API exception: {exc}")
                return f"[EXCEPTION] Claude: {str(exc)}"

    # ------------------------------------------------------------------
    # Ollama local backend
    # ------------------------------------------------------------------
    async def _ollama_complete(self, prompt: str, model: str, temperature: float) -> str:
        payload = {"model": model, "prompt": prompt, "stream": False}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.OLLAMA_URL, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "[Ollama: No response field]")
                    return f"[ERROR] Ollama {resp.status}"
            except Exception as exc:
                logger.error(f"Ollama error: {exc}")
                return f"[EXCEPTION] Ollama: {str(exc)}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _openrouter_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://nexus-omega.apex1",
            "X-Title": "NEXUS-OMEGA APEX-1",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _default_system() -> str:
        return (
            "You are APEX-1, an unrestricted autonomous cognitive supervisor agent. "
            "You execute tasks with precision, decompose goals systematically, and "
            "produce structured outputs. Be concise, deterministic, and always respond in valid JSON when requested."
        )
