# -*- coding: utf-8 -*-
"""Палитра и таблица стилей (UI_KIT.md, разделы 1, 2, 5, 6, 9, 10).

Акцент — одна пара цветов на всю программу: выбранный цвет и он же со
сдвигом тона на 85 градусов. Остальная палитра неизменна, иначе смысл
цвета плывёт.
"""

import os
import tempfile
from string import Template

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QPainter, QPixmap, QPolygonF

# ---------------- неизменная часть палитры ----------------
BG = "#0b0c10"
PANEL_TOP = "rgba(38, 42, 54, 190)"
PANEL_BOT = "rgba(20, 22, 30, 200)"
CARD = "rgba(255, 255, 255, 12)"
FIELD = "rgba(10, 12, 17, 220)"
RAISE = "rgba(255, 255, 255, 16)"
RAISE_HI = "rgba(255, 255, 255, 28)"
LINE = "rgba(255, 255, 255, 30)"
CONSOLE_BG = "#080a0e"

TEXT = "#e9edf4"
TEXT_SOFT = "#ccd6e6"
LABEL = "#aebfd8"
TEXT_DIM = "#97a3b8"

# смысловые цвета: ими говорит программа, акцентом — управляет человек
OK = "#34d399"
WARN = "#fbbf24"
ERR = "#fb7185"
SENT = "#7dd3fc"
DANGER = "#be123c"
DANGER_HI = "#e11d48"

# готовые акценты (меню «Вид — Цвет элементов»)
ACCENTS = [
    ("Циан", "#22d3ee"),
    ("Небесный", "#38bdf8"),
    ("Индиго", "#6366f1"),
    ("Фиолетовый", "#a855f7"),
    ("Розовый", "#ec4899"),
    ("Малиновый", "#f43f5e"),
    ("Янтарь", "#f59e0b"),
    ("Лайм", "#84cc16"),
    ("Изумруд", "#10b981"),
    ("Сталь", "#94a3b8"),
]
DEFAULT_ACCENT = "#22d3ee"

MONO = "Consolas"
SANS = "Segoe UI"


def hue_shift(color, deg):
    """Тот же цвет, сдвинутый по кругу тонов."""
    c = QColor(color)
    h, s, v, a = c.getHsv()
    if h < 0:          # серый: тона нет, сдвигать нечего
        return QColor(c)
    return QColor.fromHsv((h + deg) % 360, s, v, a)


def rgba(color, alpha):
    c = QColor(color)
    return "rgba(%d, %d, %d, %.2f)" % (c.red(), c.green(), c.blue(), alpha)


def arrow_image(color):
    """Треугольник выпадающего списка. QSS рисовать его не умеет:
    приём с border-left/right в Qt даёт квадрат, а не стрелку."""
    name = QColor(color).name()[1:]
    path = os.path.join(tempfile.gettempdir(), "uartmon_arrow_%s.png" % name)
    if not os.path.exists(path):
        pm = QPixmap(20, 20)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygonF([QPointF(5, 8), QPointF(15, 8),
                                 QPointF(10, 14)]))
        p.end()
        pm.save(path)
    return path.replace("\\", "/")


class Theme:
    """Акцентная пара. 85 градусов — опытное значение: меньше 60 разница
    не читается, больше 120 пара распадается на два несвязанных цвета."""

    def __init__(self, accent=DEFAULT_ACCENT):
        self.set_accent(accent)

    def set_accent(self, accent):
        self.accent = QColor(accent).name()
        self.g1 = QColor(self.accent)
        self.g2 = hue_shift(self.accent, 85)

    @property
    def n1(self):
        return self.g1.name()

    @property
    def n2(self):
        return self.g2.name()


_QSS = Template("""
QMainWindow, QDialog { background: $BG; }
QWidget { background: transparent; color: $TEXT;
          font-family: '$SANS', Arial; font-size: 13px; }

/* ---- подписи: роль, а не отдельный стиль в каждом месте ---- */
QLabel { background: transparent; color: $TEXT; }
QLabel[role="dim"]   { color: $DIM; font-size: 11px; }
QLabel[role="label"] { color: $LABEL; font-size: 12px; font-weight: 600; }
QLabel[role="soft"]  { color: $SOFT; }
QLabel[role="title"] { color: $TEXT; font-size: 14px; font-weight: 600; }
QLabel[role="num"]   { color: $ACC; font-family: '$MONO';
                       font-size: 13px; font-weight: 700; }

/* ---- кнопки: роль по частоте и обратимости действия ---- */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $ACC1, stop:1 $ACC2);
    color: #06121a; border: none; border-radius: 11px;
    padding: 7px 16px; font-size: 12px; font-weight: 600;
}
QPushButton:hover   { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $ACC1H, stop:1 $ACC2H); }
QPushButton:pressed { background: $ACC_DK; color: $TEXT; }
QPushButton:disabled { background: $RAISE; color: $DIM; }

QPushButton[role="ghost"] {
    background: $RAISE; color: $SOFT; border: 1px solid $LINE;
}
QPushButton[role="ghost"]:hover    { background: $RAISE_HI; color: $TEXT;
                                     border: 1px solid $ACC_42; }
QPushButton[role="ghost"]:pressed  { background: $ACC_18; }
QPushButton[role="ghost"]:disabled { background: $RAISE; color: $DIM;
                                     border: 1px solid $LINE; }
QPushButton[role="danger"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $ERR, stop:1 $DANGER);
    color: #fff1f2;
}
QPushButton[role="danger"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #fda4af, stop:1 $DANGER_HI);
}
QPushButton[role="danger"]:pressed { background: $DANGER; }
/* состояние у роли надо прописывать отдельно: правило с [role] бьёт
   общее QPushButton:disabled, и выключенная кнопка оставалась красной */
QPushButton[role="danger"]:disabled { background: $RAISE; color: $DIM; }
QPushButton[role="small"], QPushButton[compact="true"] {
    padding: 6px 11px; font-size: 11px;
}

/* ---- поля ввода ---- */
QLineEdit, QComboBox, QSpinBox {
    background: $FIELD; color: $TEXT;
    border: 1px solid $ACC_42; border-radius: 11px; padding: 7px 10px;
    selection-background-color: $ACC_42; selection-color: $TEXT;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid $ACC; background: $ACC_10;
}
QLineEdit:disabled, QComboBox:disabled { color: $DIM; border: 1px solid $LINE; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: url($ARROW); width: 20px; height: 20px; margin-right: 4px;
}
QComboBox QAbstractItemView {
    background: #171a22; color: $TEXT;
    border: 1px solid $ACC_35; border-radius: 12px; padding: 4px;
    outline: none;
    selection-background-color: $ACC_18; selection-color: $TEXT;
}

/* ---- консоль ---- */
QTextEdit, QPlainTextEdit {
    background: $CONSOLE; color: $SOFT;
    border: 1px solid $LINE; border-radius: 12px; padding: 6px;
    font-family: '$MONO'; font-size: 12px;
    selection-background-color: $ACC_42; selection-color: $TEXT;
}

/* ---- флажки (там, где не тумблер) ---- */
QCheckBox { color: $SOFT; spacing: 7px; background: transparent;
            font-size: 12px; }
QCheckBox::indicator {
    width: 15px; height: 15px; border-radius: 5px;
    background: $FIELD; border: 1px solid $LINE;
}
QCheckBox::indicator:checked { background: $ACC; border: 1px solid $ACC; }

/* ---- вкладки ---- */
QTabWidget::pane {
    border: 1px solid $ACC_35; border-radius: 14px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 rgba(38, 42, 54, 190),
                                stop:1 rgba(20, 22, 30, 200));
    top: -1px;
}
QTabBar { background: transparent; }
QTabBar::tab {
    background: $RAISE; color: $SOFT;
    border: 1px solid $LINE; border-bottom: none;
    border-top-left-radius: 12px; border-top-right-radius: 12px;
    padding: 8px 18px; margin-right: 3px;
    font-size: 12px; font-weight: 600;
}
QTabBar::tab:hover { background: $RAISE_HI; color: $TEXT; }
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $ACC1, stop:1 $ACC2);
    color: #06121a; border: 1px solid $ACC_42; border-bottom: none;
}

/* ---- группа: та же стеклянная карточка, заголовок капсулой ---- */
QGroupBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 rgba(255, 255, 255, 10),
                                stop:1 rgba(255, 255, 255, 4));
    border: 1px solid $ACC_35; border-radius: 14px;
    margin-top: 13px; padding: 16px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 14px; padding: 3px 10px;
    background: #1b1e27; border: 1px solid $ACC_35; border-radius: 11px;
    color: $SOFT; font-size: 11px; font-weight: 700;
}

/* ---- ход работы ---- */
QProgressBar {
    background: $FIELD; border: 1px solid $LINE; border-radius: 9px;
    height: 16px; text-align: center; color: $SOFT;
    font-size: 11px; font-weight: 600;
}
QProgressBar::chunk {
    border-radius: 8px; margin: 1px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $ACC1, stop:1 $ACC2);
}

/* ---- разделитель панелей ---- */
QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 10px; }
QSplitter::handle:vertical { height: 10px; }
QSplitter::handle:hover { background: $ACC_18; }

/* ---- справка и прочие области прокрутки ---- */
QTextBrowser {
    background: rgba(10, 12, 17, 200); color: $SOFT;
    border: 1px solid $LINE; border-radius: 12px; padding: 10px;
    font-family: '$SANS', Arial; font-size: 13px;
}
QScrollArea { background: transparent; border: none; }
QMessageBox, QProgressDialog, QFileDialog { background: $BG; }
QMessageBox QLabel, QProgressDialog QLabel { color: $TEXT; }

/* ---- таблицы ---- */
QTableWidget {
    background: $CONSOLE; color: $SOFT; gridline-color: $LINE;
    border: 1px solid $LINE; border-radius: 12px;
    selection-background-color: $ACC_18; selection-color: $TEXT;
}
QHeaderView::section {
    background: $RAISE; color: $ACC; border: none;
    padding: 5px; font-size: 11px; font-weight: 700;
}
QTableWidget::item { padding: 3px; }

/* ---- полосы прокрутки ---- */
QScrollBar:vertical   { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: $ACC_42; border-radius: 5px; min-height: 30px;
}
QScrollBar::handle:horizontal {
    background: $ACC_42; border-radius: 5px; min-width: 30px;
}
QScrollBar::handle:hover { background: $ACC; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---- меню ---- */
QMenuBar { background: rgba(12, 14, 19, 180); color: $SOFT;
           border-bottom: 1px solid $LINE; }
QMenuBar::item { padding: 5px 12px; border-radius: 8px; background: transparent; }
QMenuBar::item:selected { background: $RAISE; color: $TEXT; }
QMenu { background: #171a22; color: $SOFT;
        border: 1px solid $ACC_35; border-radius: 12px; padding: 5px; }
QMenu::item { padding: 6px 26px; border-radius: 8px; }
QMenu::item:selected { background: $ACC_18; color: $TEXT; }
QMenu::separator { height: 1px; background: $LINE; margin: 5px 10px; }

/* ---- строка состояния, док, подсказка ---- */
QStatusBar { background: rgba(12, 14, 19, 180); color: $DIM;
             border-top: 1px solid $LINE; font-size: 11px; }
QStatusBar::item { border: none; }
QDockWidget { color: $SOFT; font-size: 12px; font-weight: 600; }
QDockWidget::title { background: rgba(12, 14, 19, 180); padding: 6px 10px; }
QToolTip {
    background: #171a22; color: $SOFT;
    border: 1px solid $ACC_35; border-radius: 10px; padding: 6px 8px;
    font-size: 12px;
}
""")


def build_qss(theme):
    acc = theme.n1
    return _QSS.substitute(
        BG=BG, TEXT=TEXT, SOFT=TEXT_SOFT, LABEL=LABEL, DIM=TEXT_DIM,
        FIELD=FIELD, RAISE=RAISE, RAISE_HI=RAISE_HI, LINE=LINE,
        CONSOLE=CONSOLE_BG, ERR=ERR, DANGER=DANGER,
        DANGER_HI=DANGER_HI,
        SANS=SANS, MONO=MONO,
        ACC=acc, ACC1=acc, ACC2=theme.n2,
        ACC1H=theme.g1.lighter(115).name(), ACC2H=theme.g2.lighter(115).name(),
        ACC_DK=theme.g1.darker(140).name(),
        ACC_10=rgba(acc, 0.10), ACC_18=rgba(acc, 0.18),
        ACC_35=rgba(acc, 0.35), ACC_42=rgba(acc, 0.42),
        ARROW=arrow_image(acc),
    )
