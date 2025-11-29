# main.py
# Главный файл запуска программы

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox, QMessageBox
from PyQt5.QtGui import QIcon
from ui.blcl_tab import BlclTab
from ui.stlink_tab import StlinkTab
from ui.xilinx_tab import XilinxTab  # Новый импорт для Xilinx tab
from ui.jlink_tab import JlinkTab  # Новый импорт для J-Link tab
from ui.styles import apply_dark_theme
import serial.tools.list_ports
import serial

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLCL + STM32 + Xilinx Programmer")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(1400, 750)

        # Центральный виджет с горизонтальным layout
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Левая панель для COM-порта
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Выбор COM-порта
        com_layout = QHBoxLayout()
        self.com_label = QLabel("COM-порт:")
        self.com_combo = QComboBox()
        self.refresh_com_ports()
        com_refresh_btn = QPushButton("Обновить")
        com_refresh_btn.clicked.connect(self.refresh_com_ports)
        com_layout.addWidget(self.com_label)
        com_layout.addWidget(self.com_combo)
        com_layout.addWidget(com_refresh_btn)
        left_layout.addLayout(com_layout)

        # Кнопка подключения/отключения
        self.connect_com_btn = QPushButton("Подключиться")
        self.connect_com_btn.clicked.connect(self.toggle_com_connection)
        left_layout.addWidget(self.connect_com_btn)

        # Информация о версии и дате
        self.version_label = QLabel("Версия прошивки: Неизвестно")
        self.date_label = QLabel("Дата прошивки: Неизвестно")
        left_layout.addWidget(self.version_label)
        left_layout.addWidget(self.date_label)

        # Кнопка обновления информации
        self.update_info_btn = QPushButton("Обновить информацию")
        self.update_info_btn.clicked.connect(self.update_firmware_info)
        self.update_info_btn.setEnabled(False)
        left_layout.addWidget(self.update_info_btn)

        left_layout.addStretch()  # Заполнение пространства

        self.left_panel.setLayout(left_layout)
        self.left_panel.setFixedWidth(350)  # Фиксированная ширина панели
        main_layout.addWidget(self.left_panel)

        # Вкладки
        tabs = QTabWidget()
        tabs.addTab(BlclTab(self), "BLCL Loader")
        tabs.addTab(StlinkTab(self), "STM32 ST-Link")
        tabs.addTab(XilinxTab(self), "Xilinx JTAG")  # Новая вкладка
        tabs.addTab(JlinkTab(self), "J-Link Flash")  # Новая вкладка для J-Link

        tabs_container = QWidget()
        tabs_layout = QVBoxLayout(tabs_container)
        tabs_layout.addWidget(tabs)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(tabs_container)

        self.setCentralWidget(central)
        apply_dark_theme()

        self.serial_port = None
        self.is_com_connected = False

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
        if not com_port:
            QMessageBox.warning(self, "Ошибка", "Выберите COM-порт!")
            return
        try:
            self.serial_port = serial.Serial(com_port, baudrate=115200, timeout=1)  # Настройте baudrate по необходимости
            self.connect_com_btn.setText("Отключиться")
            self.update_info_btn.setEnabled(True)
            self.is_com_connected = True
            QMessageBox.information(self, "Успех", f"Подключено к {com_port}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось подключиться: {e}")

    def disconnect_com(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        self.connect_com_btn.setText("Подключиться")
        self.update_info_btn.setEnabled(False)
        self.is_com_connected = False
        self.version_label.setText("Версия прошивки: Неизвестно")
        self.date_label.setText("Дата прошивки: Неизвестно")
        QMessageBox.information(self, "Успех", "Отключено от COM-порта")

    def update_firmware_info(self):
        if not self.is_com_connected:
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())