import os
from dotenv import load_dotenv

load_dotenv()

# ─── Site ────────────────────────────────────────────────────────────────────
BASE_URL = "https://partai34848.com"
POOL_ID = "p76368"
GAME_TYPE = "quick_2d"
BET_TYPE = "B"  # B=full, D=discount, A=bolak-balik
BET_POSISI = "belakang"

# ─── Credentials ─────────────────────────────────────────────────────────────
USERNAME = os.getenv("PARTAI_USERNAME")
PASSWORD = os.getenv("PARTAI_PASSWORD")

# ─── OpenRouter LLM ──────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_PRIMARY = "google/gemini-2.0-flash-001"
LLM_FALLBACK = "anthropic/claude-sonnet-4-20250514"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 1000

# ─── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ─── Betting ─────────────────────────────────────────────────────────────────
NUM_PICKS = 5          # numbers to bet per period
MIN_BET = 100          # Rp 100 minimum
MAX_BET_2D = 2_000_000  # Rp 2,000,000 maximum

# ─── Martingale ──────────────────────────────────────────────────────────────
# Bet amount per number at each level (IDR)
MARTINGALE_LEVELS = [1_000, 1_500, 2_500, 4_000, 6_000, 9_000, 13_000]
MARTINGALE_LOSS_THRESHOLD = 5   # consecutive losses before level-up
MAX_MARTINGALE_LEVEL = len(MARTINGALE_LEVELS) - 1  # 0-indexed

# ─── Money management ────────────────────────────────────────────────────────
DAILY_LOSS_LIMIT = 200_000  # Rp 200,000

# ─── Timing ──────────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = 120  # 2 minutes between polls
BET_START_MINUTE = 5         # start placing bets from minute :05
BET_STOP_MINUTE = 50         # stop placing bets after minute :50
MAX_POLL_ATTEMPTS = 10       # max polling attempts for new result

# ─── External APIs ───────────────────────────────────────────────────────────
TIMER_API_URL = "https://jampasaran.smbgroup.io/pasaran"

# ─── Paths ───────────────────────────────────────────────────────────────────
DB_PATH = "data/hokidraw.db"
LOG_PATH = "logs/bot.log"

# ─── Session ─────────────────────────────────────────────────────────────────
SESSION_VALIDATION_INTERVAL = 30 * 60  # 30 minutes in seconds

# ─── Browser headers (anti-Cloudflare) ───────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

AJAX_HEADERS = {
    **HEADERS,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
