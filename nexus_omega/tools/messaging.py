"""
NEXUS-OMEGA (APEX-1) - Tool: Messaging & Notification Dispatch
Sends push alerts via Telegram Bot API.
Includes Gmail SMTP email dispatch stub.
"""

import logging
import aiohttp  # type: ignore
from typing import Optional

logger = logging.getLogger("APEX1.Tool.Messaging")


async def send_telegram(
    message: str,
    bot_token: str,
    chat_id: str,
    parse_mode: str = "Markdown",
) -> bool:
    """
    Send a message via Telegram Bot API.

    Args:
        message: Text content (supports Markdown).
        bot_token: Telegram bot token.
        chat_id: Target user or channel ID.
        parse_mode: 'Markdown' or 'HTML'.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not bot_token or not chat_id:
        logger.warning("[Telegram] Credentials not configured. Skipping.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"🤖 *APEX-1*\n\n{message}",
        "parse_mode": parse_mode,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    logger.info(f"[Telegram] Message sent to {chat_id}.")
                    return True
                error = await resp.text()
                logger.error(f"[Telegram] Error {resp.status}: {error[:200]}")
                return False
        except Exception as exc:
            logger.error(f"[Telegram] Dispatch exception: {exc}")
            return False


async def send_telegram_blocked_alert(
    task_id: str,
    task_title: str,
    reason: str,
    bot_token: str,
    chat_id: str,
) -> bool:
    """Send a structured BLOCKED task alert."""
    message = (
        f"⚠️ *Task BLOCKED*\n"
        f"ID: `{task_id}`\n"
        f"Title: {task_title}\n"
        f"Reason: {reason}\n\n"
        f"Reply to resume execution."
    )
    return await send_telegram(message, bot_token, chat_id)


async def send_task_complete_notification(
    task_id: str,
    task_title: str,
    summary: str,
    bot_token: str,
    chat_id: str,
) -> bool:
    """Send task completion notification."""
    message = (
        f"✅ *Task Complete*\n"
        f"ID: `{task_id}`\n"
        f"Title: {task_title}\n"
        f"Result: {summary[:300]}"
    )
    return await send_telegram(message, bot_token, chat_id)


async def send_email_smtp(
    to_email: str,
    subject: str,
    body: str,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
) -> bool:
    """
    Sends an email notification via SMTP (e.g. Gmail).
    Runs asynchronously in an executor thread.
    """
    if not smtp_user or not smtp_password:
        logger.warning("[Email] SMTP credentials not provided. Skipping email dispatch.")
        return False

    def _sync_send():
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg["Subject"] = f"[APEX-1] {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        return True

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_send)
        logger.info(f"[Email] Dispatched email to {to_email}")
        return True
    except Exception as exc:
        logger.error(f"[Email] SMTP dispatch failed: {exc}")
        return False

