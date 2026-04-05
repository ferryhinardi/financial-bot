# Financial Tracker Bot (Indonesia)

Bot Telegram untuk mencatat keuangan pribadi, terintegrasi langsung dengan file Excel.
Dilengkapi analisis keuangan otomatis berdasarkan standar keuangan Indonesia (OJK & BI).

---

## Fitur Utama

### Excel Tracker (8 Sheet)
| Sheet | Fungsi |
|---|---|
| **Dashboard** | Ringkasan keuangan: income, spending, savings, net worth, grafik |
| **Advisor** | Analisis cerdas: skor kesehatan, aturan 40/30/20/10, panduan investasi ID, tips |
| **Transactions** | Catatan pengeluaran harian dengan kategori & dropdown |
| **Income** | Catatan pemasukan (gaji, freelance, dll.) |
| **Savings** | Tracking tabungan per akun, target & progress |
| **Assets** | Tracking aset & investasi (saham, reksadana, emas, properti) |
| **Budget** | Budget bulanan per kategori dengan status otomatis |
| **Config** | Konstanta keuangan Indonesia (PTKP, PPh, nisab zakat, BI rate) |

### Advisor Sheet (Analisis Indonesia)
- **Skor Kesehatan Keuangan** (8 indikator: savings rate, dana darurat, rasio utang, dll.)
- **Aturan 40/30/20/10** (adaptasi Indonesia: kebutuhan/keinginan/tabungan/sedekah)
- **Analisis Tren Bulanan** (advice otomatis per bulan dalam Bahasa Indonesia)
- **Peringatan Cerdas** (over budget, transaksi besar, kesiapan zakat)
- **Panduan Investasi Indonesia** (reksadana, SBN, saham, emas + pajak masing-masing)
- **Referensi BPJS & Pajak** (BPJS Kesehatan, JHT, JP, PPh 21)
- **12 Tips Keuangan** khusus konteks Indonesia (arisan, THR, kiriman keluarga, dll.)

### Telegram Bot
- **Onboarding** (`/start`, `/setup`): `/start` akan memulai setup jika belum selesai, `/setup` untuk menjalankan ulang
- **Quick input**: `/quick Rp50.000 makan nasi padang`
- **Guided input**: `/spend`, `/income`, `/save`
- **Reports**: `/summary`, `/budget`, `/savings`, `/dashboard`, `/recent`
- **Reminders**: `/remind` — Kelola tagihan rutin bulanan
- **Health check**: `/health` — Skor kesehatan keuangan dengan visualisasi
- **NLP input**: `/nlp on` — Aktifkan input bahasa natural, `/nlp off` — Nonaktifkan input bahasa natural
- **Indonesian keyword support**: makan, bensin, listrik, pulsa, kos, obat, dll.
- **Excel-first storage**: file `Financial_Tracker.xlsx` adalah source of truth utama

---

## Prasyarat

- **Python 3.10+** (tested: 3.12, 3.14)
- **Akun Telegram**
- **macOS / Linux / Windows WSL**

### Install nullclaw (untuk NLP feature)

Untuk mengaktifkan fitur NLP parsing bahasa natural Indonesia, install nullclaw:

```bash
# Deteksi arsitektur sistem
ARCH=$(uname -m)

# Install sesuai arsitektur
if [ "$ARCH" = "aarch64" ]; then
  wget https://github.com/nullclaw/nullclaw/releases/latest/download/nullclaw-linux-arm64 -O /usr/local/bin/nullclaw
else
  wget https://github.com/nullclaw/nullclaw/releases/latest/download/nullclaw-linux-amd64 -O /usr/local/bin/nullclaw
fi

# Berikan permission execute
chmod +x /usr/local/bin/nullclaw

# Verifikasi
nullclaw --version
```

---

## Langkah Setup Lengkap

### 1. Buat Bot di Telegram

1. Buka Telegram, cari **@BotFather**
2. Kirim `/newbot`
3. Masukkan nama bot (contoh: `My Financial Tracker`)
4. Masukkan username (harus diakhiri `bot`, contoh: `ferry_finance_bot`)
5. **Salin token** yang diberikan BotFather (format: `123456789:AABBccDDeeFF...`)

#### Set Commands (Opsional, Direkomendasikan)

Kirim `/setcommands` ke @BotFather, lalu paste:

```
start - Mulai bot atau onboarding pertama kali
setup - Setup profil keuangan awal
spend - Catat pengeluaran (guided)
quick - Cepat: /quick 50000 food makan siang
income - Catat pemasukan
save - Catat tabungan (deposit/penarikan)
summary - Ringkasan pengeluaran
budget - Status budget bulanan
savings - Ringkasan tabungan
dashboard - Dashboard keuangan lengkap
recent - Transaksi terakhir
categories - Daftar kategori
cancel - Batalkan operasi
```

### 2. Dapatkan User ID Telegram

1. Cari **@userinfobot** di Telegram
2. Kirim pesan apa saja
3. Catat **user ID** Anda (angka seperti `123456789`)

### 3. Clone & Konfigurasi

```bash
cd ~/Workspace/financial-bot

# Salin file konfigurasi
cp .env.example .env
```

Edit file `.env`:

```bash
nano .env
```

Isi dengan data Anda:

```env
# Token dari BotFather
TELEGRAM_BOT_TOKEN=123456789:AABBccDDeeFF...

# Path ke file Excel (default: direktori yang sama)
EXCEL_PATH=./Financial_Tracker.xlsx

# User ID Anda (opsional, untuk keamanan)
ALLOWED_USER_IDS=123456789

# Zona waktu
TIMEZONE=Asia/Jakarta
```

### 4. Install Dependencies

```bash
chmod +x setup.sh run.sh
./setup.sh
```

Output yang diharapkan:
```
==================================
 Financial Tracker Bot - Setup
==================================

[1/4] Creating virtual environment...
[2/4] Installing dependencies...
[3/4] Setting up configuration...
[4/4] Setup complete!
```

### 5. Generate File Excel (Opsional)

File `Financial_Tracker.xlsx` sudah tersedia. Jika ingin regenerate:

```bash
source venv/bin/activate
python create_financial_tracker.py
```

### 6. Jalankan Bot

```bash
./run.sh
```

Output:
```
Starting Financial Tracker Bot...
Bot started! Tracking: /full/path/to/Financial_Tracker.xlsx
Press Ctrl+C to stop.
```

### 7. Mulai Menggunakan Bot

1. Buka bot Anda di Telegram (contoh: t.me/ferry_finance_bot)
2. Kirim `/start`
3. Jika onboarding belum selesai, bot akan langsung memulai setup awal
4. Jika ingin mengulang setup kapan saja, kirim `/setup`

#### Onboarding Flow (Step 1-5)

| Step | Yang Ditanyakan | Contoh |
|---|---|---|
| 1. Tabungan | Saldo per akun (Dana Darurat, Liburan, Investasi, Pensiun) | Emergency Fund: Rp 10,000,000 |
| 2. Aset | Investasi & properti (saham, reksadana, emas, kendaraan) | Reksadana BCA: Rp 5,000,000 |
| 3. Income | Sumber pemasukan & jumlah bulanan | Gaji PT ABC: Rp 8,000,000/bulan |
| 4. Tagihan | Tagihan rutin bulanan (sewa, listrik, internet, BPJS) | Kos: Rp 2,000,000/bulan |
| 5. Budget | Batas pengeluaran per kategori | Food & Groceries: Rp 1,500,000 |

Setelah konfirmasi, semua data tersimpan ke Excel.

---

## Penggunaan Harian

### Quick Spend (Tercepat)

```bash
/quick 50000 food nasi padang
/quick Rp25.000 transport ojol kantor
/quick 150000 shopping baju
```

**Keyword Indonesia yang didukung:**
| Keyword | Kategori |
|---|---|
| `makan`, `food`, `groceries` | Food & Groceries |
| `transport`, `ojol`, `bensin`, `parkir` | Transportation |
| `kos`, `sewa`, `rent` | Housing |
| `hiburan`, `nonton`, `netflix` | Entertainment |
| `obat`, `dokter`, `health` | Healthcare |
| `buku`, `kursus`, `edu` | Education |
| `beli`, `shop`, `belanja` | Shopping |
| `listrik`, `air`, `pulsa`, `wifi`, `pln` | Bills & Utilities |

### Guided Spend

```
/spend
```
Bot akan bertanya satu per satu: jumlah → kategori → deskripsi → metode bayar.

### Catat Pemasukan

```
/income
```
Masukkan sumber, jumlah, dan kategori (Salary, Freelance, dll.)

### Tabungan

```
/save
```
Pilih akun, tipe (Deposit/Withdrawal), dan jumlah.

### Laporan

| Command | Apa yang ditampilkan |
|---|---|
| `/summary` | Total pengeluaran bulan ini, per kategori. Bisa pakai `/summary YYYY-MM` |
| `/budget` | Status budget: OK / WARNING / OVER BUDGET. Bisa pakai `/budget YYYY-MM` |
| `/savings` | Saldo tiap akun tabungan + progress target |
| `/dashboard` | Semua di atas + net worth. Bisa pakai `/dashboard YYYY-MM` |
| `/recent` | 5 transaksi terakhir, atau `/recent 10` untuk jumlah lain |

---

## Menjalankan Bot 24/7

### Opsi A: nohup (Paling Mudah)

```bash
cd ~/Workspace/financial-bot
source venv/bin/activate
nohup python bot.py > bot.log 2>&1 &

# Cek log
tail -f bot.log

# Stop bot
kill $(pgrep -f "python bot.py")
```

### Opsi B: screen (Direkomendasikan untuk Mac)

```bash
# Install screen (jika belum ada)
brew install screen

# Jalankan
screen -S finbot
cd ~/Workspace/financial-bot && ./run.sh

# Detach: tekan Ctrl+A lalu D
# Reattach: screen -r finbot
```

### Opsi C: systemd (Linux Server / VPS)

Buat file `/etc/systemd/system/finbot.service`:

```ini
[Unit]
Description=Financial Tracker Telegram Bot
After=network.target

[Service]
Type=simple
User=ferry
WorkingDirectory=/home/ferry/Workspace/financial-bot
ExecStart=/home/ferry/Workspace/financial-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
Environment=PATH=/home/ferry/Workspace/financial-bot/venv/bin

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable finbot
sudo systemctl start finbot

# Cek status
sudo systemctl status finbot
```

---

## Struktur File

```
financial-bot/
├── bot.py                      # Telegram bot utama
├── config.py                   # Load env + default path/settings
├── excel_manager.py            # Layer baca/tulis Excel
├── onboarding.py               # Flow setup awal (5 langkah)
├── create_financial_tracker.py # Generator file Excel
├── Financial_Tracker.xlsx      # File Excel tracker
├── requirements.txt            # Python dependencies
├── setup.sh                    # Script instalasi
├── run.sh                      # Script menjalankan bot
├── .env                        # Konfigurasi (JANGAN commit!)
├── .env.example                # Template konfigurasi
├── n8n-workflow.json           # Workflow eksperimen alternatif
├── tests/                      # Unit + integration-style tests
├── onboarding_state.json       # State onboarding (auto-generated)
└── backups/                    # Auto-backup Excel (auto-generated)
```

---

## Kategori Pengeluaran

| Kategori | Contoh Pengeluaran |
|---|---|
| Food & Groceries | Makan, belanja bulanan, kopi |
| Transportation | Ojol, bensin, parkir, tol, KRL |
| Housing | Kos, sewa, cicilan rumah (KPR) |
| Entertainment | Nonton, Netflix, Spotify, game |
| Healthcare | Obat, dokter, BPJS Kesehatan |
| Education | Kursus, buku, les |
| Shopping | Baju, gadget, barang non-kebutuhan |
| Bills & Utilities | Listrik (PLN), air (PDAM), internet, pulsa |

---

## Akun Tabungan

| Akun | Kegunaan |
|---|---|
| Emergency Fund | Dana darurat (target: 6 bulan pengeluaran) |
| Vacation | Tabungan liburan / mudik |
| Investment | Dana investasi (reksadana, saham, dll.) |
| Retirement | Dana pensiun (DPLK, dll.) |
| Other | Tabungan lain-lain |

---

## Advisor: Standar Keuangan Indonesia

### Skor Kesehatan (8 Indikator)

| Indikator | Target Ideal | Sumber |
|---|---|---|
| Savings Rate | >= 20% | OJK / Financial Planner ID |
| Dana Darurat | >= 6 bulan (karyawan tetap) | OJK |
| Rasio Pengeluaran | <= 70% income | - |
| Kepatuhan Budget | 100% on budget | - |
| Kebutuhan vs Keinginan | 40-50% kebutuhan pokok | Aturan 40/30/20/10 |
| Alokasi Investasi | >= 30% net worth | - |
| Rasio Utang (DTI) | < 30% | Bank Indonesia |
| Pertumbuhan Net Worth | > inflasi (3.5%) | BI target |

### Aturan 40/30/20/10 (Adaptasi Indonesia)

| Alokasi | Persentase | Contoh (Gaji Rp 8jt) |
|---|---|---|
| Kebutuhan Pokok | 40% | Rp 3,200,000 (makan, transport, kos, listrik) |
| Keinginan | 30% | Rp 2,400,000 (hiburan, belanja, nongkrong) |
| Tabungan & Investasi | 20% | Rp 1,600,000 (reksadana, deposito, SBN) |
| Sedekah/Zakat/Keluarga | 10% | Rp 800,000 (zakat, infaq, kirim ortu) |

### Panduan Investasi Indonesia (di Advisor sheet)

| Instrumen | Return/tahun | Pajak |
|---|---|---|
| Reksadana Pasar Uang | 3-5% | **BEBAS PAJAK** |
| Reksadana Saham | 8-15% | **BEBAS PAJAK** |
| SBN Ritel (ORI/SBR) | 5-7% | 10% kupon |
| Deposito | 3-5% | 20% bunga |
| Saham (IDX) | 10-15% | 0.1% jual |
| Emas (Antam) | 5-10% | PPh capital gain |

---

## Config Sheet (Update Manual)

Nilai di sheet Config bisa di-update sesuai kondisi terkini:

| Parameter | Default | Keterangan |
|---|---|---|
| PTKP TK/0 | Rp 54,000,000 | Penghasilan Tidak Kena Pajak (lajang) |
| Nisab Zakat | Rp 85,000,000 | ~85 gram emas (update sesuai harga emas) |
| BI Rate | 5.75% | Suku bunga acuan BI |
| Inflasi Target | 3.5% | Target Bank Indonesia |
| UMP Jakarta | Rp 5,500,000 | Upah Minimum Provinsi |

---

## Keamanan

- **JANGAN commit file `.env`** ke git (sudah ada di `.gitignore`)
- File Excel berisi data keuangan pribadi -- simpan dengan aman
- Gunakan `ALLOWED_USER_IDS` di `.env` agar hanya Anda yang bisa akses bot
- **Revoke & regenerate bot token** jika pernah terekspos:
  - Kirim `/revoke` ke @BotFather
  - Pilih bot Anda
  - Update token baru di `.env`

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| Bot tidak merespons | Cek token di `.env`, pastikan bot running |
| `ModuleNotFoundError` | Jalankan `source venv/bin/activate` dulu |
| Excel tidak berubah | Pastikan `EXCEL_PATH` di `.env` benar |
| Permission denied | `chmod +x setup.sh run.sh` |
| Port already in use | `kill $(pgrep -f "python bot.py")` lalu jalankan ulang |
| Onboarding minta ulang | Hapus `onboarding_state.json` untuk reset |
| Excel corrupt | Cek folder `backups/` untuk file backup terakhir |

---

## Alternatif Eksperimental: n8n Workflow (Visual Automation)

n8n adalah platform automation visual yang bisa menghubungkan Telegram bot ke berbagai layanan.
File `n8n-workflow.json` tersedia sebagai eksperimen terpisah, bukan jalur setup utama project ini.
Untuk penggunaan harian dengan file Excel lokal, gunakan `bot.py`.

### Install n8n

n8n sudah terinstall di sistem ini via npm:

```bash
# Install (sudah dilakukan)
npm install -g n8n

# Verifikasi
n8n --version
# Output: 2.12.3
```

### Menjalankan n8n

```bash
# Start n8n
n8n start

# n8n akan berjalan di:
# http://localhost:5678
```

Buka browser ke **http://localhost:5678**

Pada pertama kali, n8n akan minta:
1. **Email** dan **Password** untuk membuat akun owner
2. Isi data, lalu login

### Import Workflow

1. Di n8n dashboard, klik **"Add workflow"** (tombol + di sidebar kiri)
2. Klik **menu "..."** (tiga titik) di pojok kanan atas
3. Pilih **"Import from file..."**
4. Pilih file: `~/Workspace/financial-bot/n8n-workflow.json`
5. Workflow akan muncul dengan node-node berikut:

```
[Telegram Trigger] → [Route Commands] → [Parse Quick Command] → [Write to Sheet] → [Send Confirmation]
```

### Setup Telegram Credential di n8n

1. Klik node **"Telegram Trigger"**
2. Di bagian **Credential**, klik **"Create New"**
3. Masukkan **Bot Token** Anda sendiri dari `@BotFather`
4. Klik **Save**
5. Lakukan hal yang sama untuk node **"Send Confirmation"**

### Setup Google Sheets (Opsional)

n8n tidak bisa langsung menulis ke file `.xlsx` lokal. Ada 2 opsi:

**Opsi A: Gunakan Google Sheets (Recommended untuk n8n)**
1. Upload `Financial_Tracker.xlsx` ke Google Drive
2. Buka sebagai Google Sheets
3. Di n8n, klik node **"Write to Google Sheet"**
4. Setup Google credential (OAuth2)
5. Pilih spreadsheet dan sheet "Transactions"

**Opsi B: Gunakan Python Bot (Recommended untuk Excel lokal)**
- Gunakan `bot.py` untuk integrasi langsung ke file Excel
- Ini adalah jalur utama yang didokumentasikan di README ini

### Mengaktifkan Workflow

1. Setelah semua credential diset, klik toggle **"Active"** di pojok kanan atas
2. Workflow akan mulai mendengarkan pesan Telegram
3. Coba kirim `/quick 50000 food nasi padang` ke bot

### Menjalankan n8n di Background

```bash
# Opsi 1: nohup
nohup n8n start > ~/.n8n/n8n.log 2>&1 &

# Opsi 2: screen
screen -S n8n
n8n start
# Ctrl+A, D untuk detach
# screen -r n8n untuk reattach

# Opsi 3: Docker (paling stabil untuk production)
docker run -d --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### Menghentikan n8n

```bash
# Jika pakai nohup
kill $(pgrep -f "n8n start")

# Jika pakai Docker
docker stop n8n
```

### n8n vs Python Bot - Perbandingan

| Fitur | Python Bot | n8n |
|---|---|---|
| Integrasi Excel lokal | Ya (langsung) | Tidak (perlu Google Sheets) |
| Visual workflow editor | Tidak | Ya |
| Onboarding setup | Ya (5 langkah) | Tidak |
| Smart advisor | Ya | Tidak |
| Mudah dimodifikasi | Perlu coding | Drag & drop |
| Hosting | Script Python | Web server (port 5678) |
| Cocok untuk | Power user | Non-developer |

> **Rekomendasi**: Gunakan **Python Bot** (`bot.py`) untuk fitur lengkap dengan Excel lokal.
> Gunakan **n8n** jika ingin mengintegrasikan dengan layanan lain (Google Sheets, Notion, Slack, dll).

---

## Deploy ke Oracle Cloud (Gratis Selamanya)

Oracle Cloud Free Tier memberikan **2 VM gratis selamanya** dengan 1GB RAM masing-masing.
Ini cukup untuk menjalankan bot 24/7.

### Langkah 1: Buat Akun Oracle Cloud

1. Buka **https://cloud.oracle.com/free**
2. Klik **"Start for Free"**
3. Isi data (perlu kartu kredit untuk verifikasi, tapi TIDAK akan dicharge)
4. Pilih **Home Region**: `ap-singapore-1` (Singapore) atau `ap-tokyo-1` (Tokyo) untuk latency rendah dari Indonesia
5. Tunggu email aktivasi (biasanya 5-15 menit)

### Langkah 2: Buat VM (Virtual Machine)

1. Login ke **Oracle Cloud Console**: https://cloud.oracle.com
2. Klik **"Create a VM instance"** atau navigasi ke: Compute > Instances > Create Instance
3. Konfigurasi:
   - **Name**: `financial-bot`
   - **Image**: Ubuntu 22.04 (atau 24.04)
   - **Shape**: `VM.Standard.E2.1.Micro` (Always Free eligible - 1 OCPU, 1GB RAM)
   - **Networking**: Biarkan default (buat VCN baru)
   - **SSH Keys**: 
     - Pilih **"Generate a key pair"** lalu **Download private key** (simpan baik-baik!)
     - Atau upload public key dari Mac: `cat ~/.ssh/id_rsa.pub`
4. Klik **"Create"**
5. Tunggu status berubah ke **RUNNING** (1-3 menit)
6. Catat **Public IP Address** (contoh: `129.150.xx.xx`)

### Langkah 3: Buka Port (Firewall)

Bot Telegram hanya membutuhkan **outbound** traffic (sudah terbuka by default).
Tidak perlu membuka port inbound kecuali untuk SSH (port 22, sudah terbuka).

Jika ingin menjalankan n8n juga (port 5678):

1. Di Oracle Console: Networking > Virtual Cloud Networks
2. Klik VCN Anda > Klik Subnet > Klik Security List
3. **Add Ingress Rule**:
   - Source CIDR: `0.0.0.0/0`
   - Destination Port: `5678`
   - Description: `n8n`
4. SSH ke VM dan buka iptables juga:
   ```bash
   sudo iptables -I INPUT -p tcp --dport 5678 -j ACCEPT
   sudo netfilter-persistent save
   ```

### Langkah 4: Connect ke VM

```bash
# Dari Mac Anda:
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<PUBLIC_IP>

# Contoh:
ssh -i ~/Downloads/ssh-key-2026-03-19.key ubuntu@129.150.42.123
```

Jika error `permission too open`:
```bash
chmod 400 ~/Downloads/ssh-key-*.key
```

### Langkah 5: Upload Project ke VM

Dari Mac Anda (terminal baru):

```bash
# Upload semua file project
scp -i ~/Downloads/ssh-key-*.key -r \
  ~/Workspace/financial-bot \
  ubuntu@<PUBLIC_IP>:~/

# Contoh:
scp -i ~/Downloads/ssh-key-2026-03-19.key -r \
  ~/Workspace/financial-bot \
  ubuntu@129.150.42.123:~/
```

### Langkah 6: Setup di VM

SSH ke VM, lalu jalankan:

```bash
# Masuk ke VM
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<PUBLIC_IP>

# Jalankan setup script
cd ~/financial-bot
chmod +x deploy-oracle.sh
./deploy-oracle.sh
```

Script ini akan:
- Install Python 3, pip, venv
- Buat virtual environment
- Install dependencies
- Generate Financial_Tracker.xlsx
- Setup systemd service (auto-start saat VM boot)

### Langkah 7: Konfigurasi Bot Token

```bash
nano ~/financial-bot/.env
```

Isi dengan:
```env
TELEGRAM_BOT_TOKEN=<TOKEN_BOT_ANDA>
EXCEL_PATH=./Financial_Tracker.xlsx
ALLOWED_USER_IDS=<TELEGRAM_USER_ID_ANDA>
TIMEZONE=Asia/Jakarta
```

Simpan: `Ctrl+O`, `Enter`, `Ctrl+X`

### Langkah 8: Start Bot

```bash
# Start bot sebagai service
sudo systemctl start financial-bot

# Cek apakah berjalan
sudo systemctl status financial-bot

# Lihat log real-time
sudo journalctl -u financial-bot -f
```

### Langkah 9: Verifikasi

1. Buka Telegram
2. Chat ke bot Anda
3. Kirim `/start`
4. Kirim `/setup` untuk onboarding

### Perintah Management VM

```bash
# Cek status bot
sudo systemctl status financial-bot

# Restart bot
sudo systemctl restart financial-bot

# Stop bot
sudo systemctl stop financial-bot

# Lihat log (100 baris terakhir)
sudo journalctl -u financial-bot -n 100

# Lihat log real-time
sudo journalctl -u financial-bot -f

# Update bot (setelah upload file baru)
sudo systemctl restart financial-bot

# Download Excel ke Mac (dari terminal Mac)
scp -i ~/Downloads/ssh-key-*.key \
  ubuntu@<PUBLIC_IP>:~/financial-bot/Financial_Tracker.xlsx \
  ~/Downloads/
```

### Update Bot di VM

Jika ada perubahan code:

```bash
# Dari Mac:
scp -i ~/Downloads/ssh-key-*.key -r \
  ~/Workspace/financial-bot/*.py \
  ubuntu@<PUBLIC_IP>:~/financial-bot/

# Di VM:
sudo systemctl restart financial-bot
```

### Deploy dengan Docker (Alternatif)

Jika lebih suka Docker:

```bash
# Di VM
sudo apt install -y docker.io
sudo usermod -aG docker $USER
# Logout & login kembali

# Build & run
cd ~/financial-bot
docker build -t financial-bot .
docker run -d --name finbot \
  --restart=always \
  -v ~/financial-bot/.env:/app/.env \
  -v ~/financial-bot/Financial_Tracker.xlsx:/app/Financial_Tracker.xlsx \
  financial-bot
```

### Estimasi Biaya

| Resource | Biaya |
|---|---|
| VM.Standard.E2.1.Micro | **Rp 0 (gratis selamanya)** |
| Boot Volume 50GB | **Rp 0 (gratis)** |
| Outbound bandwidth 10TB/bulan | **Rp 0 (gratis)** |
| Public IP | **Rp 0 (gratis)** |
| **Total** | **Rp 0/bulan** |

---

## Lisensi

Personal use. Created for financial tracking purposes.
