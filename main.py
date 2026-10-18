"""NetHawk entry point.

Ensures Administrator rights (needed for Npcap raw packet access), then starts
the local web server which opens the browser UI. Fatal errors are shown in a
native message box so the windowed .exe never dies silently.
"""
import ctypes
import os
import sys
import traceback


def is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    try:
        params = " ".join(f'"{a}"' for a in sys.argv)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1)
        return rc > 32
    except Exception:
        return False


def msgbox(title, text):
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        pass


def main():
    if os.name == "nt" and not is_admin():
        if relaunch_as_admin():
            return
        msgbox("NetHawk", "Tidak berjalan sebagai Administrator.\n"
               "Scan & cut kemungkinan gagal. Tutup lalu buka lagi via "
               "klik kanan → Run as administrator.")
    try:
        from server import run
        run()
    except Exception as e:
        msgbox("NetHawk — Error", "Gagal memulai aplikasi:\n\n%s\n\n%s"
               % (e, traceback.format_exc()))


if __name__ == "__main__":
    main()
