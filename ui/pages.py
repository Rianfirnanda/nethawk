"""All NetHawk v2 pages (Dashboard, Perangkat, Blokir Situs, Proteksi, Setelan)
plus the schedule dialog. Each page takes the shared AppState."""
import os

from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPlainTextEdit, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QInputDialog, QMessageBox, QDialog, QDialogButtonBox, QCheckBox,
    QComboBox, QTimeEdit, QScrollArea, QFrame, QProgressBar, QSizePolicy)

from core import config
from core.firewall import CATEGORIES
from .theme import (ACCENT, ACCENT2, TEXT, DIM, MUTED, DANGER, WARN, BORDER,
                    SURFACE2, BG2)
from .widgets import (StatTile, Sparkline, ToggleSwitch, Badge, Card,
                      human_rate, human_bytes)
from .charts import ThroughputChart
from .appstate import ScanWorker


def _h1(text):
    l = QLabel(text); l.setObjectName("h1"); return l


def _h2(text):
    l = QLabel(text); l.setObjectName("h2"); return l


def _dim(text):
    l = QLabel(text); l.setObjectName("dim"); return l


def _scroll(inner):
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(inner)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return sa


# =====================================================================
# Dashboard
# =====================================================================
class DashboardPage(QWidget):
    def __init__(self, st):
        super().__init__()
        self.st = st
        self.setObjectName("page")
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)

        root.addWidget(_h1("Dashboard"))
        self.sub = _dim("Memuat jaringan…")
        root.addWidget(self.sub)

        # stat tiles
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        self.t_dev = StatTile("Perangkat", "\U0001F5A5", TEXT)
        self.t_online = StatTile("Online", "\U0001F7E2", ACCENT)
        self.t_cut = StatTile("Diputus", "✂", DANGER)
        self.t_managed = StatTile("Dikelola", "\U0001F441", ACCENT2)
        self.t_blocked = StatTile("Blokir", "\U0001F6AB", WARN)
        for t in (self.t_dev, self.t_online, self.t_cut, self.t_managed,
                  self.t_blocked):
            tiles.addWidget(t)
        root.addLayout(tiles)

        # hero chart
        chart_card = Card()
        cc = QVBoxLayout(chart_card)
        cc.setContentsMargins(18, 16, 18, 14)
        cc.addWidget(_h2("Lalu lintas jaringan — realtime"))
        self.chart = ThroughputChart()
        cc.addWidget(self.chart)
        root.addWidget(chart_card)

        # bottom row: top talkers + activity log
        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        talk_card = Card()
        tl = QVBoxLayout(talk_card)
        tl.setContentsMargins(18, 16, 18, 16)
        tl.addWidget(_h2("Top Talkers"))
        self.talk_hint = _dim("Kelola perangkat untuk melihat pemakaian per-device.")
        tl.addWidget(self.talk_hint)
        self.talk_box = QVBoxLayout()
        self.talk_box.setSpacing(8)
        tl.addLayout(self.talk_box)
        tl.addStretch(1)
        bottom.addWidget(talk_card, 1)

        log_card = Card()
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(18, 16, 18, 16)
        ll.addWidget(_h2("Aktivitas"))
        self.loglist = QPlainTextEdit()
        self.loglist.setReadOnly(True)
        self.loglist.setMaximumBlockCount(300)
        ll.addWidget(self.loglist)
        bottom.addWidget(log_card, 1)
        root.addLayout(bottom)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(body))

    def append_log(self, line):
        self.loglist.appendPlainText(line)

    def tick(self, up, down, rates):
        self.chart.push(up, down)

    def refresh(self, up_total, down_total):
        st = self.st
        total = len(st.devices)
        cut = sum(1 for d in st.devices.values() if st.is_cut(d))
        managed = len(st.engine.managed_ips())
        blocked = st.engine.blocked_hits()
        online = total - cut
        self.t_dev.set_value(total)
        self.t_online.set_value(max(0, online))
        self.t_cut.set_value(cut)
        self.t_managed.set_value(managed)
        self.t_blocked.set_value(blocked)
        if st.net.ok:
            self.sub.setText("%s   •   %s perangkat terdeteksi"
                             % (st.net.summary(), total))

    def set_talkers(self, rates):
        # clear
        while self.talk_box.count():
            item = self.talk_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        pairs = []
        for mac, dev in self.st.devices.items():
            up, down = rates.get(dev["ip"], (0, 0))
            tot = up + down
            if tot > 0:
                pairs.append((tot, dev))
        pairs.sort(key=lambda x: x[0], reverse=True)
        pairs = pairs[:5]
        self.talk_hint.setVisible(not pairs)
        mx = pairs[0][0] if pairs else 1
        for tot, dev in pairs:
            name = dev.get("name") or dev["ip"]
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(10)
            lbl = QLabel("%s  %s" % (dev.get("emoji", ""), name))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(tot / mx * 100))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                "QProgressBar{background:%s;border:none;border-radius:4px;}"
                "QProgressBar::chunk{background:%s;border-radius:4px;}"
                % (BG2, ACCENT))
            val = QLabel(human_rate(tot))
            val.setStyleSheet("color:%s;font-weight:700;" % DIM)
            rl.addWidget(lbl, 2)
            rl.addWidget(bar, 3)
            rl.addWidget(val, 0)
            self.talk_box.addWidget(row)


# =====================================================================
# Perangkat (Devices)
# =====================================================================
COLS = ["Perangkat", "IP Address", "MAC", "Vendor", "Nama", "Status",
        "↓", "↑"]
C_TYPE, C_IP, C_MAC, C_VEN, C_NAME, C_STAT, C_DOWN, C_UP = range(8)


class DevicesPage(QWidget):
    def __init__(self, st, on_devices_changed=None):
        super().__init__()
        self.st = st
        self.on_devices_changed = on_devices_changed
        self.rows = {}        # mac -> row
        self.setObjectName("page")
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 20)
        root.setSpacing(14)

        head = QHBoxLayout()
        head.addWidget(_h1("Perangkat"))
        head.addStretch(1)
        self.count = _dim("0 perangkat")
        head.addWidget(self.count)
        head.addSpacing(10)
        b_all = QPushButton("✂ Semua"); b_all.setObjectName("danger")
        b_all.setToolTip("Putus internet semua perangkat")
        b_all.clicked.connect(self.act_cut_all)
        b_res = QPushButton("✓ Semua")
        b_res.setToolTip("Pulihkan semua perangkat")
        b_res.clicked.connect(self.act_restore_all)
        self.btn_scan = QPushButton("⟳ Scan")
        self.btn_scan.setObjectName("primary")
        self.btn_scan.clicked.connect(self.start_scan)
        for b in (b_all, b_res, self.btn_scan):
            b.setStyleSheet("padding:8px 13px;")
        head.addWidget(b_all)
        head.addWidget(b_res)
        head.addSpacing(6)
        head.addWidget(self.btn_scan)
        root.addLayout(head)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        for text, slot, role, tip in [
            ("✂ Putus", self.act_cut, "danger", "Putus internet"),
            ("✓ Pulih", self.act_restore, None, "Pulihkan"),
            ("\U0001F441 Kelola", self.act_manage, None,
             "Awasi (MITM) — syarat throttle & blokir situs"),
            ("\U0001F422 Batasi", self.act_throttle, None, "Batasi kecepatan"),
            ("\U0001F6AB Blokir", self.act_block, None,
             "Blokir situs untuk perangkat ini"),
            ("✎ Nama", self.act_rename, None, "Beri nama / alias"),
            ("⏰ Jadwal", self.act_schedule, None, "Jadwalkan aksi"),
        ]:
            b = QPushButton(text)
            if role:
                b.setObjectName(role)
            b.setToolTip(tip)
            b.setStyleSheet("padding:7px 10px; font-size:12px;")
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 6, 8, 8)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.doubleClicked.connect(lambda _: self.act_rename())
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(C_VEN, QHeaderView.Stretch)
        hh.setSectionResizeMode(C_NAME, QHeaderView.Stretch)
        self.table.setColumnWidth(C_TYPE, 140)
        self.table.setColumnWidth(C_IP, 120)
        self.table.setColumnWidth(C_MAC, 140)
        self.table.setColumnWidth(C_STAT, 110)
        self.table.setColumnWidth(C_DOWN, 90)
        self.table.setColumnWidth(C_UP, 90)
        cl.addWidget(self.table)
        root.addWidget(card, 1)

    # ---- scan -----------------------------------------------------------
    def start_scan(self):
        if not self.st.net.ok:
            if not self.st.refresh_network():
                QMessageBox.warning(self, "Jaringan",
                    self.st.net.error or "Jaringan tidak terbaca. Jalankan "
                    "sebagai Administrator & pastikan Npcap terpasang.")
                return
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("⏳  Memindai…")
        self._worker = ScanWorker(self.st.net)
        self._worker.device.connect(self._add_device)
        self._worker.done.connect(self._scan_done)
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _scan_done(self, n):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("⟳ Scan")
        self.count.setText("%d perangkat" % len(self.st.devices))
        if self.on_devices_changed:
            self.on_devices_changed()

    def _scan_error(self, msg):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("⟳ Scan")
        QMessageBox.critical(self, "Scan gagal", msg)

    def _add_device(self, dev):
        mac = dev["mac"]
        dev["name"] = self.st.db.name_of(mac)
        is_new = self.st.db.seen(mac)
        self.st.devices[mac] = dev
        if mac not in self.rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.rows[mac] = r
            for c in range(len(COLS)):
                self.table.setItem(r, c, QTableWidgetItem(""))
            self.table.item(r, C_MAC).setData(Qt.UserRole, mac)
        self._fill(self.rows[mac], dev, is_new)
        self.count.setText("%d perangkat" % len(self.st.devices))

    def _fill(self, r, dev, is_new=False):
        ip = dev["ip"]
        tag = ("  (You)" if ip == self.st.net.local_ip else
               "  (Gateway)" if ip == self.st.net.gateway_ip else "")
        self._set(r, C_TYPE, "%s  %s" % (dev.get("emoji", ""), dev.get("type", "")))
        self._set(r, C_IP, ip + tag)
        self._set(r, C_MAC, dev["mac"].upper())
        self._set(r, C_VEN, dev.get("vendor", ""))
        nm = dev.get("name", "") or ("\U0001F195 baru" if is_new else "")
        self._set(r, C_NAME, nm)
        self._status(r, dev)

    def _set(self, r, c, text):
        it = self.table.item(r, c)
        if it is None:
            it = QTableWidgetItem("")
            self.table.setItem(r, c, it)
        it.setText(str(text))

    def _status(self, r, dev):
        label, color = self.st.status_of(dev)
        it = self.table.item(r, C_STAT)
        it.setText(label)
        it.setForeground(QColor(color))

    # ---- selection ------------------------------------------------------
    def _selected(self):
        out = []
        for ri in {i.row() for i in self.table.selectedIndexes()}:
            it = self.table.item(ri, C_MAC)
            if it:
                dev = self.st.devices.get(it.data(Qt.UserRole))
                if dev:
                    out.append(dev)
        return out

    def refresh_status(self):
        for mac, r in self.rows.items():
            dev = self.st.devices.get(mac)
            if dev:
                self._status(r, dev)

    def refresh_rates(self, rates):
        for mac, r in self.rows.items():
            dev = self.st.devices.get(mac)
            if not dev:
                continue
            up, down = rates.get(dev["ip"], (None, None))
            self._set(r, C_DOWN, human_rate(down) if down is not None else "—")
            self._set(r, C_UP, human_rate(up) if up is not None else "—")

    # ---- actions --------------------------------------------------------
    def act_cut(self):
        for d in self._selected():
            self.st.cut(d)
        self.refresh_status()

    def act_restore(self):
        for d in self._selected():
            self.st.restore(d)
        self.refresh_status()

    def act_manage(self):
        for d in self._selected():
            self.st.manage(d)
        self.refresh_status()

    def act_throttle(self):
        devs = [d for d in self._selected() if not self.st.is_protected(d)]
        if not devs:
            return
        kbps, ok = QInputDialog.getInt(
            self, "Batasi Kecepatan",
            "Batas (kbps, 0 = tanpa batas):", 1024, 0, 1000000, 128)
        if not ok:
            return
        for d in devs:
            self.st.set_throttle(d, kbps)
        self.refresh_status()
        if kbps > 0:
            QMessageBox.information(self, "Throttle",
                "Batas kecepatan aktif. Butuh IP forwarding (Setelan → "
                "Aktifkan). Bila belum terasa, reboot 1x lalu coba lagi.")

    def act_block(self):
        devs = [d for d in self._selected() if not self.st.is_protected(d)]
        if not devs:
            return
        domain, ok = QInputDialog.getText(
            self, "Blokir Situs untuk Perangkat",
            "Domain yang diblokir (mis. tiktok.com):")
        if not ok or not domain.strip():
            return
        for d in devs:
            self.st.firewall.add_for_device(d["mac"], domain)
            self.st.manage(d)   # must be managed to enforce
        self.refresh_status()
        QMessageBox.information(self, "Blokir Situs",
            "'%s' diblokir untuk %d perangkat. Butuh IP forwarding aktif."
            % (domain.strip(), len(devs)))

    def act_rename(self):
        devs = self._selected()
        if not devs:
            return
        d = devs[0]
        name, ok = QInputDialog.getText(
            self, "Beri Nama", "Nama untuk %s:" % d["ip"],
            text=d.get("name", ""))
        if ok:
            self.st.db.set_name(d["mac"], name)
            d["name"] = name
            self._fill(self.rows[d["mac"]], d)

    def act_schedule(self):
        devs = self._selected()
        if not devs:
            QMessageBox.information(self, "Jadwal", "Pilih perangkat dulu.")
            return
        d = devs[0]
        dlg = ScheduleDialog(self, d.get("name") or d["ip"])
        if dlg.exec() == QDialog.Accepted:
            action, days, start, end = dlg.result()
            if not days:
                QMessageBox.warning(self, "Jadwal", "Pilih minimal satu hari.")
                return
            self.st.scheduler.add_rule(d["mac"], d["ip"],
                                       d.get("name") or d["ip"],
                                       action, days, start, end)
            QMessageBox.information(self, "Jadwal",
                "Jadwal ditambahkan. Kelola di Setelan → Jadwal.")

    def act_cut_all(self):
        if QMessageBox.question(self, "Putus Semua",
            "Putus internet SEMUA perangkat (kecuali PC & gateway)?") \
                != QMessageBox.Yes:
            return
        for d in self.st.devices.values():
            self.st.cut(d)
        self.refresh_status()

    def act_restore_all(self):
        self.st.spoofer.clear()
        for ip in list(self.st.engine.managed_ips()):
            self.st.engine.unmanage(ip)
        self.refresh_status()

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("✂  Putus", self.act_cut)
        m.addAction("✓  Pulihkan", self.act_restore)
        m.addAction("\U0001F441  Kelola", self.act_manage)
        m.addAction("\U0001F422  Batasi Kecepatan", self.act_throttle)
        m.addAction("\U0001F6AB  Blokir Situs", self.act_block)
        m.addSeparator()
        m.addAction("✎  Beri Nama", self.act_rename)
        m.addAction("⏰  Jadwalkan", self.act_schedule)
        m.exec(self.table.viewport().mapToGlobal(pos))


# =====================================================================
# Blokir Situs (Sites)
# =====================================================================
class SitesPage(QWidget):
    def __init__(self, st):
        super().__init__()
        self.st = st
        self.setObjectName("page")
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)
        root.addWidget(_h1("Blokir Situs"))
        root.addWidget(_dim("Berlaku untuk perangkat yang sedang 'Dikelola'. "
                            "Butuh IP forwarding aktif (Setelan)."))

        # categories
        cat_card = Card()
        cv = QVBoxLayout(cat_card)
        cv.setContentsMargins(18, 16, 18, 10)
        cv.addWidget(_h2("Kategori Cepat"))
        self._cat_switches = {}
        for name, domains in CATEGORIES.items():
            row = QHBoxLayout()
            lbl = QLabel("%s" % name)
            sub = _dim("  %d domain" % len(domains))
            sw = ToggleSwitch(name in self.st.firewall.enabled_categories)
            sw.toggled.connect(lambda on, n=name: self._toggle_cat(n, on))
            self._cat_switches[name] = sw
            row.addWidget(lbl)
            row.addWidget(sub)
            row.addStretch(1)
            row.addWidget(sw)
            cv.addLayout(row)
        root.addWidget(cat_card)

        # global custom domains
        g_card = Card()
        gv = QVBoxLayout(g_card)
        gv.setContentsMargins(18, 16, 18, 16)
        gv.addWidget(_h2("Domain Kustom (global)"))
        add = QHBoxLayout()
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("mis. facebook.com")
        self.inp.returnPressed.connect(self._add)
        b = QPushButton("Tambah"); b.setObjectName("primary")
        b.clicked.connect(self._add)
        add.addWidget(self.inp)
        add.addWidget(b)
        gv.addLayout(add)
        self.lst = QListWidget()
        self.lst.setMaximumHeight(220)
        gv.addWidget(self.lst)
        rm = QPushButton("Hapus yang dipilih"); rm.setObjectName("ghost")
        rm.clicked.connect(self._remove)
        gv.addWidget(rm, alignment=Qt.AlignLeft)
        root.addWidget(g_card)
        root.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(body))
        self.refresh()

    def _toggle_cat(self, name, on):
        self.st.firewall.toggle_category(name, on)

    def _add(self):
        d = self.inp.text().strip()
        if d:
            self.st.firewall.add_global(d)
            self.inp.clear()
            self.refresh()

    def _remove(self):
        for it in self.lst.selectedItems():
            self.st.firewall.remove_global(it.text())
        self.refresh()

    def refresh(self):
        self.lst.clear()
        for d in sorted(self.st.firewall.global_block):
            self.lst.addItem(QListWidgetItem(d))
        for name, sw in self._cat_switches.items():
            sw.setChecked(name in self.st.firewall.enabled_categories)


# =====================================================================
# Proteksi
# =====================================================================
class ProtectionPage(QWidget):
    def __init__(self, st):
        super().__init__()
        self.st = st
        self.setObjectName("page")
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)
        root.addWidget(_h1("Proteksi ARP"))
        root.addWidget(_dim("Deteksi & tangkis serangan ARP spoofing yang "
                            "ditujukan ke PC-mu (anti-NetCut)."))

        card = Card()
        cv = QVBoxLayout(card)
        cv.setContentsMargins(20, 18, 20, 18)
        row = QHBoxLayout()
        self.stat = QLabel("Proteksi nonaktif")
        self.stat.setObjectName("h2")
        self.sw = ToggleSwitch(False)
        self.sw.toggled.connect(self._toggle)
        row.addWidget(self.stat)
        row.addStretch(1)
        row.addWidget(QLabel("OFF  "))
        row.addWidget(self.sw)
        cv.addLayout(row)
        self.info = _dim("")
        cv.addWidget(self.info)
        root.addWidget(card)

        log_card = Card()
        lv = QVBoxLayout(log_card)
        lv.setContentsMargins(20, 16, 20, 16)
        lv.addWidget(_h2("Log Serangan"))
        self.attacks = QPlainTextEdit()
        self.attacks.setReadOnly(True)
        lv.addWidget(self.attacks)
        root.addWidget(log_card, 1)

    def showEvent(self, e):
        super().showEvent(e)
        g = self.st.net
        self.info.setText("Gateway: %s  (%s)" % (g.gateway_ip, g.gateway_mac))

    def _toggle(self, on):
        if on:
            self.st.protector.start()
            self.stat.setText("Proteksi AKTIF — memantau gateway")
            self.stat.setStyleSheet("color:%s;" % ACCENT)
        else:
            self.st.protector.stop()
            self.stat.setText("Proteksi nonaktif")
            self.stat.setStyleSheet("color:%s;" % TEXT)

    def on_attack(self, mac, ip):
        self.stat.setText("⚠ SERANGAN TERDETEKSI!")
        self.stat.setStyleSheet("color:%s;" % DANGER)
        self.attacks.appendPlainText(
            "Penyerang MAC=%s meniru gateway %s" % (mac, ip))


# =====================================================================
# Setelan
# =====================================================================
class SettingsPage(QWidget):
    def __init__(self, st):
        super().__init__()
        self.st = st
        self.setObjectName("page")
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)
        root.addWidget(_h1("Setelan"))

        # advanced
        adv = Card()
        av = QVBoxLayout(adv)
        av.setContentsMargins(20, 16, 20, 16)
        av.addWidget(_h2("Fitur Lanjutan (Blokir Situs & Batasi Kecepatan)"))
        av.addWidget(_dim("Fitur ini butuh laptop jadi perantara (MITM) + IP "
                          "forwarding Windows. Klik untuk mengaktifkan "
                          "(mungkin perlu 1x restart PC)."))
        b = QPushButton("Aktifkan IP Forwarding"); b.setObjectName("primary")
        b.clicked.connect(self._enable_fwd)
        self.fwd_stat = _dim("Status: belum diaktifkan")
        av.addWidget(b, alignment=Qt.AlignLeft)
        av.addWidget(self.fwd_stat)
        root.addWidget(adv)

        # schedules
        sc = Card()
        sv = QVBoxLayout(sc)
        sv.setContentsMargins(20, 16, 20, 16)
        sv.addWidget(_h2("Jadwal (Parental Control)"))
        self.sched_box = QVBoxLayout()
        sv.addLayout(self.sched_box)
        self.sched_empty = _dim("Belum ada jadwal. Tambah dari Perangkat → Jadwal.")
        sv.addWidget(self.sched_empty)
        root.addWidget(sc)

        # about
        ab = Card()
        bv = QVBoxLayout(ab)
        bv.setContentsMargins(20, 16, 20, 16)
        bv.addWidget(_h2("Tentang"))
        bv.addWidget(_dim("%s v%s  —  network control suite"
                          % (config.APP_NAME, config.APP_VERSION)))
        btns = QHBoxLayout()
        bd = QPushButton("Buka Folder Data"); bd.setObjectName("ghost")
        bd.clicked.connect(lambda: self._open(config.data_dir()))
        bl = QPushButton("Buka Log"); bl.setObjectName("ghost")
        bl.clicked.connect(lambda: self._open(config.log_path()))
        btns.addWidget(bd); btns.addWidget(bl); btns.addStretch(1)
        bv.addLayout(btns)
        root.addWidget(ab)
        root.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(body))

    def _enable_fwd(self):
        self.st.engine.enable_forwarding()
        self.fwd_stat.setText("Status: diaktifkan (bila fitur belum bekerja, "
                              "restart PC sekali).")

    def _open(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            QMessageBox.warning(self, "Gagal", str(e))

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh_schedules()

    def refresh_schedules(self):
        while self.sched_box.count():
            item = self.sched_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        rules = self.st.scheduler.all_rules()
        self.sched_empty.setVisible(not rules)
        for rule in rules:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            act = "Putus" if rule["action"] == "cut" else "Blokir situs"
            days = ",".join(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"][d]
                            for d in rule["days"])
            txt = QLabel("%s  —  %s  %s–%s  (%s)"
                         % (rule["name"], act, rule["start"], rule["end"], days))
            rm = QPushButton("Hapus"); rm.setObjectName("ghost")
            rm.clicked.connect(lambda _, rid=rule["id"]: self._del(rid))
            rl.addWidget(txt)
            rl.addStretch(1)
            rl.addWidget(rm)
            self.sched_box.addWidget(row)

    def _del(self, rid):
        self.st.scheduler.remove_rule(rid)
        self.refresh_schedules()


# =====================================================================
# Schedule dialog
# =====================================================================
class ScheduleDialog(QDialog):
    def __init__(self, parent, device_name):
        super().__init__(parent)
        self.setWindowTitle("Jadwalkan — %s" % device_name)
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        lay.addWidget(QLabel("Aksi:"))
        self.action = QComboBox()
        self.action.addItem("Putus internet", "cut")
        self.action.addItem("Blokir situs (sesuai daftar)", "block")
        lay.addWidget(self.action)

        lay.addWidget(QLabel("Hari:"))
        days_row = QHBoxLayout()
        self.day_boxes = []
        for i, d in enumerate(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]):
            cb = QCheckBox(d)
            cb.setChecked(i < 5)
            self.day_boxes.append(cb)
            days_row.addWidget(cb)
        lay.addLayout(days_row)

        times = QHBoxLayout()
        times.addWidget(QLabel("Dari:"))
        self.start = QTimeEdit(QTime(21, 0))
        self.start.setDisplayFormat("HH:mm")
        times.addWidget(self.start)
        times.addSpacing(16)
        times.addWidget(QLabel("Sampai:"))
        self.end = QTimeEdit(QTime(6, 0))
        self.end.setDisplayFormat("HH:mm")
        times.addWidget(self.end)
        times.addStretch(1)
        lay.addLayout(times)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def result(self):
        action = self.action.currentData()
        days = [i for i, cb in enumerate(self.day_boxes) if cb.isChecked()]
        start = self.start.time().toString("HH:mm")
        end = self.end.time().toString("HH:mm")
        return action, days, start, end
