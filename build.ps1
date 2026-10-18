# Build NetHawk menjadi satu file .exe (Windows) dengan PyInstaller.
# Jalankan dari folder proyek:  powershell -ExecutionPolicy Bypass -File build.ps1
#
# Catatan:
#  - Build TIDAK perlu admin, tapi .exe hasilnya minta "Run as administrator" otomatis.
#  - Npcap harus terpasang di komputer yang MENJALANKAN .exe (bukan saat build).

$ErrorActionPreference = "Stop"

Write-Host "==> Menginstall dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

$iconArg = @()
if (Test-Path "assets\icon.ico") { $iconArg = @("--icon", "assets\icon.ico") }

Write-Host "==> Membangun NetHawk.exe..." -ForegroundColor Cyan
pyinstaller --noconfirm --clean --onefile --windowed `
  --name NetHawk `
  --uac-admin `
  --add-data "web;web" `
  --collect-all scapy `
  --collect-all pydivert `
  --collect-all aiohttp `
  --collect-all mac_vendor_lookup `
  @iconArg `
  main.py

Write-Host ""
Write-Host "SELESAI. EXE ada di: dist\NetHawk.exe" -ForegroundColor Green
Write-Host "Tip debugging: ganti --windowed jadi --console untuk melihat error di terminal." -ForegroundColor Yellow
