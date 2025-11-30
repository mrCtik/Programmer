# ui/version_tab.py
# Вынос панели с информацией о версии и дате прошивки, плюс логика COM-подключения

import time
import serial.tools.list_ports
import serial
from PyQt5.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QComboBox
from PyQt5.QtCore import Qt

class VersionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Ссылка на MainWindow, если нужно
        self.serial_port = None
        self.is_com_connected = False

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

        # Кнопка подключения (вынесено из main.py)
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.setFixedHeight(40)
        self.connect_btn.clicked.connect(self.toggle_com_connection)
        layout.addWidget(self.connect_btn)

        # Текущая информация о прошивке
        current_group = QGroupBox("Current Firmware Info")
        current_vbox = QVBoxLayout()
        self.version_label = QLabel("Версия прошивки: Неизвестно")
        self.date_label = QLabel("Дата прошивки: Неизвестно")
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
        version_row.addWidget(self.version_input)
        new_vbox.addLayout(version_row)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Новая дата:"))
        self.date_input = QLineEdit(time.strftime("%Y-%m-%d"))
        date_row.addWidget(self.date_input)
        new_vbox.addLayout(date_row)

        new_group.setLayout(new_vbox)
        layout.addWidget(new_group)

        # Кнопка установки новой информации
        self.set_info_btn = QPushButton("Установить информацию")
        self.set_info_btn.setEnabled(False)
        self.set_info_btn.clicked.connect(self.set_firmware_info)
        layout.addWidget(self.set_info_btn)

    def set_enabled(self, enabled):
        self.update_info_btn.setEnabled(enabled)
        self.set_info_btn.setEnabled(enabled)

    def reset_info(self):
        self.version_label.setText("Версия прошивки: Неизвестно")
        self.date_label.setText("Дата прошивки: Неизвестно")

    def update_firmware_info(self):
        if not self.is_com_connected or not self.serial_port:
            return
        try:
            # Предполагаем команды для чтения версии и даты (замените на реальные)
            self.serial_port.write(b'VER?\n')  # Команда для версии
            version = self.serial_port.readline().decode().strip()
            self.serial_port.write(b'DATE?\n')  # Команда для даты
            date = self.serial_port.readline().decode().strip()

            self.version_label.setText(f"Версия прошивки: {version}")
            self.date_label.setText(f"Дата прошивки: {date}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить информацию: {e}")

    def set_firmware_info(self):
        if not self.is_com_connected or not self.serial_port:
            return
        version = self.version_input.text().strip()
        date = self.date_input.text().strip()
        if not version or not date:
            QMessageBox.warning(self, "Ошибка", "Заполните поля версии и даты!")
            return
        try:
            # Предполагаем команды для установки версии и даты (замените на реальные)
            self.serial_port.write(f'SET_VER {version}\n'.encode())
            response = self.serial_port.readline().decode().strip()
            # self.log.append(response)  # Лог, если нужно
            self.serial_port.write(f'SET_DATE {date}\n'.encode())
            response = self.serial_port.readline().decode().strip()
            # self.log.append(response)
            QMessageBox.information(self, "Успех", "Информация установлена!")
            self.update_firmware_info()  # Обновляем отображение
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось установить информацию: {e}")

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