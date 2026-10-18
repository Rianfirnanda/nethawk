@echo off
REM Build NetHawk menjadi satu file .exe (Windows) dengan PyInstaller.
REM Jalankan dari folder proyek:  build.bat

echo ==> Menginstall dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo ==> Membangun NetHawk.exe...
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name NetHawk ^
  --uac-admin ^
  --add-data "web;web" ^
  --collect-all scapy ^
  --collect-all pydivert ^
  --collect-all aiohttp ^
  --collect-all mac_vendor_lookup ^
  main.py
if errorlevel 1 goto :error

echo.
echo SELESAI. EXE ada di: dist\NetHawk.exe
echo Tip debugging: ganti --windowed jadi --console untuk melihat error.
goto :eof

:error
echo.
echo GAGAL build. Cek pesan error di atas.
exit /b 1
