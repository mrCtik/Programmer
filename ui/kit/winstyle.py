# -*- coding: utf-8 -*-
"""Тёмная рамка окна и значок на панели задач (UI_KIT.md, раздел 11)."""

import ctypes
from ctypes import byref, c_int

from PyQt5.QtCore import QObject, QEvent
from PyQt5.QtWidgets import QWidget


def _dark_frame(widget):
    """Атрибут 20 — нынешний DWMWA_USE_IMMERSIVE_DARK_MODE, 19 — его
    номер в сборках Windows 10 до 20H1; пробуются оба."""
    try:
        hwnd = int(widget.winId())
    except Exception:
        return
    for attr in (20, 19):
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, byref(c_int(1)), 4)
        except Exception:
            pass


class _FrameFilter(QObject):
    """Задним числом система перерисовывает заголовок не всегда, поэтому
    рамка ставится на событии показа — и диалогам тоже."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and isinstance(obj, QWidget) \
                and obj.isWindow():
            _dark_frame(obj)
        return False


_filter = None


def dark_titlebars(app):
    global _filter
    _filter = _FrameFilter(app)
    app.installEventFilter(_filter)
    return _filter


def taskbar_identity(app_id):
    """Без этого Windows считает окно частью python.exe и показывает на
    панели задач его значок. Вызывать до создания окон."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass
