# -*- coding: utf-8 -*-
"""Фон окна, стеклянная панель, свечение (UI_KIT.md, разделы 3, 4, 5).

Qt не умеет ни градиентной рамки, ни внешнего свечения, ни зерна —
всё это рисуется руками через QPainter.
"""

import random

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (QColor, QPainter, QPainterPath, QPen, QPixmap,
                         QLinearGradient, QRadialGradient, QFont, QBrush)
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QVBoxLayout

from . import theme as T

_noise = None


def noise_pixmap(size=140, seed=7):
    """Зерно — плитка из случайных белых точек.

    Без него полупрозрачные панели читаются как плоская заливка.
    Считается один раз и с фиксированным seed, чтобы картинка не
    «дышала» между запусками.
    """
    global _noise
    if _noise is not None:
        return _noise
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    rnd = random.Random(seed)
    for _ in range(size * size // 14):
        x = rnd.randrange(size)
        y = rnd.randrange(size)
        p.fillRect(x, y, 1, 1, QColor(255, 255, 255, rnd.randrange(4, 15)))
    p.end()
    _noise = pm
    return _noise


def paint_background(widget, painter, theme):
    """Три слоя: градиент, два акцентных пятна, зерно."""
    r = widget.rect()
    g = QLinearGradient(0, 0, 0, r.height())
    g.setColorAt(0.0, QColor("#101218"))
    g.setColorAt(1.0, QColor("#0a0b0f"))
    painter.fillRect(r, g)

    for color, cx in ((theme.g1, 0.16), (theme.g2, 0.86)):
        c = QColor(color)
        c.setAlpha(38)
        rad = max(r.width(), r.height()) * 0.72
        rg = QRadialGradient(QPointF(r.width() * cx, r.height() * 0.05), rad)
        rg.setColorAt(0.0, c)
        rg.setColorAt(0.62, QColor(c.red(), c.green(), c.blue(), 0))
        painter.fillRect(r, QBrush(rg))

    painter.fillRect(r, QBrush(noise_pixmap()))


class GlassRoot(QWidget):
    """Подложка окна: то же самое обязательно и для диалогов, иначе
    они выпадают из оформления серой плитой."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        paint_background(self, p, self.theme)


class GlassPanel(QWidget):
    """Стеклянная панель с неоновым кантом и заголовком-капсулой.

    Содержимое кладётся в panel.content, НЕ в саму панель.
    setStyleSheet у панели вызывать нельзя: своя таблица стилей
    перебивает глобальную для всего поддерева (UI_KIT, грабля №1).
    """

    RADIUS = 16
    CAP_H = 26

    def __init__(self, title, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.title = (title or "").upper()
        # капсула сидит на канте и заходит внутрь на половину высоты —
        # содержимое должно начинаться ниже неё, иначе наложение
        top = (9 + self.CAP_H // 2 + 4) if self.title else 12
        self.content = QWidget(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, top, 14, 12)
        lay.addWidget(self.content)

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = self.theme
        body = QRectF(self.rect()).adjusted(9, 9 if self.title else 6, -9, -9)
        rr = self.RADIUS

        # свечение контура: три обводки наружу от тела панели
        for width, alpha in ((8, 9), (5, 16), (2, 26)):
            c = QColor(t.g1)
            c.setAlpha(alpha)
            p.setPen(QPen(c, width))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(body, rr, rr)

        # стекло
        g = QLinearGradient(body.topLeft(), body.bottomLeft())
        g.setColorAt(0.0, QColor(38, 42, 54, 190))
        g.setColorAt(1.0, QColor(20, 22, 30, 200))
        path = QPainterPath()
        path.addRoundedRect(body, rr, rr)
        p.fillPath(path, QBrush(g))

        # блик сверху, обрезанный по скруглению
        p.save()
        p.setClipPath(path)
        hl = QLinearGradient(body.topLeft(), body.topLeft() + QPointF(0, 40))
        hl.setColorAt(0.0, QColor(255, 255, 255, 16))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(body.left(), body.top(), body.width(), 40), QBrush(hl))
        p.restore()

        # кант: линия с градиентом акцентной пары по диагонали
        eg = QLinearGradient(body.topLeft(), body.bottomRight())
        c1, c2 = QColor(t.g1), QColor(t.g2)
        c1.setAlpha(110)
        c2.setAlpha(110)
        eg.setColorAt(0.0, c1)
        eg.setColorAt(1.0, c2)
        p.setPen(QPen(QBrush(eg), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(body, rr, rr)

        if not self.title:
            return

        # заголовок-капсула на самом канте
        f = QFont(T.SANS, 8)
        f.setBold(True)
        f.setLetterSpacing(QFont.PercentageSpacing, 112)
        p.setFont(f)
        w = p.fontMetrics().width(self.title) + 22
        cap = QRectF(body.left() + 16, body.top() - self.CAP_H / 2.0,
                     w, self.CAP_H)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1b1e27"))
        p.drawRoundedRect(cap, self.CAP_H / 2.0, self.CAP_H / 2.0)
        p.setPen(QPen(QBrush(eg), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(cap, self.CAP_H / 2.0, self.CAP_H / 2.0)
        p.setPen(QColor(T.TEXT_SOFT))
        p.drawText(cap, Qt.AlignCenter, self.title)


def glow(widget, color, radius=26, alpha=110):
    """Свечение кнопке — QSS этого не умеет."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(radius)
    eff.setOffset(0, 0)
    c = QColor(color)
    c.setAlpha(alpha)
    eff.setColor(c)
    widget.setGraphicsEffect(eff)
    return eff
