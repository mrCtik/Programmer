# -*- coding: utf-8 -*-
"""Общее для вкладок программаторов: фоновые задачи и настройки.

Раньше каждая вкладка несла свою копию потока поиска и своих
load/save_cli_path. Здесь одна реализация на всех.
"""

import json
import os
import subprocess
import tempfile

from PyQt5.QtCore import QThread, pyqtSignal

from utils import proc
from utils.helpers import data_path


class CommandThread(QThread):
    """Запуск внешней утилиты в фоне.

    Проверки программатора занимали до минуты прямо в GUI-потоке, и
    Windows успевала показать «Не отвечает».
    """

    done = pyqtSignal(int, str)        # код возврата, вывод (stdout+stderr)
    failed = pyqtSignal(str)           # текст ошибки

    def __init__(self, cmd, timeout=None, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.timeout = timeout

    def run(self):
        try:
            r = proc.run(self.cmd, timeout=self.timeout)
            self.done.emit(r.returncode, (r.stdout or '') + (r.stderr or ''))
        except FileNotFoundError:
            self.failed.emit(f"Файл не найден: {self.cmd[0]}")
        except subprocess.TimeoutExpired:
            self.failed.emit(f"Таймаут {self.timeout} с: команда не ответила")
        except Exception as e:
            self.failed.emit(str(e))


class SearchThread(QThread):
    """Поиск утилиты по дискам. Отмена действительно останавливает обход:
    поисковик спрашивает should_stop на каждой папке."""

    found = pyqtSignal(str)

    def __init__(self, finder, parent=None):
        super().__init__(parent)
        self.finder = finder

    def run(self):
        try:
            path = self.finder(should_stop=self.isInterruptionRequested)
        except Exception:
            path = None
        self.found.emit(path or '')


# ---------------- настройки рядом с программой ----------------

def _settings_path():
    d = data_path('resources')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'settings.json')


def load_settings():
    try:
        with open(_settings_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_setting(key, default=''):
    return load_settings().get(key, default)


def save_setting(key, value):
    settings = load_settings()
    settings[key] = value
    try:
        with open(_settings_path(), 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def load_list(name, default=None):
    """Список в своём файле рядом с настройками (модели контроллеров)."""
    path = os.path.join(data_path('resources'), name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else list(default or [])
    except (OSError, ValueError):
        return list(default or [])


def save_list(name, items):
    d = data_path('resources')
    os.makedirs(d, exist_ok=True)
    try:
        with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def temp_script(text, suffix):
    """Временный скрипт для CLI-утилиты. Удалять через drop_temp()."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                     mode='w') as f:
        f.write(text)
        return f.name


def drop_temp(path):
    """Раньше os.unlink стоял после wait(): при исключении по дороге
    файл оставался в %TEMP% навсегда."""
    try:
        if path:
            os.unlink(path)
    except OSError:
        pass
