"""Money management with soft martingale and daily loss limit."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import (
    MARTINGALE_LEVELS, MARTINGALE_LOSS_THRESHOLD,
    MAX_MARTINGALE_LEVEL, DAILY_LOSS_LIMIT, NUM_PICKS,
)
from modules import database as db

logger = logging.getLogger(__name__)

# WIB = UTC+7
_WIB = timezone(timedelta(hours=7))


def _today_wib() -> str:
    return datetime.now(_WIB).strftime("%Y-%m-%d")


class MoneyManager:
    """Tracks consecutive losses, manages martingale levels, enforces daily loss limit."""

    # ─── State accessors ─────────────────────────────────────────────────────

    async def get_consecutive_losses(self) -> int:
        val = await db.get_state("consecutive_losses", "0")
        return int(val)

    async def set_consecutive_losses(self, count: int) -> None:
        await db.set_state("consecutive_losses", str(count))

    async def get_martingale_level(self) -> int:
        val = await db.get_state("martingale_level", "0")
        return int(val)

    async def set_martingale_level(self, level: int) -> None:
        level = min(level, MAX_MARTINGALE_LEVEL)
        await db.set_state("martingale_level", str(level))

    async def get_daily_loss(self) -> int:
        val = await db.get_state("daily_loss", "0")
        return int(val)

    async def add_daily_loss(self, amount: int) -> int:
        current = await self.get_daily_loss()
        new_total = current + amount
        await db.set_state("daily_loss", str(new_total))
        return new_total

    async def reset_daily_loss(self) -> None:
        await db.set_state("daily_loss", "0")
        logger.info("Daily loss counter reset")

    # ─── Bet amount ──────────────────────────────────────────────────────────

    async def get_bet_amount(self) -> int:
        """Return bet amount per number for current martingale level."""
        level = await self.get_martingale_level()
        return MARTINGALE_LEVELS[level]

    async def get_total_bet(self, num_numbers: int = NUM_PICKS) -> int:
        """Return total bet amount for current martingale level."""
        return (await self.get_bet_amount()) * num_numbers

    # ─── Daily loss limit ─────────────────────────────────────────────────────

    async def is_daily_limit_reached(self) -> bool:
        daily_loss = await self.get_daily_loss()
        return daily_loss >= DAILY_LOSS_LIMIT

    async def check_and_enforce_daily_limit(self) -> bool:
        """Returns True if betting should continue, False if limit hit."""
        if await self.is_daily_limit_reached():
            loss = await self.get_daily_loss()
            logger.warning(
                "Daily loss limit reached: Rp%s / Rp%s — pausing until midnight WIB",
                loss, DAILY_LOSS_LIMIT,
            )
            return False
        return True

    # ─── Result recording ─────────────────────────────────────────────────────

    async def record_loss(self, wagered: int) -> None:
        """Update state after a losing round."""
        losses = await self.get_consecutive_losses()
        losses += 1
        await self.set_consecutive_losses(losses)

        # Add to daily loss
        daily = await self.add_daily_loss(wagered)
        logger.info(
            "Loss recorded: consecutive=%s daily_loss=Rp%s/Rp%s",
            losses, daily, DAILY_LOSS_LIMIT,
        )

        # Level up martingale if threshold reached
        if losses > 0 and losses % MARTINGALE_LOSS_THRESHOLD == 0:
            current_level = await self.get_martingale_level()
            if current_level < MAX_MARTINGALE_LEVEL:
                new_level = current_level + 1
                await self.set_martingale_level(new_level)
                logger.info(
                    "Martingale level up: %s → %s (bet per number: Rp%s)",
                    current_level, new_level, MARTINGALE_LEVELS[new_level],
                )
            else:
                logger.warning(
                    "Already at max martingale level %s (Rp%s/number)",
                    MAX_MARTINGALE_LEVEL, MARTINGALE_LEVELS[MAX_MARTINGALE_LEVEL],
                )

        # Update daily stats
        today = _today_wib()
        await db.update_daily_stats(today, wagered, 0, is_win=False)

    async def record_win(self, wagered: int, won: int) -> None:
        """Update state after a winning round — reset consecutive losses."""
        await self.set_consecutive_losses(0)
        await self.set_martingale_level(0)
        logger.info("Win recorded: won=Rp%s wagered=Rp%s — martingale reset", won, wagered)

        today = _today_wib()
        await db.update_daily_stats(today, wagered, won, is_win=True)

    # ─── Daily reset ─────────────────────────────────────────────────────────

    async def midnight_reset(self) -> None:
        """Reset daily counters at midnight WIB."""
        await self.reset_daily_loss()
        logger.info("Midnight reset: daily loss cleared")

    # ─── Summary ─────────────────────────────────────────────────────────────

    async def get_status_summary(self) -> dict:
        level = await self.get_martingale_level()
        losses = await self.get_consecutive_losses()
        daily_loss = await self.get_daily_loss()
        bet_amount = MARTINGALE_LEVELS[level]

        return {
            "martingale_level": level,
            "consecutive_losses": losses,
            "bet_per_number": bet_amount,
            "total_bet_per_round": bet_amount * NUM_PICKS,
            "daily_loss": daily_loss,
            "daily_limit": DAILY_LOSS_LIMIT,
            "daily_limit_remaining": max(0, DAILY_LOSS_LIMIT - daily_loss),
            "limit_reached": daily_loss >= DAILY_LOSS_LIMIT,
        }
