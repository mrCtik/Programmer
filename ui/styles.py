# ui/styles.py
# Оформление по UI_KIT.md. Сама палитра и таблица стилей — в ui/kit,
# этот модуль только держит выбранный акцент и раздаёт его программе.

import json
import os
import sys

from PyQt5.QtWidgets import QApplication

from ui.kit import theme as T
from ui.kit.appicon import app_icon

# Акцент программатора — индиго; у uart_monitor циан, так программы
# различимы на панели задач, оставаясь одного вида.
DEFAULT_ACCENT = "#6366f1"

THEME = T.Theme(DEFAULT_ACCENT)


def config_dir():
    """Рядом с exe, а не во временной папке распаковки PyInstaller."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _accent_file():
    return os.path.join(config_dir(), "ui.json")


def load_accent():
    try:
        with open(_accent_file(), encoding="utf-8") as f:
            return json.load(f).get("accent", DEFAULT_ACCENT)
    except (OSError, ValueError):
        return DEFAULT_ACCENT


def save_accent(color):
    try:
        with open(_accent_file(), "w", encoding="utf-8") as f:
            json.dump({"accent": color}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def apply_dark_theme(accent=None):
    """Одна таблица стилей на всю программу. Своих setStyleSheet у
    контейнеров быть не должно: они перебивают эту для всего поддерева."""
    app = QApplication.instance()
    if not app:
        return
    if accent:
        THEME.set_accent(accent)
    app.setStyleSheet(T.build_qss(THEME))
    app.setWindowIcon(app_icon(THEME))


def role(widget, name, compact=False):
    """Роль кнопки или подписи: ghost / danger / small / dim / label…"""
    widget.setProperty("role", name)
    if compact:
        widget.setProperty("compact", "true")
    return widget


def group(title, *rows):
    """Стеклянная карточка с заголовком-капсулой: QGroupBox, который
    таблица стилей кита рисует панелью. Внутрь кладутся готовые строки."""
    from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QLayout, QWidget

    box = QGroupBox(title)
    vbox = QVBoxLayout(box)
    vbox.setSpacing(8)
    for row in rows:
        if isinstance(row, QLayout):
            vbox.addLayout(row)
        elif isinstance(row, QWidget):
            vbox.addWidget(row)
    return box
