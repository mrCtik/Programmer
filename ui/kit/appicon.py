# -*- coding: utf-8 -*-
"""Иконка приложения, нарисованная кодом (UI_KIT.md, раздел 11).

Рисуется теми же акцентами, что и окно, и перерисовывается при смене
акцента. Для программатора рисунок — микросхема с молнией: прошивка.
"""

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (QIcon, QPixmap, QPainter, QColor, QPen, QPolygonF,
                         QLinearGradient, QBrush, QPainterPath)

# молния в условном квадрате 100x100 — масштабируется под любой размер
_BOLT = [(60, 6), (28, 54), (46, 54), (38, 94), (74, 44), (54, 44)]


def icon_pixmap(theme, size=256):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = size
    body = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)

    # плитка: тёмное стекло с акцентным кантом
    path = QPainterPath()
    path.addRoundedRect(body, s * 0.22, s * 0.22)
    g = QLinearGradient(body.topLeft(), body.bottomRight())
    g.setColorAt(0.0, QColor("#141821"))
    g.setColorAt(1.0, QColor("#0a0b0f"))
    p.fillPath(path, QBrush(g))

    eg = QLinearGradient(body.topLeft(), body.bottomRight())
    eg.setColorAt(0.0, QColor(theme.g1))
    eg.setColorAt(1.0, QColor(theme.g2))
    p.setPen(QPen(QBrush(eg), s * 0.045))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(body, s * 0.22, s * 0.22)

    # корпус микросхемы с выводами
    chip = QRectF(s * 0.28, s * 0.28, s * 0.44, s * 0.44)
    pen = QPen(QColor(theme.g1), s * 0.035, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.drawRoundedRect(chip, s * 0.05, s * 0.05)
    for i in (0.36, 0.5, 0.64):
        p.drawLine(QPointF(s * 0.18, s * i), QPointF(s * 0.28, s * i))
        p.drawLine(QPointF(s * 0.72, s * i), QPointF(s * 0.82, s * i))

    # молния поверх — прошивка идёт
    bolt = QPolygonF([QPointF(s * x / 100.0, s * y / 100.0)
                      for x, y in _BOLT])
    p.setPen(QPen(QColor("#0a0b0f"), s * 0.05, Qt.SolidLine, Qt.RoundCap,
                  Qt.RoundJoin))
    p.setBrush(QColor(theme.g2))
    p.drawPolygon(bolt)
    p.end()
    return pm


def app_icon(theme):
    ic = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(icon_pixmap(theme, sz))
    return ic
