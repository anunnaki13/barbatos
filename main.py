"""
Hokidraw 2D Lottery Bot
=======================
Automatically predicts and places 2D bets on the Hokidraw market (partai34848.com)
using OpenRouter LLM for number selection and soft martingale money management.

Usage:
    python main.py              # live mode
    python main.py --dry-run    # dry-run (no real bets placed)
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import (
    POLL_INTERVAL_SECONDS, MAX_POLL_ATTEMPTS,
    BET_START_MINUTE, BET_STOP_MINUTE,
    DAILY_LOSS_LIMIT, LOG_PATH, DB_PATH,
    validate_config,
)
from modules import database as db
from modules.auth import AuthManager
from modules.scraper import Scraper
from modules.predictor import Predictor
from modules.bettor import Bettor
from modules.money_manager import MoneyManager
from modules.notifier import TelegramNotifier

# ─── Logging ─────────────────────────────────────────────────────────────────

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger("hokidraw.main")

# ─── WIB timezone ─────────────────────────────────────────────────────────────
_WIB = timezone(timedelta(hours=7))


def _now_wib() -> datetime:
    return datetime.now(_WIB)


# ─── Bot state ────────────────────────────────────────────────────────────────

class HokidrawBot:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.auth = AuthManager()
        self.scraper = Scraper(self.auth)
        self.predictor = Predictor()
        self.bettor = Bettor(self.auth)
        self.money_manager = MoneyManager()
        self.notifier = TelegramNotifier()
        self._last_handled_periode: Optional[str] = None

    # ─── Betting cycle ───────────────────────────────────────────────────────

    async def run_betting_cycle(self) -> None:
        """Full hourly betting cycle: result → predict → bet."""
        now = _now_wib()
        logger.info("=== Betting cycle start @ %s ===", now.strftime("%H:%M WIB"))

        # Check daily loss limit before doing anything
        if not await self.money_manager.check_and_enforce_daily_limit():
            await self.notifier.send_limit_reached(
                await self.money_manager.get_daily_loss(), DAILY_LOSS_LIMIT
            )
            return

        # Ensure we are logged in
        if not await self.auth.ensure_logged_in():
            await self.notifier.send_alert("Login failed — skipping cycle")
            return

        # ── Step 1: Poll for latest draw result ──────────────────────────────
        new_result = await self._wait_for_new_result()
        if new_result is None:
            logger.warning("No new result detected after %s attempts", MAX_POLL_ATTEMPTS)
            return

        # ── Step 2: Check pending bets against new result ────────────────────
        await self._settle_pending_bets(new_result)

        # ── Step 3: Check daily limit again (post-settle) ────────────────────
        if not await self.money_manager.check_and_enforce_daily_limit():
            await self.notifier.send_limit_reached(
                await self.money_manager.get_daily_loss(), DAILY_LOSS_LIMIT
            )
            return

        # ── Step 4: Check if we're in the betting window ─────────────────────
        minute = now.minute
        if not (BET_START_MINUTE <= minute <= BET_STOP_MINUTE):
            logger.info("Outside betting window (:%02d) — skipping bet", minute)
            return

        # ── Step 5: Fetch history and predict ────────────────────────────────
        history = await self.scraper.get_draw_history()
        if not history:
            await self.notifier.send_alert("Failed to fetch draw history")
            return

        prediction = await self.predictor.predict(history)
        if prediction is None:
            await self.notifier.send_alert("LLM prediction failed")
            return

        picks = prediction["picks"]
        numbers = [p["number"] for p in picks]
        analysis = prediction.get("analysis", "")
        logger.info("Predicted numbers: %s", numbers)
        logger.info("Analysis: %s", analysis)

        # ── Step 6: Get bet amount from money manager ─────────────────────────
        bet_per_number = await self.money_manager.get_bet_amount()
        total_bet = bet_per_number * len(numbers)
        martingale_level = await self.money_manager.get_martingale_level()

        # ── Step 7: Get current periode ───────────────────────────────────────
        periode = await self.scraper.get_current_periode()
        if not periode:
            await self.notifier.send_alert("Failed to get current periode")
            return

        # Avoid re-betting on the same periode
        if periode == self._last_handled_periode:
            logger.info("Already bet on periode %s — skipping", periode)
            return

        # ── Step 8: Place bets ────────────────────────────────────────────────
        response = await self.bettor.place_bets(numbers, bet_per_number, dry_run=self.dry_run)
        if response is None:
            await self.notifier.send_alert(f"Bet placement failed for periode {periode}")
            return

        success = (
            self.dry_run
            or response.get("status") in (1, "1", True, "true", "ok", "success")
        )

        if success:
            self._last_handled_periode = periode
            # Save to DB
            bet_id = await db.save_bet(
                periode=periode,
                numbers=numbers,
                bet_amount=bet_per_number,
                martingale_level=martingale_level,
                raw_response=str(response),
            )
            logger.info("Bet saved to DB: id=%s periode=%s", bet_id, periode)

            await self.notifier.send_bet_placed(
                periode=periode,
                numbers=numbers,
                bet_per_number=bet_per_number,
                total_bet=total_bet,
                martingale_level=martingale_level,
                analysis=analysis,
                dry_run=self.dry_run,
            )
        else:
            await self.notifier.send_alert(
                f"Bet rejected for periode {periode}: {response}"
            )

    # ─── New result polling ───────────────────────────────────────────────────

    async def _wait_for_new_result(self) -> Optional[dict]:
        """
        Poll for a new draw result that hasn't been seen yet.
        Returns the result dict or None after MAX_POLL_ATTEMPTS.
        """
        last_known = await db.get_last_result()
        last_periode = last_known["periode"] if last_known else None

        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            latest = await self.scraper.get_latest_result()
            if latest and latest["periode"] != last_periode:
                # New result found
                inserted = await db.save_result(
                    latest["periode"],
                    latest["result"],
                    latest["draw_time"],
                )
                if inserted:
                    logger.info(
                        "New result: periode=%s result=%s",
                        latest["periode"], latest["result"],
                    )
                return latest

            if attempt < MAX_POLL_ATTEMPTS:
                logger.debug("No new result yet (attempt %s/%s), waiting %ss",
                             attempt, MAX_POLL_ATTEMPTS, POLL_INTERVAL_SECONDS)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        return None

    # ─── Bet settlement ───────────────────────────────────────────────────────

    async def _settle_pending_bets(self, new_result: dict) -> None:
        """Check all pending bets against the new draw result."""
        pending = await db.get_pending_bets()
        if not pending:
            return

        result_str = new_result["result"]
        for bet in pending:
            numbers = bet["numbers"].split(",")
            won, winning_num = self.bettor.check_win(numbers, result_str)
            bet_amount = bet["bet_amount"]
            total_wagered = bet_amount * len(numbers)

            if won:
                payout = self.bettor.calculate_payout(bet_amount, len(numbers))
                await db.update_bet_result(bet["id"], "won", payout)
                await self.money_manager.record_win(total_wagered, payout)
                daily_loss = await self.money_manager.get_daily_loss()
                await self.notifier.send_result(
                    periode=bet["periode"],
                    draw_result=result_str,
                    won=True,
                    winning_number=winning_num,
                    win_amount=payout,
                    wagered=total_wagered,
                    consecutive_losses=0,
                    daily_loss=daily_loss,
                )
            else:
                await db.update_bet_result(bet["id"], "lost", 0)
                await self.money_manager.record_loss(total_wagered)
                consecutive = await self.money_manager.get_consecutive_losses()
                daily_loss = await self.money_manager.get_daily_loss()
                await self.notifier.send_result(
                    periode=bet["periode"],
                    draw_result=result_str,
                    won=False,
                    winning_number=None,
                    win_amount=0,
                    wagered=total_wagered,
                    consecutive_losses=consecutive,
                    daily_loss=daily_loss,
                )

    # ─── Daily summary ────────────────────────────────────────────────────────

    async def run_daily_summary(self) -> None:
        """Send daily summary at 23:55 WIB."""
        today = _now_wib().strftime("%Y-%m-%d")
        stats = await db.get_daily_stats(today)
        balance = await self.auth.get_balance()

        if stats:
            await self.notifier.send_daily_summary(
                date=today,
                total_bets=stats["total_bets"],
                total_wagered=stats["total_wagered"],
                total_won=stats["total_won"],
                win_count=stats["win_count"],
                loss_count=stats["loss_count"],
                final_balance=balance,
            )
        else:
            await self.notifier.send_info(f"No bets placed today ({today})")

        await self.money_manager.midnight_reset()

    # ─── Startup ─────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        await db.init_db()
        if not await self.auth.login():
            logger.error("Initial login failed — check credentials")
            sys.exit(1)
        balance = await self.auth.get_balance()
        logger.info("Logged in. Balance: Rp%s", f"{balance:,}" if balance else "unknown")
        await self.notifier.send_startup(dry_run=self.dry_run)

    async def shutdown(self) -> None:
        await self.notifier.send_shutdown()
        await self.auth.close()


# ─── Scheduler setup ──────────────────────────────────────────────────────────

async def run(dry_run: bool) -> None:
    bot = HokidrawBot(dry_run=dry_run)
    await bot.startup()

    scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

    # Main cycle: every hour at minute :05
    scheduler.add_job(
        bot.run_betting_cycle,
        CronTrigger(minute=BET_START_MINUTE, timezone="Asia/Jakarta"),
        id="betting_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    # Daily summary at 23:55 WIB
    scheduler.add_job(
        bot.run_daily_summary,
        CronTrigger(hour=23, minute=55, timezone="Asia/Jakarta"),
        id="daily_summary",
        max_instances=1,
    )

    scheduler.start()
    logger.info(
        "Scheduler started. Betting cycle fires at :%02d each hour. Dry run: %s",
        BET_START_MINUTE, dry_run,
    )

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown(wait=False)
        await bot.shutdown()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Hokidraw 2D Lottery Bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log semua aksi tanpa benar-benar pasang bet",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Cek konfigurasi .env saja lalu keluar",
    )
    args = parser.parse_args()

    # Validasi konfigurasi — wajib sebelum apapun
    validate_config(exit_on_error=not args.check_config)

    if args.check_config:
        sys.exit(0)

    if args.dry_run:
        logger.info("*** DRY RUN MODE — tidak ada bet sungguhan yang dipasang ***")

    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
