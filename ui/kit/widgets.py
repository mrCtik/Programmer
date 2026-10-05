# -*- coding: utf-8 -*-
"""Элементы, которых нет в Qt (UI_KIT.md, разделы 7, 11).

Плашка состояния, тумблер, подпись с подсказкой. Всё рисуется руками:
полумеры через QSS выглядят хуже, чем честный QPainter.
"""

from PyQt5.QtCore import (Qt, QRectF, QPropertyAnimation, pyqtProperty,
                          pyqtSignal, QEasingCurve, QSize)
from PyQt5.QtGui import (QColor, QPainter, QPen, QFont, QBrush,
                         QFontMetrics, QLinearGradient)
from PyQt5.QtWidgets import (QWidget, QLabel, QHBoxLayout,
                             QSizePolicy)

from . import theme as T


class Pill(QWidget):
    """Состояние словом и заливкой, без иконок.

    Тёмный текст на светлой заливке в активных состояниях — плашка
    читается с расстояния и не спорит с акцентом.
    """

    STATES = {
        "off":  ("#aab6c8", "#454d5e", "#2e3441"),
        "on":   ("#05211a", "#6ee7b7", "#10b981"),
        "move": ("#241700", "#fcd34d", "#f59e0b"),
        "err":  ("#2b0611", "#fda4af", "#e11d48"),
    }

    def __init__(self, text="", state="off", parent=None):
        super().__init__(parent)
        self._text = text
        self._state = state
        self.setMinimumHeight(26)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self._resize()

    def _resize(self):
        self.setFixedWidth(self.sizeHint().width())

    def set_state(self, state, text=None):
        self._state = state if state in self.STATES else "off"
        if text is not None:
            self._text = text
        self._resize()
        self.updateGeometry()
        self.update()

    def setText(self, text):
        self.set_state(self._state, text)

    def text(self):
        return self._text

    def _font(self):
        f = QFont(T.SANS, 8)
        f.setBold(True)
        f.setLetterSpacing(QFont.PercentageSpacing, 106)
        return f

    def sizeHint(self):
        fm = QFontMetrics(self._font())
        return QSize(fm.width(self._text.upper()) + 26, 26)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        fg, c1, c2 = self.STATES[self._state]
        r = QRectF(0, (self.height() - 24) / 2.0, self.width(), 24)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0.0, QColor(c1))
        g.setColorAt(1.0, QColor(c2))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QColor(fg))
        p.setFont(self._font())
        p.drawText(r, Qt.AlignCenter, self._text.upper())


class Toggle(QWidget):
    """48x26, ползунок ездит анимацией 150 мс.

    Тумблер вместо флажка там, где значение меняется часто и у него
    два равноправных состояния.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, theme, checked=False, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._checked = checked
        self._p = 1.0 if checked else 0.0
        self.setFixedSize(46, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"slide", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def get_slide(self):
        return self._p

    def set_slide(self, v):
        self._p = v
        self.update()

    slide = pyqtProperty(float, fget=get_slide, fset=set_slide)

    def isChecked(self):
        return self._checked

    def setChecked(self, v, animate=True):
        v = bool(v)
        if v == self._checked:
            return
        self._checked = v
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._p)
            self._anim.setEndValue(1.0 if v else 0.0)
            self._anim.start()
        else:
            self.set_slide(1.0 if v else 0.0)
        self.toggled.emit(v)

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        rad = r.height() / 2.0

        g = QLinearGradient(r.topLeft(), r.topRight())
        c1, c2 = QColor(self.theme.g1), QColor(self.theme.g2)
        c1.setAlpha(int(40 + 130 * self._p))
        c2.setAlpha(int(40 + 190 * self._p))
        g.setColorAt(0.0, c1)
        g.setColorAt(1.0, c2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(10, 12, 17, 220))
        p.drawRoundedRect(r, rad, rad)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, rad, rad)

        edge = QColor(self.theme.g1)
        edge.setAlpha(int(60 + 90 * self._p))
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, rad, rad)

        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._p
        knob = QColor("#e9edf4") if self._checked else QColor("#8b95a7")
        p.setPen(Qt.NoPen)
        p.setBrush(knob)
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class SwitchBox(QWidget):
    """Тумблер с подписью. Заменяет QCheckBox без правок в вызовах."""

    toggled = pyqtSignal(bool)

    def __init__(self, text, theme, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        self.sw = Toggle(theme)
        self.lbl = QLabel(text)
        self.lbl.setProperty("role", "soft")
        lay.addWidget(self.sw)
        lay.addWidget(self.lbl)
        self.sw.toggled.connect(self.toggled.emit)

    def isChecked(self):
        return self.sw.isChecked()

    def setChecked(self, v):
        self.sw.setChecked(v)

    def setText(self, t):
        self.lbl.setText(t)

    def set_theme(self, theme):
        self.sw.set_theme(theme)

    def setToolTip(self, tip):
        super().setToolTip(tip)
        self.sw.setToolTip(tip)
        self.lbl.setToolTip(tip)


class TipLabel(QLabel):
    """Подпись с пунктирным подчёркиванием, если к ней есть пояснение:
    видно, что здесь есть что рассказать."""

    def __init__(self, text, tip="", role="label", parent=None):
        super().__init__(text, parent)
        self.setProperty("role", role)
        if tip:
            self.setToolTip(tip)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self.toolTip():
            return
        p = QPainter(self)
        c = QColor(T.TEXT_DIM)
        c.setAlpha(120)
        pen = QPen(c, 1, Qt.DotLine)
        p.setPen(pen)
        w = self.fontMetrics().width(self.text())
        y = self.height() - 3
        p.drawLine(0, y, min(w, self.width()), y)
