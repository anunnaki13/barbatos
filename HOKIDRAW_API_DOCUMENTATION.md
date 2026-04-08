# Hokidraw Bot — API Documentation
## Hasil Analisis HAR File partai34848.com

---

## 1. IDENTITAS HOKIDRAW
- **Pool ID**: `p76368`
- **Internal Code**: `OKAQ`
- **Jadwal**: 24x sehari, setiap 1 jam
- **Situs resmi draw**: https://hokidraw.com
- **Base URL**: `https://partai34848.com`

---

## 2. AUTHENTICATION

### Login
```
POST /json/post/ceklogin-ts
Content-Type: application/json
X-Requested-With: XMLHttpRequest

{
  "entered_login": "<username>",
  "entered_password": "<password>",
  "liteMode": "",
  "_token": "<csrf_token>"
}
```
**Catatan**: `_token` adalah CSRF token yang harus diambil dulu dari halaman sebelumnya.

### Session Check
```
GET /json/post/validate-login
```

### Logout
```
GET /logout
```

---

## 3. BETTING (ENDPOINT UTAMA)

### Submit Bet — Quick 2D
```
POST /games/4d/send
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest

Parameters:
  type=B              # B = BET FULL, D = BET DISKON, A = BET BB
  ganti=F             # Fixed value
  game=quick_2d       # Game type
  bet=0.1             # Nominal per angka (dalam ribuan: 0.1 = Rp 100)
  posisi=belakang     # Posisi 2D (belakang = 2 digit terakhir)
  cek1=1              # Flag angka ke-1 aktif
  tebak1=50           # Angka tebakan ke-1
  cek2=1              # Flag angka ke-2 aktif
  tebak2=51           # Angka tebakan ke-2
  ... (sampai cekN / tebakN)
  sar=p76368          # Pool ID Hokidraw
```

### Response Sukses
```json
{
  "status": true,
  "transaksi": "50@@C@@100@@0.00@@0@@100@@100@@10000@@B//51@@C@@...",
  "error": "",
  "periode": "11037 - HOKIDRAW",
  "balance": "40013.00"
}
```
**Format transaksi**: `angka@@status@@taruhan@@diskon@@?@@bayar@@?@@potensi_menang@@type//`

### Tipe Bet
| Code | Nama | Keterangan |
|------|------|------------|
| B | BET FULL | Bayar penuh, hadiah penuh (x100 untuk 2D) |
| D | BET DISKON | Ada diskon taruhan, hadiah lebih kecil |
| A | BET BB | Bolak-Balik |

### Limits (dari hidden fields)
| Parameter | Min | Max | Max BB |
|-----------|-----|-----|--------|
| 2D | 100 (Rp 100) | 2,000,000 | 2,000,000 |
| 3D | 100 | 500,000 | 250,000 |
| 4D | 100 | 50,000 | 25,000 |

### Unit & Konversi
- `bet=0.1` → Rp 100 (IDR 1.000 = 1 unit)
- `bet=1` → Rp 1.000
- `bet=5` → Rp 5.000
- Kelipatan: 100 (unit `z2dlipat`)

### Hadiah 2D BET FULL
- **x100** → Bet Rp 1.000 menang Rp 100.000

---

## 4. GAME DATA

### Load Game Page
```
GET /games/4d/p76368
```
**Hidden fields penting**:
- `timerpools` = detik tersisa sampai betting ditutup
- `periode` = nomor periode aktif

### Load Quick 2D Panel
```
GET /games/4d/load/quick_2d/p76368
```
Response: HTML form betting

### Load 4D Panel (full)
```
GET /games/4d/load/4d/p76368
```
Response: HTML form + semua hidden fields (limits, balance, dll)

---

## 5. HISTORY & RESULTS

### History Nomor (Public, tanpa login)
```
GET /history/v2                         # History page
GET /history/detail/p76368-pool         # Hokidraw history page
GET /history/detail/data/p76368-1       # Hokidraw history DATA (JSON)
```
**Catatan**: Response body kosong di HAR (lazy-loaded). Perlu diakses langsung.

### Bet History (Setelah login)
```
GET /games/4d/history/quick_2d/p76368
GET /games/4d/history/4d/p76368
```
Response: HTML table dengan kolom No, Tebakan, Taruhan, Diskon, Bayar, Type, Menang

---

## 6. BALANCE & ACCOUNT

### Check Balance
```
POST /request-balance
X-Requested-With: XMLHttpRequest
```

### Check Memo Count
```
POST /request-memo-count
```

---

## 7. JADWAL PASARAN (External API)

```
GET https://jampasaran.smbgroup.io/pasaran
```
Response:
```json
{
  "status": "success",
  "ep": "geng1.com",
  "data": {
    "hokidraw": 1138,
    "totocambodia": 72238,
    "poipet12": 77638,
    ...
  }
}
```
**Nilai = detik sampai draw berikutnya** (1138 detik ≈ 19 menit)

---

## 8. WEBSOCKET (Real-time)

### Draw Results Push
```
wss://sbstat.hokibagus.club/smb/az2/socket.io/?EIO=3&transport=websocket
```
Socket.io v3, kemungkinan push event saat draw result keluar.

### Live Games
```
wss://realtime.dewab2b.com/socket.io/?EIO=4&transport=websocket
```
Socket.io v4, untuk live game updates.

---

## 9. BOT FLOW SUMMARY

```
1. Login      → POST /json/post/ceklogin-ts
2. Get Timer  → GET /games/4d/p76368 (parse timerpools)
               atau GET https://jampasaran.smbgroup.io/pasaran
3. Get History → GET /history/detail/data/p76368-1
4. Predict    → Kirim history ke OpenRouter LLM
5. Place Bet  → POST /games/4d/send (quick_2d, type=B)
6. Check Win  → GET /games/4d/history/quick_2d/p76368
7. Balance    → POST /request-balance
8. Repeat     → Loop setiap jam
```

---

## 10. SECURITY NOTES

- CSRF token diperlukan untuk login (`_token` field)
- Cloudflare challenge-platform aktif (anti-bot)
- Session cookies diperlukan untuk semua request setelah login
- X-Requested-With: XMLHttpRequest header wajib untuk AJAX calls
- Password dikirim plain (tidak di-hash MD5 di sisi client berdasarkan HAR)
