"""
NEXUS-OMEGA (APEX-1) - Core Configuration Module
Loads environment variables and provides a unified settings object.
"""

import os
import sys
import site
from dataclasses import dataclass, field

# Ensure user site-packages is included in sys.path
user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass


@dataclass
class SystemConfig:
    # --- LLM Provider Keys ---
    OPENROUTER_API_KEY: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    GOOGLE_API_KEY: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    ANTHROPIC_API_KEY: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # --- Model Selection ---
    BASE_MODEL: str = field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "google/gemini-2.0-flash-001"))
    FALLBACK_MODEL: str = field(default_factory=lambda: os.getenv("FALLBACK_MODEL", "deepseek/deepseek-chat"))

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    TELEGRAM_AUTHORIZED_USER_ID: str = field(default_factory=lambda: os.getenv("TELEGRAM_AUTHORIZED_USER_ID", ""))

    # --- Database ---
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres:apexpassword@localhost:5432/nexus_omega")
    )

    # --- Redis ---
    REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # --- LiveKit ---
    LIVEKIT_URL: str = field(default_factory=lambda: os.getenv("LIVEKIT_URL", "wss://localhost:7880"))
    LIVEKIT_API_KEY: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY", ""))
    LIVEKIT_API_SECRET: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", ""))

    # --- Web Dashboard ---
    WEB_HOST: str = field(default_factory=lambda: os.getenv("WEB_HOST", "0.0.0.0"))
    WEB_PORT: int = field(default_factory=lambda: int(os.getenv("WEB_PORT", "8000")))

    # --- Behavior ---
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    MAX_CONCURRENT_WORKERS: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_WORKERS", "5")))
    TASK_POLL_INTERVAL: float = field(default_factory=lambda: float(os.getenv("TASK_POLL_INTERVAL_SECONDS", "2")))


# Singleton
config = SystemConfig()
