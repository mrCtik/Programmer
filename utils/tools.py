# -*- coding: utf-8 -*-
"""Общее для вкладок программаторов: фоновые задачи и настройки.

Раньше каждая вкладка несла свою копию потока поиска и своих
load/save_cli_path. Здесь одна реализация на всех.
"""

import json
import os
import subprocess
import tempfile

from PyQt5.QtCore import (QFileSystemWatcher, QObject, QThread, QTimer,
                          pyqtSignal)

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


def fill_combo(combo, directory, extensions, empty_first=False):
    """Перечитывает папку в выпадающий список, сохраняя выбранное.

    Возвращает список имён. Выбор сохраняется обязательно: список
    перечитывается сам при появлении файла в папке, и сбрасывать при
    этом то, что человек уже выбрал, нельзя.
    """
    exts = tuple(e.lower() for e in extensions)
    names = []
    if os.path.isdir(directory):
        names = sorted(f for f in os.listdir(directory)
                       if f.lower().endswith(exts))

    current = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    if empty_first:
        combo.addItem("")
    combo.addItems(names)
    idx = combo.findText(current)
    combo.setCurrentIndex(idx if idx >= 0 else 0)
    combo.blockSignals(False)
    return names


class FolderWatcher(QObject):
    """Следит за папкой и зовёт on_change, когда в ней что-то меняется.

    Нужно, чтобы новая прошивка, положенная в папку при открытой
    программе, появлялась в списке сама. Срабатывания копятся в таймер:
    копирование файла даёт несколько событий подряд, а большой .bit
    успевает дописаться за время задержки.
    """

    def __init__(self, directory, on_change, delay_ms=800, parent=None):
        super().__init__(parent)
        self.directory = directory
        self._on_change = on_change
        self._watcher = QFileSystemWatcher(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._fire)
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self.start()

    def start(self):
        if os.path.isdir(self.directory) \
                and self.directory not in self._watcher.directories():
            self._watcher.addPath(self.directory)

    def _on_dir_changed(self, _path):
        self._timer.start()

    def _fire(self):
        # после некоторых операций (папку пересоздали) путь слетает
        self.start()
        try:
            self._on_change()
        except Exception as e:
            print(f"[watch] {self.directory}: {e}")
