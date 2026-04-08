"""Telegram notification module."""

import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self) -> None:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            self._bot = Bot(token=TELEGRAM_BOT_TOKEN)
            self._chat_id = TELEGRAM_CHAT_ID
            self._enabled = True
        else:
            self._bot = None
            self._chat_id = None
            self._enabled = False
            logger.warning("Telegram not configured — notifications disabled")

    async def _send(self, text: str) -> None:
        if not self._enabled:
            logger.info("[Telegram] %s", text)
            return
        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            logger.error("Telegram send failed: %s", e)

    # ─── Message types ───────────────────────────────────────────────────────

    async def send_bet_placed(
        self,
        periode: str,
        numbers: list[str],
        bet_per_number: int,
        total_bet: int,
        martingale_level: int,
        analysis: str = "",
        dry_run: bool = False,
    ) -> None:
        mode = "[DRY RUN] " if dry_run else ""
        numbers_str = " ".join(f"<b>{n}</b>" for n in numbers)
        text = (
            f"{mode}🎯 <b>Bet Placed — Periode {periode}</b>\n"
            f"Numbers: {numbers_str}\n"
            f"Bet: Rp{bet_per_number:,}/number | Total: Rp{total_bet:,}\n"
            f"Martingale Level: {martingale_level}\n"
        )
        if analysis:
            text += f"Analysis: <i>{analysis[:200]}</i>"
        await self._send(text)

    async def send_result(
        self,
        periode: str,
        draw_result: str,
        won: bool,
        winning_number: Optional[str],
        win_amount: int,
        wagered: int,
        consecutive_losses: int,
        daily_loss: int,
    ) -> None:
        if won:
            text = (
                f"✅ <b>WIN — Periode {periode}</b>\n"
                f"Draw Result: <b>{draw_result}</b> | Matched: <b>{winning_number}</b>\n"
                f"Won: Rp{win_amount:,} | Wagered: Rp{wagered:,}\n"
                f"Net: +Rp{win_amount - wagered:,}\n"
                f"Daily Loss: Rp{daily_loss:,}"
            )
        else:
            text = (
                f"❌ <b>LOSS — Periode {periode}</b>\n"
                f"Draw Result: <b>{draw_result}</b>\n"
                f"Wagered: Rp{wagered:,} | Consecutive Losses: {consecutive_losses}\n"
                f"Daily Loss: Rp{daily_loss:,}"
            )
        await self._send(text)

    async def send_daily_summary(
        self,
        date: str,
        total_bets: int,
        total_wagered: int,
        total_won: int,
        win_count: int,
        loss_count: int,
        final_balance: Optional[int] = None,
    ) -> None:
        net = total_won - total_wagered
        net_str = f"+Rp{net:,}" if net >= 0 else f"-Rp{abs(net):,}"
        win_rate = (win_count / total_bets * 100) if total_bets else 0
        balance_line = f"Balance: Rp{final_balance:,}\n" if final_balance else ""
        text = (
            f"📊 <b>Daily Summary — {date}</b>\n"
            f"Bets: {total_bets} (W:{win_count} L:{loss_count} | {win_rate:.1f}%)\n"
            f"Wagered: Rp{total_wagered:,}\n"
            f"Won: Rp{total_won:,}\n"
            f"Net: {net_str}\n"
            f"{balance_line}"
        )
        await self._send(text)

    async def send_alert(self, message: str) -> None:
        await self._send(f"⚠️ <b>Alert</b>\n{message}")

    async def send_info(self, message: str) -> None:
        await self._send(f"ℹ️ {message}")

    async def send_startup(self, dry_run: bool = False) -> None:
        mode = " [DRY RUN MODE]" if dry_run else ""
        await self._send(f"🤖 <b>Hokidraw Bot Started{mode}</b>\nWaiting for first draw...")

    async def send_shutdown(self) -> None:
        await self._send("🛑 <b>Hokidraw Bot Stopped</b>")

    async def send_limit_reached(self, daily_loss: int, limit: int) -> None:
        await self._send(
            f"🚫 <b>Daily Loss Limit Reached</b>\n"
            f"Lost: Rp{daily_loss:,} / Limit: Rp{limit:,}\n"
            f"Pausing until midnight WIB."
        )
