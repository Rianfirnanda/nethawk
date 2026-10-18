# NetHawk 🦅

NetHawk itu semacam "ruang kendali" buat Wi-Fi-mu, dan semuanya jalan di browser. Scan siapa aja yang lagi nyambung, intip mereka lagi buka situs apa, batasi kecepatan atau putus yang bikin boros, blokir situs, sampai atur kuota ala hotspot cafe — semua dari satu dashboard yang (semoga) enak dilihat.

Awalnya cuma pengin bikin alternatif NetCut. Eh, keterusan, ujung-ujungnya malah lebih mirip **ntopng** yang dikawinkan sama tool manajemen jaringan. Dibungkus jadi satu file `.exe` — tinggal dobel-klik, browser-nya kebuka sendiri.

> ⚠️ **Baca ini dulu:** pakai NetHawk cuma di jaringan **milikmu sendiri atau yang kamu punya izin**. Ini bukan mainan buat jahilin WiFi tetangga.

---

## Apa aja yang bisa dilakuin

**Lihat & pantau**
- Scan jaringan kilat — nemu semua perangkat beserta IP, MAC, vendor, dan tebakan tipe (HP, laptop, router, dll).
- Dashboard realtime gaya ntopng: grafik throughput, jumlah flow aktif, top protokol (donut chart), top endpoint, status interface.
- **Aktivitas** — lihat domain/situs yang lagi dibuka tiap perangkat, diambil dari DNS & SNI.

**Kendalikan**
- Putus internet perangkat — satu, beberapa, atau semuanya sekaligus.
- Batasi kecepatan (throttle) per perangkat.
- Blokir situs — per perangkat, atau borongan pakai kategori (sosmed, video, game, dewasa, iklan & tracker).
- Jadwal otomatis buat parental control: putus atau blokir di jam-jam tertentu.

**Mode bisnis / cafe — Hotspot Controller**
- Kuota data & waktu per perangkat, auto-putus begitu habis ("gratis 1 jam" gampang dibikin).
- Mode Tamu: batasi kecepatan semua tamu sekaligus biar adil.
- Role **Guest / Staff / Block** — perangkat Staff nggak akan pernah kena batas atau kuota.
- Auto-blokir perangkat baru sampai kamu approve.
- Export laporan pemakaian ke CSV buat catatan.

**Keamanan**
- Proteksi ARP (anti-NetCut) — ketahuan kalau ada yang nyoba nge-cut kamu.
- Blokir iklan & tracker se-jaringan (gaya Pi-hole ringan).

---

## Cara pakai

Cara tercepat: **build `.exe`-nya** (lihat di bawah), terus **klik kanan → Run as administrator**. Browser default kamu bakal kebuka sendiri ke `http://127.0.0.1:8787`.

Yang kamu butuhin:
- Windows 10/11
- **Npcap** → <https://npcap.com> (waktu install, centang *"WinPcap API-compatible Mode"*)
- Jalan sebagai **Administrator** — wajib, karena butuh akses jaringan level rendah

### Jalan dari source (buat ngoprek)
```bash
pip install -r requirements.txt
python main.py
```

### Build jadi .exe sendiri
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```
Hasilnya ada di `dist\NetHawk.exe` — satu file, otomatis minta izin admin pas dibuka.

> Catatan: NetHawk jalan sebagai server tanpa jendela, jadi nutup tab browser **nggak** otomatis matiin dia. Buat benar-benar berhenti, ada tombol **⏻ Matikan NetHawk** di tab Setelan.

---

## Di balik layar

- **Python** + **aiohttp** — web server plus WebSocket buat update realtime
- **Scapy** — ARP scan & spoofing
- **WinDivert** (pydivert) — engine MITM buat throttle, blokir situs, dan baca domain
- **psutil** — statistik throughput & koneksi aktif
- **PyInstaller** — bungkus semua jadi satu `.exe`
- Frontend: HTML/CSS/JS murni, tanpa framework, tanpa CDN — biar tetap jalan walau offline

---

## Jujur soal batasannya

Biar nggak kebanyakan janji:

- NetHawk cuma bisa lihat trafik perangkat yang lagi kamu **"Awasi"** (trafiknya sengaja dialihkan lewat laptopmu). Di Wi-Fi biasa, trafik perangkat lain nggak kelihatan secara pasif — beda sama ntopng yang biasanya dipasang langsung di gateway atau mirror port.
- Yang kelihatan cuma **nama domain** (misal `youtube.com`), bukan isi halaman HTTPS-nya.
- **Throttle & blokir situs** butuh IP forwarding Windows aktif — kadang perlu restart sekali biar jalan.
- Fokus ke **satu subnet** (jaringan lokalmu).
- HP modern pakai MAC acak, jadi vendornya sering muncul "unknown". Itu normal, bukan bug.

---

## Legal & etika

Tool ini sifatnya *dual-use*. Fitur ARP (cut/throttle) cuma buat jaringan yang kamu **miliki atau punya izin tertulis** — rumah, cafe sendiri, lab, atau uji keamanan yang memang diizinkan. Dipakai di jaringan orang lain tanpa izin itu melanggar hukum, dan risikonya ada di kamu. Pakai dengan kepala dingin.

---

## Terima kasih

Terinspirasi dari **elmocut**, **NetCut**, dan **ntopng**. Dibangun pelan-pelan sambil belajar jaringan.
