# -*- coding: utf-8 -*-
"""Запуск внешних утилит.

Программа собрана с `console=False`, и каждый запуск консольной утилиты
(J-Link, STM32_Programmer_CLI, Vivado) открывал бы на секунду чёрное
окно. Флаг CREATE_NO_WINDOW это подавляет. Из исходников эффекта не
видно — там консоль и так есть.
"""

import subprocess
import sys

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0) \
    if sys.platform == 'win32' else 0


def run(cmd, **kw):
    """subprocess.run с перехватом вывода и без консольного окна."""
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    kw.setdefault('creationflags', NO_WINDOW)
    return subprocess.run(cmd, **kw)


def popen(cmd, **kw):
    """subprocess.Popen с потоковым выводом и без консольного окна."""
    kw.setdefault('stdout', subprocess.PIPE)
    kw.setdefault('stderr', subprocess.STDOUT)
    kw.setdefault('text', True)
    kw.setdefault('creationflags', NO_WINDOW)
    return subprocess.Popen(cmd, **kw)
