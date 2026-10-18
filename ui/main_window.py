"""NetHawk v2 shell: sidebar navigation + stacked pages + realtime timers."""
import threading

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QStackedWidget, QButtonGroup, QGraphicsOpacityEffect)

from core import config, vendor
from .theme import qss
from .appstate import AppState
from .pages import (DashboardPage, DevicesPage, SitesPage, ProtectionPage,
                    SettingsPage)

NAV = [
    ("\U0001F4CA", "Dashboard"),
    ("\U0001F5A5", "Perangkat"),
    ("\U0001F6AB", "Blokir Situs"),
    ("\U0001F6E1", "Proteksi"),
    ("⚙", "Setelan"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("%s v%s — Network Control Suite"
                            % (config.APP_NAME, config.APP_VERSION))
        self.setMinimumSize(1020, 620)
        self.resize(1200, 710)

        self.st = AppState()
        self._build()
        self.setStyleSheet(qss())

        self.st.sig_log.connect(self.dash.append_log)
        self.st.sig_attack.connect(self.prot.on_attack)

        threading.Thread(target=vendor.ensure_db, daemon=True).start()
        self.st.scheduler.start()
        QTimer.singleShot(60, self._init_net)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ---- construction ---------------------------------------------------
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(212)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(16, 20, 16, 16)
        sv.setSpacing(5)

        logo = QHBoxLayout()
        name = QLabel("NetHawk")
        name.setObjectName("logo")
        dot = QLabel("●")
        dot.setObjectName("logoDot")
        logo.addWidget(name)
        logo.addWidget(dot)
        logo.addStretch(1)
        sv.addLayout(logo)
        sv.addSpacing(18)

        self.pages = QStackedWidget()
        self.dash = DashboardPage(self.st)
        self.devices = DevicesPage(self.st, on_devices_changed=self._devices_changed)
        self.sites = SitesPage(self.st)
        self.prot = ProtectionPage(self.st)
        self.settings = SettingsPage(self.st)
        page_objs = [self.dash, self.devices, self.sites, self.prot, self.settings]

        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        for i, (icon, label) in enumerate(NAV):
            b = QPushButton("  %s    %s" % (icon, label))
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self._go(idx))
            self.nav.addButton(b, i)
            sv.addWidget(b)
            self.pages.addWidget(page_objs[i])
        self.nav.button(0).setChecked(True)

        sv.addStretch(1)
        self.side_meta = QLabel("—")
        self.side_meta.setObjectName("sideMeta")
        self.side_meta.setWordWrap(True)
        sv.addWidget(self.side_meta)

        lay.addWidget(side)
        lay.addWidget(self.pages, 1)

    # ---- navigation with fade ------------------------------------------
    def _go(self, idx):
        self.pages.setCurrentIndex(idx)
        w = self.pages.currentWidget()
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(170)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))
        anim.start()
        self._page_anim = anim
        if idx == 2:
            self.sites.refresh()
        elif idx == 4:
            self.settings.refresh_schedules()

    # ---- lifecycle ------------------------------------------------------
    def _init_net(self):
        ok = self.st.refresh_network()
        if ok:
            self.side_meta.setText("%s\nIP %s\nGW %s"
                                   % (self.st.net.iface_name,
                                      self.st.net.local_ip,
                                      self.st.net.gateway_ip))
        else:
            self.side_meta.setText(self.st.net.error or "Jaringan tidak terbaca")
        self.dash.refresh(0, 0)

    def _devices_changed(self):
        self.dash.refresh(0, 0)

    def _tick(self):
        up, down = self.st.throughput.sample()
        rates = self.st.engine.rates()
        self.dash.tick(up, down, rates)
        self.dash.refresh(up, down)
        self.dash.set_talkers(rates)
        self.devices.refresh_rates(rates)
        self.devices.refresh_status()

    def closeEvent(self, e):
        try:
            self.st.shutdown()
        except Exception:
            pass
        e.accept()
