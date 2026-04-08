# CLAUDE CODE BLUEPRINT: Hokidraw 2D Auto-Betting Bot

## PROJECT OVERVIEW

Bangun bot Python untuk otomatis memasang taruhan togel 2D pada pasaran **Hokidraw** di situs partai34848.com. Bot berjalan di VPS Linux, menggunakan OpenRouter LLM untuk analisis prediksi, dan mengirim notifikasi via Telegram.

---

## TARGET PASARAN

- **Nama**: HOKIDRAW POOLS
- **Pool ID**: `p76368`
- **Internal Code**: `OKAQ`
- **Jadwal**: 24 draw per hari (setiap 1 jam)
- **Draw dimulai**: menit :01 setiap jam
- **Hasil masuk ke situs**: sekitar menit :20 (delay dari penyelenggara)
- **Situs resmi draw**: https://hokidraw.com
- **Game type**: `quick_2d` (2 digit terakhir, posisi "belakang")

---

## API ENDPOINTS (CONFIRMED FROM HAR)

### Base URL: `https://partai34848.com`

### 1. Authentication
```
POST /json/post/ceklogin-ts
Content-Type: application/json
X-Requested-With: XMLHttpRequest

Body:
{
  "entered_login": "<username>",
  "entered_password": "<password>",
  "liteMode": "",
  "_token": "<csrf_token>"
}

Note: _token (CSRF) harus diambil dari halaman utama sebelum login.
Note: Password dikirim plain text (tidak di-hash).
```

### 2. Place Bet (ENDPOINT UTAMA)
```
POST /games/4d/send
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest

Body (URL-encoded form data):
  type=B                  # B=BET FULL (hadiah x100), D=BET DISKON, A=BET BB
  ganti=F                 # Fixed value, selalu "F"
  game=quick_2d           # Tipe game
  bet=1                   # Nominal dalam ribuan (1 = Rp 1.000)
  posisi=belakang         # Posisi 2D belakang (2 digit terakhir)
  cek1=1                  # Flag angka ke-1 aktif
  tebak1=34               # Angka tebakan ke-1 (00-99)
  cek2=1                  # Flag angka ke-2 aktif
  tebak2=17               # Angka tebakan ke-2 (00-99)
  cek3=1                  # Flag angka ke-3 aktif
  tebak3=82               # Angka tebakan ke-3 (00-99)
  sar=p76368              # Pool ID Hokidraw

Response (JSON):
{
  "status": true,
  "transaksi": "34@@C@@1000@@0.00@@0@@1000@@1000@@100000@@B//...",
  "error": "",
  "periode": "11037 - HOKIDRAW",
  "balance": "40013.00"
}

Konversi bet:
  bet=0.1 → Rp 100
  bet=1   → Rp 1.000
  bet=5   → Rp 5.000
  bet=10  → Rp 10.000

Limits 2D: min=100 (Rp 100), max=2.000.000
Hadiah BET FULL 2D: x100 (bet Rp 1.000 → menang Rp 100.000)
```

### 3. Game Data & Timer
```
GET /games/4d/p76368
→ Parse hidden field "timerpools" = detik tersisa sampai betting ditutup
→ Parse hidden field "periode" = nomor periode aktif

GET /games/4d/load/quick_2d/p76368
→ HTML form Quick 2D betting panel
→ Berisi info periode aktif

GET https://jampasaran.smbgroup.io/pasaran (PUBLIC, no auth needed)
→ JSON response:
{
  "status": "success",
  "data": {
    "hokidraw": 1138,  ← detik sampai draw berikutnya
    ...
  }
}
```

### 4. History / Results
```
GET /history/detail/data/p76368-1
→ JSON data history keluaran (perlu dicoba langsung, body kosong di HAR karena lazy-load)

GET /games/4d/history/quick_2d/p76368
→ HTML table bet history: No, Tebakan, Taruhan, Diskon, Bayar, Type, Menang
```

### 5. Balance
```
POST /request-balance
X-Requested-With: XMLHttpRequest
→ Response: saldo current (angka, misal "40013.00")
```

### 6. WebSocket (Real-time results)
```
wss://sbstat.hokibagus.club/smb/az2/socket.io/?EIO=3&transport=websocket
→ Socket.io v3, push event hasil draw
```

### 7. Session Check
```
GET /json/post/validate-login
→ Check apakah session masih aktif
```

---

## ARCHITECTURE

```
hokidraw-bot/
├── config.py              # Semua konfigurasi
├── main.py                # Entry point + scheduler
├── modules/
│   ├── auth.py            # Login, CSRF token, session management
│   ├── scraper.py         # Ambil history results + detect new draw
│   ├── predictor.py       # Analisis statistik + LLM call via OpenRouter
│   ├── bettor.py          # Submit taruhan ke /games/4d/send
│   ├── money_manager.py   # Soft Martingale logic + daily limits
│   ├── notifier.py        # Telegram bot notifications
│   └── database.py        # SQLite operations
├── data/
│   └── hokidraw.db        # SQLite database
├── logs/
│   └── bot.log            # Rotating log files
├── .env                   # Environment variables (credentials)
└── requirements.txt
```

---

## CONFIG.PY STRUCTURE

```python
# .env file:
PARTAI_USERNAME=xxx
PARTAI_PASSWORD=xxx
OPENROUTER_API_KEY=sk-or-xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# config.py constants:
BASE_URL = "https://partai34848.com"
POOL_ID = "p76368"
GAME_TYPE = "quick_2d"
BET_TYPE = "B"  # BET FULL
BET_POSITION = "belakang"

# Timing
POLL_INTERVAL_SECONDS = 120  # Check every 2 minutes for new results
POLL_START_MINUTE = 5        # Start polling at :05 each hour
BET_DEADLINE_MINUTES = 50    # Stop betting at :50 (safety margin)

# Money Management - Soft Martingale
BASE_BET = 1          # Rp 1.000 per angka
NUM_PICKS = 5         # Jumlah angka per periode
MARTINGALE_MULTIPLIER = 1.5
MARTINGALE_STEP_LOSSES = 5  # Naik level setiap 5 consecutive losses
MARTINGALE_CEILING = 7      # Max level
DAILY_LOSS_LIMIT = 200000   # Rp 200.000 per hari

# Martingale Levels (in Rupiah per angka)
MARTINGALE_LEVELS = [1000, 1500, 2500, 4000, 6000, 9000, 13000]

# LLM
OPENROUTER_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_FALLBACK = "anthropic/claude-sonnet-4-20250514"
HISTORY_WINDOW = 200  # Jumlah periode terakhir untuk analisis
```

---

## MODULE SPECIFICATIONS

### 1. auth.py
```
class AuthManager:
  - __init__(session: httpx.AsyncClient)
  - get_csrf_token() -> str
      # GET homepage, parse _token dari HTML/meta tag
  - login(username, password) -> bool
      # POST /json/post/ceklogin-ts
  - check_session() -> bool
      # GET /json/post/validate-login
  - ensure_logged_in()
      # Check session, re-login if expired
  - get_balance() -> float
      # POST /request-balance

PENTING: Situs menggunakan Cloudflare protection.
Gunakan httpx dengan headers yang meniru browser:
  User-Agent: Chrome terbaru
  Accept, Accept-Language, etc.
Jika Cloudflare memblokir, fallback ke Playwright headless browser.
```

### 2. scraper.py
```
class Scraper:
  - __init__(session, db)
  - get_timer() -> int
      # GET https://jampasaran.smbgroup.io/pasaran
      # Return detik tersisa untuk hokidraw
  - get_current_period() -> str
      # GET /games/4d/p76368, parse hidden field "periode"
  - get_history(limit=200) -> list[dict]
      # GET /history/detail/data/p76368-1
      # Parse JSON response: [{periode, tanggal, nomor}]
      # Jika endpoint JSON kosong, fallback: GET /games/4d/history/quick_2d/p76368
      # Parse HTML table sebagai fallback
  - detect_new_result() -> Optional[dict]
      # Poll dan compare dengan last known result di DB
      # Return new result jika ada
  - get_bet_history() -> list[dict]
      # GET /games/4d/history/quick_2d/p76368
      # Parse HTML table: tebakan, taruhan, type, menang
```

### 3. predictor.py
```
class Predictor:
  - __init__(openrouter_api_key, model)
  - analyze(history: list[dict]) -> list[dict]
      # Kirim data history ke LLM via OpenRouter
      # Minta analisis: hot numbers, cold numbers, overdue, patterns
      # Return: [{"number": "34", "confidence": 0.72, "reason": "..."}]

  Prompt template:
  """
  Kamu adalah analis statistik togel 2D. Analisis data berikut dan rekomendasikan
  5 angka 2D (00-99) yang paling berpotensi keluar di periode berikutnya.

  Data {n} periode terakhir pasaran Hokidraw (2 digit terakhir):
  {history_data}

  Analisis yang harus dilakukan:
  1. Frekuensi: angka mana yang paling sering muncul (hot numbers)
  2. Gap analysis: angka mana yang sudah lama tidak keluar (overdue)
  3. Pattern: apakah ada pola berulang (genap/ganjil, besar/kecil)
  4. Distribusi digit: analisis digit puluhan dan satuan secara terpisah
  5. Trend terkini: pola dari 10-20 periode terakhir

  PENTING: Respond HANYA dalam format JSON berikut, tanpa teks lain:
  {
    "recommendations": [
      {"number": "XX", "confidence": 0.XX, "reason": "..."},
      ...max 5 angka
    ],
    "analysis_summary": "ringkasan singkat analisis"
  }
  """

  OpenRouter API call:
  POST https://openrouter.ai/api/v1/chat/completions
  Headers:
    Authorization: Bearer $OPENROUTER_API_KEY
    Content-Type: application/json
  Body:
    model: "google/gemini-2.0-flash-001"
    messages: [{role: "user", content: prompt}]
    temperature: 0.3
    max_tokens: 1000
```

### 4. bettor.py
```
class Bettor:
  - __init__(session, pool_id)
  - place_bet(numbers: list[str], bet_amount: float) -> dict
      # POST /games/4d/send
      # Build form data:
      #   type=B, ganti=F, game=quick_2d, bet={amount_in_thousands}
      #   posisi=belakang, sar=p76368
      #   cek1=1, tebak1={numbers[0]}, cek2=1, tebak2={numbers[1]}, ...
      # Return: {"status": bool, "periode": str, "balance": float, "error": str}
  - validate_bet(numbers, amount) -> bool
      # Validate: numbers 00-99, amount within limits, no duplicates
```

### 5. money_manager.py
```
class MoneyManager:
  - __init__(db, config)
  - get_current_level() -> int
      # Hitung level berdasar consecutive losses
  - get_bet_amount() -> float
      # Return nominal bet sesuai martingale level (dalam ribuan untuk API)
  - record_result(period, numbers_bet, result, win_amount) -> None
      # Simpan ke DB, update consecutive loss counter
  - on_win() -> None
      # Reset ke level 1
  - on_loss() -> None
      # Increment loss counter, check step-up
  - check_daily_limit() -> bool
      # Return False jika daily loss limit tercapai
  - get_stats() -> dict
      # Total bet, total win, profit/loss, current level, etc.

  Soft Martingale Logic:
  - consecutive_losses tracked in DB
  - Level up setiap 5 consecutive losses
  - Max level = 7 (ceiling)
  - Win → reset ke level 1
  - Daily loss limit → bot pause sampai 00:00 WIB
```

### 6. notifier.py
```
class TelegramNotifier:
  - __init__(bot_token, chat_id)
  - send_message(text) -> None
  - notify_bet_placed(period, numbers, amount, level) -> None
      # "🎯 BET Periode 11038 - HOKIDRAW
      #  Angka: 34, 17, 82, 56, 21
      #  Bet: Rp 1.000/angka (Level 1)
      #  Total: Rp 5.000"
  - notify_result(period, result, win, amount_won) -> None
      # "✅ WIN! Periode 11038: 1234 (2D=34)
      #  Menang: Rp 100.000"
      # atau
      # "❌ LOSS Periode 11038: 5678 (2D=78)
      #  Rugi: -Rp 5.000 | Level: 1→1"
  - notify_daily_summary(stats) -> None
      # "📊 Ringkasan Hari Ini
      #  Bet: 24 periode | Win: 2 | Loss: 22
      #  Total Bet: Rp 120.000 | Total Win: Rp 200.000
      #  Profit: +Rp 80.000 | Saldo: Rp 540.000"
  - notify_alert(message) -> None
      # Saldo rendah, error, daily limit reached, dll
```

### 7. database.py
```
SQLite schema:

CREATE TABLE results (
    id INTEGER PRIMARY KEY,
    period TEXT UNIQUE,
    draw_time DATETIME,
    full_number TEXT,   -- 4 digit: "1234"
    number_2d TEXT,     -- 2 digit terakhir: "34"
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bets (
    id INTEGER PRIMARY KEY,
    period TEXT,
    numbers TEXT,        -- JSON array: ["34","17","82","56","21"]
    bet_amount REAL,     -- per angka dalam Rupiah
    total_amount REAL,   -- total semua angka
    martingale_level INTEGER,
    bet_type TEXT,        -- "B" (full), "D" (diskon), "A" (BB)
    status TEXT,          -- "placed", "won", "lost"
    win_amount REAL DEFAULT 0,
    result_2d TEXT,       -- 2D yang keluar
    api_response TEXT,    -- raw response from /games/4d/send
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE daily_stats (
    date TEXT PRIMARY KEY,
    total_bets INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    total_bet_amount REAL DEFAULT 0,
    total_win_amount REAL DEFAULT 0,
    profit REAL DEFAULT 0,
    ending_balance REAL DEFAULT 0
);

CREATE TABLE bot_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
-- Keys: "consecutive_losses", "martingale_level", "last_period", "daily_loss"
```

### 8. main.py (Entry Point)
```
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def main():
    # 1. Initialize all modules
    # 2. Login
    # 3. Start scheduler

    scheduler = AsyncIOScheduler()

    # Run bot cycle every hour
    # Trigger at :05, :07, :09... until new result detected
    # Then: predict → bet → wait for next hour

    async def hourly_cycle():
        """Main bot cycle - runs each hour"""
        # Step 1: Ensure logged in
        await auth.ensure_logged_in()

        # Step 2: Poll for new result (from previous period)
        result = None
        for attempt in range(10):  # Max 10 attempts (20 minutes)
            result = await scraper.detect_new_result()
            if result:
                break
            await asyncio.sleep(120)  # Wait 2 minutes

        if result:
            # Step 3: Record result, update martingale
            was_win = money_manager.record_result(result)
            await notifier.notify_result(result, was_win)

        # Step 4: Check daily limit
        if not money_manager.check_daily_limit():
            await notifier.notify_alert("Daily loss limit reached. Bot paused.")
            return

        # Step 5: Get history & predict
        history = await scraper.get_history(limit=200)
        predictions = await predictor.analyze(history)

        # Step 6: Get bet amount from martingale
        bet_amount = money_manager.get_bet_amount()
        numbers = [p["number"] for p in predictions[:5]]

        # Step 7: Place bet
        result = await bettor.place_bet(numbers, bet_amount)
        if result["status"]:
            await notifier.notify_bet_placed(...)

    # Schedule: run at :05 past every hour
    scheduler.add_job(hourly_cycle, 'cron', minute=5)

    # Daily summary at 23:55
    scheduler.add_job(daily_summary, 'cron', hour=23, minute=55)

    scheduler.start()
    await asyncio.Event().wait()  # Run forever

asyncio.run(main())
```

---

## REQUIREMENTS.TXT

```
httpx[http2]>=0.27.0
beautifulsoup4>=4.12.0
apscheduler>=3.10.0
python-dotenv>=1.0.0
python-telegram-bot>=21.0
openai>=1.30.0       # Compatible with OpenRouter
aiosqlite>=0.20.0
lxml>=5.0.0
```

---

## GIT & GITHUB WORKFLOW

### Repository Structure
```
hokidraw-bot/
├── .github/
│   └── workflows/         # (optional) CI checks
├── modules/
│   ├── __init__.py
│   ├── auth.py
│   ├── scraper.py
│   ├── predictor.py
│   ├── bettor.py
│   ├── money_manager.py
│   ├── notifier.py
│   └── database.py
├── data/                  # .gitkeep only, DB created at runtime
│   └── .gitkeep
├── logs/                  # .gitkeep only, logs created at runtime
│   └── .gitkeep
├── config.py
├── main.py
├── requirements.txt
├── .env.example           # Template tanpa credentials
├── .gitignore
├── README.md
└── HOKIDRAW_BOT_BLUEPRINT.md  # Dokumen ini
```

### .gitignore (PENTING — jangan commit credentials!)
```
.env
data/*.db
logs/*.log
__pycache__/
*.pyc
venv/
.vscode/
```

### .env.example (commit ini sebagai template)
```
PARTAI_USERNAME=your_username_here
PARTAI_PASSWORD=your_password_here
OPENROUTER_API_KEY=sk-or-your_key_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Claude Code Git Commands
Saat bekerja di Claude Code dengan GitHub repo:
```bash
# Clone / init repo
git init
git remote add origin https://github.com/<username>/hokidraw-bot.git

# Setelah selesai build setiap modul
git add -A
git commit -m "feat: add auth module with CSRF + login"
git push origin main
```

Commit secara incremental per modul:
1. `feat: project setup + config + database schema`
2. `feat: auth module (login, CSRF, session)`
3. `feat: scraper module (history, results, timer)`
4. `feat: predictor module (OpenRouter LLM integration)`
5. `feat: bettor module (place bet API)`
6. `feat: money manager (soft martingale)`
7. `feat: telegram notifier`
8. `feat: main.py scheduler + full integration`
9. `feat: dry-run mode for testing`

---

## DEPLOYMENT — Pull ke VPS

Setelah semua code di GitHub, tarik ke VPS:

```bash
# 1. Setup VPS
sudo apt update && sudo apt install -y python3.11 python3.11-venv git

# 2. Clone repo
cd ~
git clone https://github.com/<username>/hokidraw-bot.git
cd hokidraw-bot

# 3. Virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
nano .env  # Isi credentials asli

# 5. Test dry-run dulu
python main.py --dry-run

# 6. Run dengan systemd (production)
sudo tee /etc/systemd/system/hokidraw-bot.service << 'EOF'
[Unit]
Description=Hokidraw 2D Auto-Betting Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/hokidraw-bot
Environment=PATH=/home/ubuntu/hokidraw-bot/venv/bin:$PATH
ExecStart=/home/ubuntu/hokidraw-bot/venv/bin/python main.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hokidraw-bot
sudo systemctl start hokidraw-bot

# 7. Monitor
sudo journalctl -u hokidraw-bot -f

# 8. Update dari GitHub (kalau ada perubahan)
cd ~/hokidraw-bot
git pull origin main
sudo systemctl restart hokidraw-bot
```

---

## CLOUDFLARE HANDLING STRATEGY

Situs menggunakan Cloudflare protection. Strategi:

1. **Primary**: httpx dengan headers browser lengkap + cookie jar persisten
   - Copy semua headers dari HAR file (User-Agent, Accept, dll)
   - Maintain cookies across requests

2. **Fallback**: Jika httpx diblokir, gunakan Playwright headless browser
   ```python
   from playwright.async_api import async_playwright
   # Launch headless Chromium
   # Navigate, solve Cloudflare challenge
   # Extract cookies → transfer ke httpx untuk API calls
   ```

3. **Cookie refresh**: Setiap 30 menit, re-validate session

---

## IMPORTANT NOTES

1. **Togel adalah permainan RANDOM** - LLM tidak bisa memprediksi dengan akurasi tinggi. Bot ini adalah eksperimen, bukan jaminan profit.

2. **Daily loss limit WAJIB diimplementasi** - tanpa ini, martingale bisa menghabiskan saldo dalam hitungan jam.

3. **Mulai dengan bet minimum** (Rp 100/angka) untuk testing sebelum naikkan nominal.

4. **Log SEMUA aktivitas** - setiap API call, setiap prediksi, setiap taruhan. Ini penting untuk debugging dan evaluasi.

5. **CSRF Token** - harus diambil fresh sebelum setiap login. Parse dari homepage HTML.

6. **Bet amount format** - dikirim dalam ribuan (bet=1 artinya Rp 1.000). Untuk Rp 100, kirim bet=0.1

7. **Test dulu tanpa real money** - implementasi dry-run mode yang log semua aksi tanpa benar-benar betting.
