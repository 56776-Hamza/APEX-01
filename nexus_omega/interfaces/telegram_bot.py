"""
NEXUS-OMEGA (APEX-1) - Telegram Bot Interface
Listens for commands from authorized users, dispatches goals to the supervisor,
and forwards BLOCKED task alerts and completion notifications.
"""

import asyncio
import logging
from typing import Optional, Callable

logger = logging.getLogger("APEX1.Telegram")


class TelegramBotInterface:
    """
    Telegram bot interface for APEX-1.
    Listens for user commands and forwards them to the supervisor.
    Sends push notifications for task state changes.

    Commands:
        /goal <text>     - Submit a new autonomous goal
        /status          - Show Kanban board summary
        /resume <id>     - Resume a BLOCKED task
        /kill            - Emergency stop
    """

    def __init__(self, config, supervisor_callback: Optional[Callable] = None):
        self.config = config
        self.supervisor_callback = supervisor_callback
        self._app = None

    def _is_authorized(self, update) -> bool:
        if not update or not update.message or not update.message.from_user:
            return False
        if not getattr(self.config, 'TELEGRAM_AUTHORIZED_USERS', None):
            return True
        return str(update.message.from_user.id) in self.config.TELEGRAM_AUTHORIZED_USERS

    async def start(self):
        """Start the Telegram bot long-polling listener."""
        if not self.config.TELEGRAM_BOT_TOKEN:
            logger.warning("[Telegram] BOT_TOKEN not set. Interface disabled.")
            return

        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, filters

            self._app = (
                Application.builder().token(self.config.TELEGRAM_BOT_TOKEN).build()
            )

            self._app.add_handler(CommandHandler("start", self._cmd_start))
            self._app.add_handler(CommandHandler("goal", self._cmd_goal))
            self._app.add_handler(CommandHandler("status", self._cmd_status))
            self._app.add_handler(CommandHandler("resume", self._cmd_resume))
            self._app.add_handler(CommandHandler("kill", self._cmd_kill))
            self._app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
            )

            logger.info("[Telegram] Bot started. Listening for commands...")
            await self._app.initialize()
            await self._app.start()
            if self._app.updater:
                await self._app.updater.start_polling(drop_pending_updates=True)

        except Exception as exc:
            logger.error(f"[Telegram] Failed to start: {exc}")

    async def stop(self):
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    # ------------------------------------------------------------------
    # Command Handlers
    # ------------------------------------------------------------------
    async def _cmd_start(self, update, context):
        if not self._is_authorized(update):
            return
        await update.message.reply_text(
            "🤖 *NEXUS-OMEGA APEX-1* online.\n"
            "Use /goal <text> to submit an autonomous directive.\n"
            "Use /status to view the Kanban board.",
            parse_mode="Markdown",
        )

    async def _cmd_goal(self, update, context):
        if not self._is_authorized(update):
            return
        goal_text = " ".join(context.args)
        if not goal_text:
            await update.message.reply_text("Usage: /goal <your goal description>")
            return
        await update.message.reply_text(f"⚡ Goal accepted. Dispatching to supervisor...\n`{goal_text}`", parse_mode="Markdown")
        if self.supervisor_callback:
            asyncio.create_task(self.supervisor_callback("goal", goal_text))

    async def _cmd_status(self, update, context):
        if not self._is_authorized(update):
            return
        if self.supervisor_callback:
            summary = await self.supervisor_callback("status", None)
            await update.message.reply_text(f"📊 *Kanban Status*\n```\n{summary}\n```", parse_mode="Markdown")

    async def _cmd_resume(self, update, context):
        if not self._is_authorized(update):
            return
        task_id = " ".join(context.args)
        if not task_id:
            await update.message.reply_text("Usage: /resume <task_id>")
            return
        await update.message.reply_text(f"▶️ Resuming task `{task_id}`...", parse_mode="Markdown")
        if self.supervisor_callback:
            asyncio.create_task(self.supervisor_callback("resume", task_id))

    async def _cmd_kill(self, update, context):
        if not self._is_authorized(update):
            return
        await update.message.reply_text("🛑 Emergency stop signal sent.")
        if self.supervisor_callback:
            asyncio.create_task(self.supervisor_callback("kill", None))

    async def _handle_text(self, update, context):
        if not self._is_authorized(update):
            return
        # Treat freeform text as goal submission
        text = update.message.text
        await update.message.reply_text(f"📨 Treating as goal directive...", parse_mode="Markdown")
        if self.supervisor_callback:
            asyncio.create_task(self.supervisor_callback("goal", text))

        return True

    async def simulate_incoming_command(self, action: str, payload: str = ""):
        """Allows test suites or headless environments to simulate incoming Telegram directives."""
        logger.info(f"[Telegram Mock] Simulating incoming command: /{action} {payload}")
        if self.supervisor_callback:
            return await self.supervisor_callback(action, payload)
        return None

