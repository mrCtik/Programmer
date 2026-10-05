# ui/version_tab.py
# Вынос панели с информацией о версии, дате и серийном номере прошивки + логика COM-подключения

import time
import serial.tools.list_ports
import serial
import json
import os
from PyQt5.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QComboBox
from PyQt5.QtCore import Qt
from logic import get_logic_module  # Импорт из logic/__init__.py
from utils.helpers import resource_path, data_path
from ui.kit.glass import glow
from ui.styles import THEME, role

class VersionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.serial_port = None
        self.is_com_connected = False
        self.original_version = ""
        self.original_date   = ""
        self.original_serial = ""
        self.projects = []           # Список проектов из JSON
        self.selected_project = None
        self.selected_board = None
        self.logic_module = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── COM Settings ───────────────────────────────────────────────
        com_group = QGroupBox("Подключение")
        com_vbox = QVBoxLayout()

        com_row = QHBoxLayout()
        com_row.addWidget(QLabel("COM-порт:"))
        self.com_combo = QComboBox()
        self.refresh_com_ports()
        com_row.addWidget(self.com_combo)
        com_vbox.addLayout(com_row)

        baud_row = QHBoxLayout()
        baud_row.addWidget(QLabel("Baudrate:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud_combo.setCurrentText('115200')
        baud_row.addWidget(self.baud_combo)
        com_vbox.addLayout(baud_row)

        com_group.setLayout(com_vbox)
        layout.addWidget(com_group)

        # Кнопки подключения / обновления портов
        buttons_row = QHBoxLayout()
        self.connect_btn = QPushButton("Подключиться")
        glow(self.connect_btn, THEME.g1, 22, 90)
        self.connect_btn.setFixedHeight(40)
        buttons_row.addWidget(self.connect_btn)

        refresh_btn = QPushButton("Обновить")
        role(refresh_btn, "ghost")
        refresh_btn.setFixedHeight(40)
        refresh_btn.clicked.connect(self.refresh_com_ports)
        buttons_row.addWidget(refresh_btn)
        layout.addLayout(buttons_row)

        # ── Выбор проекта и платы ──────────────────────────────────────
        project_group = QGroupBox("Проект")
        project_vbox = QVBoxLayout()
        project_row = QHBoxLayout()
        project_row.addWidget(QLabel("Проект:"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(300)
        self.project_combo.currentTextChanged.connect(self.on_project_changed)
        project_row.addWidget(self.project_combo)
        project_vbox.addLayout(project_row)
        project_group.setLayout(project_vbox)
        layout.addWidget(project_group)

        board_group = QGroupBox("Плата")
        board_vbox = QVBoxLayout()
        board_row = QHBoxLayout()
        board_row.addWidget(QLabel("Плата:"))
        self.board_combo = QComboBox()
        self.board_combo.setMinimumWidth(300)
        self.board_combo.currentTextChanged.connect(self.on_board_changed)
        board_row.addWidget(self.board_combo)
        board_vbox.addLayout(board_row)
        board_group.setLayout(board_vbox)
        layout.addWidget(board_group)

        # ── Текущая информация ─────────────────────────────────────────
        current_group = QGroupBox("Прошивка на плате")
        current_vbox = QVBoxLayout()
        self.version_label = QLabel("Версия прошивки: Неизвестно")
        self.date_label    = QLabel("Дата прошивки:   Неизвестно")
        self.serial_label  = QLabel("Серийный номер:  Неизвестно")
        for lbl in (self.version_label, self.date_label, self.serial_label):
            lbl.setMinimumWidth(280)
        current_vbox.addWidget(self.version_label)
        current_vbox.addWidget(self.date_label)
        current_vbox.addWidget(self.serial_label)
        current_group.setLayout(current_vbox)
        layout.addWidget(current_group)

        self.update_info_btn = QPushButton("Обновить информацию")
        glow(self.update_info_btn, THEME.g1, 22, 90)
        self.update_info_btn.setEnabled(False)
        self.update_info_btn.clicked.connect(self.update_firmware_info)
        layout.addWidget(self.update_info_btn)

        # ── Новая информация ───────────────────────────────────────────
        new_group = QGroupBox("Записать в плату")
        new_vbox = QVBoxLayout()

        # Версия
        v_row = QHBoxLayout()
        v_row.addWidget(QLabel("Новая версия:"))
        self.version_input = QLineEdit()
        self.version_input.textChanged.connect(self.check_changes)
        v_row.addWidget(self.version_input)
        new_vbox.addLayout(v_row)

        # Дата
        d_row = QHBoxLayout()
        d_row.addWidget(QLabel("Новая дата:"))
        self.date_input = QLineEdit(time.strftime("%Y-%m-%d"))
        self.date_input.textChanged.connect(self.check_changes)
        d_row.addWidget(self.date_input)
        new_vbox.addLayout(d_row)

        # Серийный номер
        s_row = QHBoxLayout()
        s_row.addWidget(QLabel("Новый серийный номер:"))
        self.serial_input = QLineEdit()
        self.serial_input.textChanged.connect(self.check_changes)
        s_row.addWidget(self.serial_input)
        new_vbox.addLayout(s_row)

        new_group.setLayout(new_vbox)
        layout.addWidget(new_group)

        # Кнопка отправки
        self.set_info_btn = QPushButton("Установить информацию")
        role(self.set_info_btn, "ghost")
        self.set_info_btn.setEnabled(False)
        self.set_info_btn.clicked.connect(self.set_firmware_info)
        layout.addWidget(self.set_info_btn)

        # Загрузка проектов
        self.load_projects()

        self.connect_btn.clicked.connect(self.toggle_com_connection)

    def load_projects(self):
        # сначала файл рядом с программой (его можно править без
        # пересборки), и только потом зашитый в exe
        json_path = data_path('resources', 'projects.json')
        if not os.path.exists(json_path):
            json_path = resource_path('resources/projects.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.projects = json.load(f)
                for project in self.projects:
                    self.project_combo.addItem(project['name'])
            if self.project_combo.count() > 0:
                self.project_combo.setCurrentIndex(0)
                self.on_project_changed(self.project_combo.currentText())
        else:
            QMessageBox.warning(self, "Ошибка", "Файл projects.json не найден!")

    def on_project_changed(self, text):
        self.selected_project = next((p for p in self.projects if p['name'] == text), None)
        self.board_combo.clear()
        self.selected_board = None
        self.logic_module = None
        if self.selected_project and 'boards' in self.selected_project:
            for board in self.selected_project['boards']:
                self.board_combo.addItem(board['name'])
            if self.board_combo.count() > 0:
                self.board_combo.setCurrentIndex(0)
                self.on_board_changed(self.board_combo.currentText())

    def on_board_changed(self, text):
        if not self.selected_project:
            return
        self.selected_board = next((b for b in self.selected_project['boards'] if b['name'] == text), None)
        if self.selected_board and 'logic_type' in self.selected_board:
            logic_type = self.selected_board['logic_type']
            self.logic_module = get_logic_module(logic_type)
            if not self.logic_module:
                import logic as logic_pkg
                reason = logic_pkg.last_error
                QMessageBox.warning(
                    self, "Предупреждение",
                    f"Логика '{logic_type}' для платы '{text}' не загружена."
                    + (f"\n\nПричина: {reason}" if reason else ""))
                self.logic_module = None
        else:
            self.logic_module = None

    def set_enabled(self, enabled):
        self.update_info_btn.setEnabled(enabled)
        self.set_info_btn.setEnabled(enabled)

    def reset_info(self):
        self.version_label.setText("Версия прошивки: Неизвестно")
        self.date_label.setText(  "Дата прошивки:   Неизвестно")
        self.serial_label.setText("Серийный номер:  Неизвестно")
        self.original_version = ""
        self.original_date   = ""
        self.original_serial = ""
        self.version_input.clear()
        self.date_input.setText(time.strftime("%Y-%m-%d"))
        self.serial_input.clear()
        self.check_changes()

    def update_firmware_info(self):
        if not self.is_com_connected or not self.serial_port:
            return
        if not self.logic_module:
            QMessageBox.warning(self, "Ошибка", "Выберите проект и плату с поддерживаемой логикой!")
            return

        reply = QMessageBox.information(self, "Инструкция",
                                        "Перезапустите устройство сейчас, чтобы оно отправило информацию.\n"
                                        "После перезапуска нажмите OK.")
        if reply != QMessageBox.Ok:
            return

        self.logic_module.read_firmware_info(self.serial_port, self)

    def set_firmware_info(self):
        if not self.is_com_connected or not self.serial_port:
            return
        if not self.logic_module:
            QMessageBox.warning(self, "Ошибка", "Выберите проект и плату с поддерживаемой логикой!")
            return

        version = self.version_input.text().strip()
        date    = self.date_input.text().strip()
        serial  = self.serial_input.text().strip()

        if not version or not date:
            QMessageBox.warning(self, "Ошибка", "Версия и дата — обязательные поля!")
            return

        # serial может быть пустым — в этом случае в прошивке обычно оставляют старое значение

        reply = QMessageBox.information(self, "Инструкция",
                                        "Перезапустите устройство сейчас.\n"
                                        "После перезапуска в течение 5 секунд нажмите OK для отправки команды.")
        if reply != QMessageBox.Ok:
            return

        self.serial_port.reset_input_buffer()
        self.logic_module.send_update(self.serial_port, version, date, serial, self)

    def check_changes(self):
        cv = self.version_input.text().strip()
        cd = self.date_input.text().strip()
        cs = self.serial_input.text().strip()

        changed = (
            (cv != self.original_version) or
            (cd != self.original_date)   or
            (cs != self.original_serial)
        )
        self.set_info_btn.setEnabled(changed and self.is_com_connected)

    # ── COM-порты ──────────────────────────────────────────────────
    def refresh_com_ports(self):
        self.com_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            desc = p.description
            suffix = f" ({p.device})"
            if desc.endswith(suffix):
                desc = desc[:-len(suffix)]
            self.com_combo.addItem(f"{p.device} - {desc}")

    def toggle_com_connection(self):
        if self.is_com_connected:
            self.disconnect_com()
        else:
            self.connect_com()

    def connect_com(self):
        text = self.com_combo.currentText()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Выберите COM-порт!")
            return
        com_port = text.split(' - ')[0]
        baud = int(self.baud_combo.currentText())

        try:
            self.serial_port = serial.Serial(com_port, baudrate=baud, timeout=1)
            self.connect_btn.setText("Отключиться")
            self.set_enabled(True)
            self.is_com_connected = True
            QMessageBox.information(self, "Успех", f"Подключено: {text}")
        except Exception as e:
            print(f"Ошибка открытия порта: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось подключиться:\n{e}")

    def disconnect_com(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        self.connect_btn.setText("Подключиться")
        self.set_enabled(False)
        self.reset_info()
        self.is_com_connected = False
        QMessageBox.information(self, "Успех", "Порт отключён")