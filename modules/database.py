"""SQLite database layer for the Hokidraw bot."""

import os
import logging
import aiosqlite
from config import DB_PATH

logger = logging.getLogger(__name__)

# ─── DDL ─────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    periode    TEXT    UNIQUE NOT NULL,
    result     TEXT    NOT NULL,
    draw_time  TEXT    NOT NULL,
    created_at TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bets (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    periode          TEXT    NOT NULL,
    numbers          TEXT    NOT NULL,
    bet_amount       INTEGER NOT NULL,
    martingale_level INTEGER NOT NULL,
    status           TEXT    DEFAULT 'pending',
    win_amount       INTEGER DEFAULT 0,
    raw_response     TEXT,
    created_at       TEXT    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    UNIQUE NOT NULL,
    total_bets    INTEGER DEFAULT 0,
    total_wagered INTEGER DEFAULT 0,
    total_won     INTEGER DEFAULT 0,
    net_result    INTEGER DEFAULT 0,
    win_count     INTEGER DEFAULT 0,
    loss_count    INTEGER DEFAULT 0,
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bot_state (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


# ─── Init ─────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        for statement in _SCHEMA.strip().split(";"):
            s = statement.strip()
            if s:
                await db.execute(s)
        await db.commit()
    logger.info("Database initialised at %s", DB_PATH)


# ─── Results ──────────────────────────────────────────────────────────────────

async def save_result(periode: str, result: str, draw_time: str) -> bool:
    """Insert a new draw result. Returns True if inserted, False if duplicate."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO results (periode, result, draw_time) VALUES (?, ?, ?)",
            (periode, result, draw_time),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_recent_results(limit: int = 200) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM results ORDER BY id DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_last_result() -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM results ORDER BY id DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def result_exists(periode: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM results WHERE periode = ?", (periode,)
        ) as cur:
            return await cur.fetchone() is not None


# ─── Bets ─────────────────────────────────────────────────────────────────────

async def save_bet(
    periode: str,
    numbers: list[str],
    bet_amount: int,
    martingale_level: int,
    raw_response: str | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO bets (periode, numbers, bet_amount, martingale_level, raw_response)
               VALUES (?, ?, ?, ?, ?)""",
            (periode, ",".join(numbers), bet_amount, martingale_level, raw_response),
        )
        await db.commit()
        return cur.lastrowid


async def update_bet_result(bet_id: int, status: str, win_amount: int = 0) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE bets
               SET status = ?, win_amount = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, win_amount, bet_id),
        )
        await db.commit()


async def get_pending_bets() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bets WHERE status = 'pending' ORDER BY id DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_bet_by_periode(periode: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bets WHERE periode = ? LIMIT 1", (periode,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ─── Bot state ────────────────────────────────────────────────────────────────

async def get_state(key: str, default: str | None = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM bot_state WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def set_state(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO bot_state (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE
               SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
            (key, str(value)),
        )
        await db.commit()


# ─── Daily stats ──────────────────────────────────────────────────────────────

async def update_daily_stats(
    date: str, wagered: int, won: int, is_win: bool
) -> None:
    net = won - wagered
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_stats
               (date, total_bets, total_wagered, total_won, net_result, win_count, loss_count)
               VALUES (?, 1, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   total_bets    = total_bets + 1,
                   total_wagered = total_wagered + excluded.total_wagered,
                   total_won     = total_won     + excluded.total_won,
                   net_result    = net_result    + excluded.net_result,
                   win_count     = win_count     + excluded.win_count,
                   loss_count    = loss_count    + excluded.loss_count""",
            (date, wagered, won, net, 1 if is_win else 0, 0 if is_win else 1),
        )
        await db.commit()


async def get_daily_stats(date: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM daily_stats WHERE date = ?", (date,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
