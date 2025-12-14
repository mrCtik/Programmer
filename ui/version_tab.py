# ui/version_tab.py
# Вынос панели с информацией о версии и дате прошивки, плюс логика COM-подключения

import time
import serial.tools.list_ports
import serial
import json
import os
from PyQt5.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QComboBox
from PyQt5.QtCore import Qt
from logic import get_logic_module  # Импорт из logic/__init__.py

class VersionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Ссылка на MainWindow, если нужно
        self.serial_port = None
        self.is_com_connected = False
        self.original_version = ""
        self.original_date = ""
        self.projects = []  # Список проектов из JSON
        self.selected_project = None  # Текущий выбранный проект
        self.selected_board = None  # Текущая выбранная плата
        self.logic_module = None  # Модуль с логикой для выбранной платы

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Группа COM-порта (вынесено из main.py)
        com_group = QGroupBox("COM Settings")
        com_vbox = QVBoxLayout()

        # Строка COM-порт
        com_row = QHBoxLayout()
        com_row.addWidget(QLabel("COM-порт:"))
        self.com_combo = QComboBox()
        self.refresh_com_ports()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_com_ports)
        com_row.addWidget(self.com_combo)
        com_row.addWidget(refresh_btn)
        com_vbox.addLayout(com_row)

        # Строка Baudrate
        baud_row = QHBoxLayout()
        baud_row.addWidget(QLabel("Baudrate:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud_combo.setCurrentText('115200')
        baud_row.addWidget(self.baud_combo)
        com_vbox.addLayout(baud_row)

        com_group.setLayout(com_vbox)
        layout.addWidget(com_group)

        # Выпадающий список проектов под панелью COM
        project_group = QGroupBox("Select Project")
        project_vbox = QVBoxLayout()
        project_row = QHBoxLayout()
        project_row.addWidget(QLabel("Проект:"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(300)  # Сделали шире
        self.project_combo.currentTextChanged.connect(self.on_project_changed)
        project_row.addWidget(self.project_combo)
        project_vbox.addLayout(project_row)
        project_group.setLayout(project_vbox)
        layout.addWidget(project_group)

        # Выпадающий список плат (boards) под проектом
        board_group = QGroupBox("Select Board")
        board_vbox = QVBoxLayout()
        board_row = QHBoxLayout()
        board_row.addWidget(QLabel("Плата:"))
        self.board_combo = QComboBox()
        self.board_combo.setMinimumWidth(300)  # Сделали шире
        self.board_combo.currentTextChanged.connect(self.on_board_changed)
        board_row.addWidget(self.board_combo)
        board_vbox.addLayout(board_row)
        board_group.setLayout(board_vbox)
        layout.addWidget(board_group)

        # Кнопка подключения (вынесено из main.py)
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.setFixedHeight(40)
        self.connect_btn.clicked.connect(self.toggle_com_connection)
        layout.addWidget(self.connect_btn)

        # Текущая информация о прошивке
        current_group = QGroupBox("Current Firmware Info")
        current_vbox = QVBoxLayout()
        self.version_label = QLabel("Версия прошивки: Неизвестно")
        self.version_label.setMinimumWidth(200)  # Сделали уже (если это подпись)
        self.date_label = QLabel("Дата прошивки: Неизвестно")
        self.date_label.setMinimumWidth(200)  # Сделали уже (если это подпись)
        current_vbox.addWidget(self.version_label)
        current_vbox.addWidget(self.date_label)
        current_group.setLayout(current_vbox)
        layout.addWidget(current_group)

        # Кнопка обновления информации
        self.update_info_btn = QPushButton("Обновить информацию")
        self.update_info_btn.setEnabled(False)
        self.update_info_btn.clicked.connect(self.update_firmware_info)
        layout.addWidget(self.update_info_btn)

        # Новая информация о прошивке
        new_group = QGroupBox("New Firmware Info")
        new_vbox = QVBoxLayout()

        version_row = QHBoxLayout()
        version_row.addWidget(QLabel("Новая версия:"))
        self.version_input = QLineEdit()
        self.version_input.textChanged.connect(self.check_changes)
        version_row.addWidget(self.version_input)
        new_vbox.addLayout(version_row)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Новая дата:"))
        self.date_input = QLineEdit(time.strftime("%Y-%m-%d"))
        self.date_input.textChanged.connect(self.check_changes)
        date_row.addWidget(self.date_input)
        new_vbox.addLayout(date_row)

        new_group.setLayout(new_vbox)
        layout.addWidget(new_group)

        # Кнопка установки новой информации
        self.set_info_btn = QPushButton("Установить информацию")
        self.set_info_btn.setEnabled(False)
        self.set_info_btn.clicked.connect(self.set_firmware_info)
        layout.addWidget(self.set_info_btn)

        # Загружаем проекты (если нужно перезагрузить при init)
        self.load_projects()

    def load_projects(self):
        json_path = 'resources/projects.json'
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.projects = json.load(f)
                for project in self.projects:
                    self.project_combo.addItem(project['name'])
            # NEW: Инициализация первого проекта и плат, если есть
            if self.project_combo.count() > 0:
                self.project_combo.setCurrentIndex(0)
                self.on_project_changed(self.project_combo.currentText())
        else:
            QMessageBox.warning(self, "Ошибка", "Файл projects.json не найден в папке resources!")

    def on_project_changed(self, text):
        self.selected_project = next((p for p in self.projects if p['name'] == text), None)
        self.board_combo.clear()
        self.selected_board = None
        self.logic_module = None
        if self.selected_project and 'boards' in self.selected_project:
            for board in self.selected_project['boards']:
                self.board_combo.addItem(board['name'])
            # NEW: Инициализация первой платы, если есть
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
                QMessageBox.warning(self, "Предупреждение", f"Логика '{logic_type}' для платы '{text}' не реализована (файл logic_{logic_type}.py не найден).")
                self.logic_module = None
        else:
            self.logic_module = None

    def set_enabled(self, enabled):
        self.update_info_btn.setEnabled(enabled)
        self.set_info_btn.setEnabled(enabled)

    def reset_info(self):
        self.version_label.setText("Версия прошивки: Неизвестно")
        self.date_label.setText("Дата прошивки: Неизвестно")
        self.original_version = ""
        self.original_date = ""
        self.version_input.clear()
        self.date_input.setText(time.strftime("%Y-%m-%d"))
        self.check_changes()

    def calculate_crc8(self, data):
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
            crc &= 0xFF  # Обрезаем до 8 бит
        return crc

    def update_firmware_info(self):
        if not self.is_com_connected or not self.serial_port:
            return
        if not self.logic_module:
            QMessageBox.warning(self, "Ошибка", "Выберите проект и плату с поддерживаемой логикой!")
            return
        # Всплывающее окно с просьбой перезагрузить
        reply = QMessageBox.information(self, "Инструкция", "Перезапустите устройство (STM32) сейчас, чтобы оно отправило информацию, и нажмите OK для начала ожидания данных.")
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
        date = self.date_input.text().strip()
        if not version or not date:
            QMessageBox.warning(self, "Ошибка", "Заполните поля версии и даты!")
            return
        # Всплывающее окно с просьбой перезагрузить
        reply = QMessageBox.information(self, "Инструкция", "Перезапустите устройство (STM32) сейчас, чтобы оно вошло в режим ожидания обновления, и нажмите OK в течение 5 секунд после перезапуска для отправки команды.")
        if reply != QMessageBox.Ok:
            return
        self.serial_port.reset_input_buffer()  # Очистка буфера перед отправкой
        self.logic_module.send_update(self.serial_port, version, date, self)

    def check_changes(self):
        # Проверяем, изменились ли значения
        current_version = self.version_input.text().strip()
        current_date = self.date_input.text().strip()
        changed = (current_version != self.original_version) or (current_date != self.original_date)
        self.set_info_btn.setEnabled(changed and self.is_com_connected)

    # Методы для COM (вынесено из main.py)
    def refresh_com_ports(self):
        self.com_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.com_combo.addItem(port.device)

    def toggle_com_connection(self):
        if self.is_com_connected:
            self.disconnect_com()
        else:
            self.connect_com()

    def connect_com(self):
        com_port = self.com_combo.currentText()
        baud = int(self.baud_combo.currentText())
        if not com_port:
            QMessageBox.warning(self, "Ошибка", "Выберите COM-порт!")
            return
        try:
            self.serial_port = serial.Serial(com_port, baudrate=baud, timeout=1)  # Настройте baudrate по необходимости
            self.connect_btn.setText("Отключиться")
            self.set_enabled(True)
            self.is_com_connected = True
            QMessageBox.information(self, "Успех", f"Подключено к {com_port}")
            # Автоматически ждём и обновляем информацию после подключения
            self.update_firmware_info()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось подключиться: {e}")

    def disconnect_com(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        self.connect_btn.setText("Подключиться")
        self.set_enabled(False)
        self.reset_info()
        self.is_com_connected = False
        QMessageBox.information(self, "Успех", "Отключено от COM-порта")