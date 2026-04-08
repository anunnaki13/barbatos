"""Bet placement module for partai34848.com."""

import logging
import json
import re
from typing import Optional

import httpx

from config import (
    BASE_URL, POOL_ID, GAME_TYPE, BET_TYPE, BET_POSISI,
    MIN_BET, MAX_BET_2D, AJAX_HEADERS,
)
from modules.auth import AuthManager

logger = logging.getLogger(__name__)


class Bettor:
    def __init__(self, auth: AuthManager) -> None:
        self._auth = auth

    # ─── Validation ──────────────────────────────────────────────────────────

    @staticmethod
    def validate_numbers(numbers: list[str]) -> list[str]:
        """Validate and deduplicate 2D numbers. Returns cleaned list."""
        cleaned = []
        seen = set()
        for num in numbers:
            num = str(num).strip().zfill(2)
            if not re.match(r"^\d{2}$", num):
                logger.warning("Invalid number skipped: %s", num)
                continue
            if num in seen:
                logger.warning("Duplicate number skipped: %s", num)
                continue
            seen.add(num)
            cleaned.append(num)
        return cleaned

    @staticmethod
    def idr_to_bet_param(amount_idr: int) -> str:
        """Convert IDR amount to bet parameter (in thousands). Rp 1000 → '1'."""
        val = amount_idr / 1000
        # Format cleanly: no trailing zeros for whole numbers
        if val == int(val):
            return str(int(val))
        return str(round(val, 3))

    # ─── Bet placement ───────────────────────────────────────────────────────

    async def place_bets(
        self,
        numbers: list[str],
        bet_amount_idr: int,
        dry_run: bool = False,
    ) -> Optional[dict]:
        """
        Place 2D bets on the given numbers.

        Args:
            numbers: list of 2-digit strings to bet on.
            bet_amount_idr: IDR amount per number.
            dry_run: if True, log the bet but do not submit.

        Returns:
            Parsed API response dict, or a dry-run placeholder.
        """
        numbers = self.validate_numbers(numbers)
        if not numbers:
            logger.error("No valid numbers to bet")
            return None

        # Clamp bet amount
        bet_amount_idr = max(MIN_BET, min(MAX_BET_2D, bet_amount_idr))
        bet_param = self.idr_to_bet_param(bet_amount_idr)

        # Build form payload
        payload: dict[str, str] = {
            "type": BET_TYPE,
            "game": GAME_TYPE,
            "bet": bet_param,
            "posisi": BET_POSISI,
            "sar": POOL_ID,
        }
        for i, num in enumerate(numbers, start=1):
            payload[f"cek{i}"] = "1"
            payload[f"tebak{i}"] = num

        logger.info(
            "Betting: numbers=%s amount=Rp%s/number total=Rp%s dry_run=%s",
            numbers, bet_amount_idr, bet_amount_idr * len(numbers), dry_run,
        )

        if dry_run:
            return {
                "status": "dry_run",
                "numbers": numbers,
                "bet_amount": bet_amount_idr,
                "total": bet_amount_idr * len(numbers),
                "payload": payload,
            }

        client = await self._auth.get_client()
        try:
            resp = await client.post(
                BASE_URL + "/games/4d/send",
                data=payload,
                headers={
                    **AJAX_HEADERS,
                    "Referer": f"{BASE_URL}/games/4d/{POOL_ID}",
                },
            )
            raw = resp.text
            logger.debug("Bet API raw response: %s", raw)

            try:
                data = resp.json()
            except Exception:
                data = {"raw": raw}

            data["_numbers"] = numbers
            data["_bet_amount"] = bet_amount_idr

            success = data.get("status") in (1, "1", True, "true", "ok", "success")
            if success:
                logger.info(
                    "Bet placed OK: periode=%s transaksi=%s balance=%s",
                    data.get("periode"),
                    data.get("transaksi"),
                    data.get("balance"),
                )
            else:
                logger.error("Bet placement failed: %s", data)

            return data

        except Exception as e:
            logger.error("Bet request failed: %s", e)
            return None

    # ─── Win check ───────────────────────────────────────────────────────────

    @staticmethod
    def check_win(numbers_bet: list[str], draw_result: str) -> tuple[bool, str | None]:
        """
        Check if any bet number matches the draw result.

        For 2D belakang, we match the last 2 digits of the result.
        Returns (won: bool, winning_number: str | None).
        """
        result_clean = str(draw_result).strip()
        # Extract last 2 digits
        digits = re.sub(r"\D", "", result_clean)
        last_two = digits[-2:] if len(digits) >= 2 else digits.zfill(2)

        for num in numbers_bet:
            if num == last_two:
                return True, num
        return False, None

    @staticmethod
    def calculate_payout(bet_amount_idr: int, num_numbers: int) -> int:
        """
        Calculate potential payout for type=B (full) 2D bet.
        Payout is x100 per winning number; total wagered = bet_amount * num_numbers.
        """
        return bet_amount_idr * 100  # per winning number
