# ui/stlink_tab.py
# Вкладка для прошивки STM32 через ST-Link

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox
from core.stlink_flash import STM32FlashThread
import os
import subprocess

class StlinkTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.auto_detect_cli_path()  # Автоматически ищем путь

    def setup_ui(self):
        layout = QVBoxLayout()

        # Путь к STM32_Programmer_CLI.exe
        cli_path_layout = QHBoxLayout()
        self.cli_path_label = QLabel("Путь к STM32_Programmer_CLI.exe:")
        self.cli_path = QLineEdit()
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_cli)
        cli_path_layout.addWidget(self.cli_path_label)
        cli_path_layout.addWidget(self.cli_path)
        cli_path_layout.addWidget(browse_btn)
        layout.addLayout(cli_path_layout)

        # Статус ST-Link
        stlink_layout = QHBoxLayout()
        self.stlink_status = QLabel("ST-Link: Не обнаружен")
        self.stlink_status.setStyleSheet("color: red;")
        self.connect_btn = QPushButton("Проверить ST-Link")
        self.connect_btn.clicked.connect(self.check_stlink)
        stlink_layout.addWidget(QLabel("Программатор:"))
        stlink_layout.addWidget(self.stlink_status)
        stlink_layout.addWidget(self.connect_btn)
        layout.addLayout(stlink_layout)

        # Выбор прошивки
        firmware_layout = QHBoxLayout()
        self.firmware_combo = QComboBox()
        self.firmware_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'firmware')
        self.refresh_firmware_list()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_firmware_list)
        firmware_layout.addWidget(QLabel("Прошивка:"))
        firmware_layout.addWidget(self.firmware_combo)
        firmware_layout.addWidget(refresh_btn)
        layout.addLayout(firmware_layout)

        self.stm32_flash_btn = QPushButton("Прошить STM32")
        self.stm32_flash_btn.clicked.connect(self.start_stm32_flash)
        self.stm32_flash_btn.setEnabled(False)
        layout.addWidget(self.stm32_flash_btn)

        # Лог
        self.stm32_log = QTextEdit()
        self.stm32_log.setReadOnly(True)
        layout.addWidget(self.stm32_log)

        self.setLayout(layout)

    def auto_detect_cli_path(self):
        """Автоматически ищет STM32_Programmer_CLI.exe"""
        default_paths = [
            r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
            r"C:\ST\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
            "STM32_Programmer_CLI"  # Если в PATH
        ]
        for path in default_paths:
            if os.path.exists(path) or self.check_cli_executable(path):
                self.cli_path.setText(path)
                self.check_stlink()  # Автоматически проверяем
                return
        self.stm32_log.append("STM32_Programmer_CLI.exe не найден автоматически. Укажите путь вручную.")

    def check_cli_executable(self, path):
        """Проверяет, существует ли исполняемый файл"""
        try:
            subprocess.run([path, "--version"], capture_output=True, timeout=5)
            return True
        except:
            return False

    def browse_cli(self):
        """Открывает диалог для выбора файла"""
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать STM32_Programmer_CLI.exe", "", "Executables (*.exe)")
        if file_name:
            self.cli_path.setText(file_name)
            self.check_stlink()

    def refresh_firmware_list(self):
        """Обновляет список прошивок из папки firmware"""
        self.firmware_combo.clear()
        if os.path.exists(self.firmware_dir):
            for f in os.listdir(self.firmware_dir):
                if f.lower().endswith(('.bin', '.hex')):
                    self.firmware_combo.addItem(f)

    def check_stlink(self):
        """Проверяет подключение ST-Link"""
        cli_path = self.cli_path.text()
        if not cli_path:
            QMessageBox.warning(self, "Ошибка", "Укажите путь к STM32_Programmer_CLI.exe!")
            return
        try:
            result = subprocess.run([cli_path, "-c", "port=SWD"], capture_output=True, text=True, timeout=10)
            self.stm32_log.append(result.stdout + result.stderr)
            if "ST-LINK" in result.stdout:
                self.stlink_status.setText("ST-Link: Подключен")
                self.stlink_status.setStyleSheet("color: green;")
                self.stm32_flash_btn.setEnabled(True)
            else:
                self.stlink_status.setText("ST-Link: Не найден")
                self.stlink_status.setStyleSheet("color: red;")
                self.stm32_flash_btn.setEnabled(False)
        except FileNotFoundError:
            QMessageBox.warning(self, "Ошибка", "STM32_Programmer_CLI.exe не найден! Укажите полный путь.")
            self.stm32_log.append("Ошибка: Файл не найден. Укажите полный путь к STM32_Programmer_CLI.exe.")
        except Exception as e:
            self.stm32_log.append(f"Ошибка: {e}")

    def start_stm32_flash(self):
        """Запускает прошивку STM32"""
        if self.firmware_combo.count() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет прошивок в папке firmware!")
            return
        bin_path = os.path.join(self.firmware_dir, self.firmware_combo.currentText())
        cli_path = self.cli_path.text()
        self.stm32_log.clear()
        self.stm32_flash_btn.setEnabled(False)
        self.stm32_thread = STM32FlashThread(bin_path, cli_path)
        self.stm32_thread.log.connect(self.stm32_log.append)
        self.stm32_thread.finished.connect(lambda s: self.stm32_flash_btn.setEnabled(True))
        self.stm32_thread.start()