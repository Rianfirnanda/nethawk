"""Command Center dark theme for NetHawk v2."""

# Palette
BG       = "#0a0e14"
BG2      = "#0c1119"
SIDEBAR  = "#0b1017"
SURFACE  = "#121a24"
SURFACE2 = "#18222e"
CARD     = "#121a24"
BORDER   = "#1f2b38"
BORDER2  = "#283749"
TEXT     = "#e8eef5"
DIM      = "#7f8ea0"
MUTED    = "#53616f"
ACCENT   = "#1fe0a4"   # mint/teal
ACCENT2  = "#17b6e6"   # cyan (second series / gradients)
DANGER   = "#ff5d6c"
WARN     = "#ffb84d"
PURPLE   = "#9b8cff"


def qss() -> str:
    return f"""
    * {{
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 13px; color: {TEXT}; outline: none;
    }}
    QWidget#root, QMainWindow {{ background: {BG}; }}
    QWidget#page {{ background: {BG}; }}

    /* ---------- Sidebar ---------- */
    QWidget#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
    QLabel#logo {{ font-size: 19px; font-weight: 800; color: {TEXT}; }}
    QLabel#logoDot {{ color: {ACCENT}; font-size: 19px; font-weight: 800; }}
    QLabel#sideMeta {{ color: {MUTED}; font-size: 11px; }}

    QPushButton#nav {{
        text-align: left; padding: 11px 14px; border: none; border-radius: 10px;
        background: transparent; color: {DIM}; font-size: 13px; font-weight: 600;
    }}
    QPushButton#nav:hover {{ background: {SURFACE}; color: {TEXT}; }}
    QPushButton#nav:checked {{
        background: {SURFACE2}; color: {ACCENT};
        border-left: 3px solid {ACCENT}; padding-left: 11px;
    }}

    /* ---------- Headings ---------- */
    QLabel#h1 {{ font-size: 22px; font-weight: 800; color: {TEXT}; }}
    QLabel#h2 {{ font-size: 15px; font-weight: 700; color: {TEXT}; }}
    QLabel#dim {{ color: {DIM}; font-size: 12px; }}
    QLabel#muted {{ color: {MUTED}; font-size: 11px; }}

    /* ---------- Cards ---------- */
    QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; }}
    QFrame#cardAlt {{ background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 14px; }}
    QLabel#cardTitle {{ color: {DIM}; font-size: 11px; font-weight: 700;
                        letter-spacing: 1px; }}
    QLabel#statValue {{ font-size: 26px; font-weight: 800; }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        background: {SURFACE2}; border: 1px solid {BORDER2}; border-radius: 10px;
        padding: 9px 15px; color: {TEXT}; font-weight: 600;
    }}
    QPushButton:hover {{ background: #223044; }}
    QPushButton:pressed {{ background: #27374d; }}
    QPushButton:disabled {{ color: {MUTED}; background: {SURFACE}; }}
    QPushButton#primary {{ background: {ACCENT}; color: #04231a; border: none; }}
    QPushButton#primary:hover {{ background: #2bf2b4; }}
    QPushButton#danger  {{ background: {DANGER}; color: #2b0005; border: none; }}
    QPushButton#danger:hover {{ background: #ff7682; }}
    QPushButton#ghost {{ background: transparent; border: 1px solid {BORDER2}; }}
    QPushButton#ghost:hover {{ background: {SURFACE}; }}

    /* ---------- Table ---------- */
    QTableWidget {{
        background: transparent; border: none; gridline-color: transparent;
        selection-background-color: rgba(31,224,164,0.14); selection-color: {TEXT};
    }}
    QTableWidget::item {{ padding: 9px 8px; border-bottom: 1px solid {BORDER}; }}
    QHeaderView::section {{
        background: transparent; color: {MUTED}; padding: 8px;
        border: none; border-bottom: 1px solid {BORDER2};
        font-weight: 700; font-size: 11px; letter-spacing: .5px;
    }}
    QTableCornerButton::section {{ background: transparent; border: none; }}

    /* ---------- Inputs ---------- */
    QLineEdit, QSpinBox, QComboBox, QTimeEdit {{
        background: {BG2}; border: 1px solid {BORDER2}; border-radius: 9px;
        padding: 8px 11px; color: {TEXT}; selection-background-color: {ACCENT};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTimeEdit:focus {{
        border: 1px solid {ACCENT}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE2}; border: 1px solid {BORDER2};
        selection-background-color: rgba(31,224,164,0.18); outline: none; }}

    /* ---------- Log ---------- */
    QPlainTextEdit {{
        background: {BG2}; border: 1px solid {BORDER}; border-radius: 12px;
        color: #93b8ac; font-family: 'Consolas','Cascadia Mono',monospace;
        font-size: 12px; padding: 10px; }}

    /* ---------- Scroll / menu ---------- */
    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {BORDER2}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: #35495f; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollArea {{ border: none; background: transparent; }}
    QMenu {{ background: {SURFACE2}; border: 1px solid {BORDER2}; border-radius: 10px; padding: 4px; }}
    QMenu::item {{ padding: 8px 22px; border-radius: 6px; }}
    QMenu::item:selected {{ background: rgba(31,224,164,0.16); }}
    QToolTip {{ background: {SURFACE2}; color: {TEXT}; border: 1px solid {BORDER2};
                border-radius: 6px; padding: 5px 8px; }}
    QCheckBox {{ color: {TEXT}; spacing: 8px; }}
    """
