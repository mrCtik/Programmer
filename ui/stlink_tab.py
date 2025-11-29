# ui/stlink_tab.py
# Вкладка для прошивки STM32 через ST-Link

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox, QProgressDialog
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from core.stlink_flash import STM32FlashThread
import os
import subprocess
import glob
import json

class SearchThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stop_requested = False

    def requestInterruption(self):
        self._stop_requested = True
        super().requestInterruption()

    def run(self):
        possible_patterns = [
            'C:/**/STM32_Programmer_CLI.exe',
            'D:/**/STM32_Programmer_CLI.exe',
            'E:/**/STM32_Programmer_CLI.exe',
            # Добавьте другие диски при необходимости
        ]
        for pattern in possible_patterns:
            if self._stop_requested:
                self.finished.emit(None)
                return
            paths = glob.glob(pattern, recursive=True)
            if paths:
                self.finished.emit(paths[0])
                return
        self.finished.emit(None)

class StlinkTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_cli_path()  # Загружаем сохраненный путь

    def setup_ui(self):
        layout = QVBoxLayout()

        # Путь к STM32_Programmer_CLI.exe
        cli_path_layout = QHBoxLayout()
        self.cli_path_label = QLabel("Путь к STM32_Programmer_CLI.exe:")
        self.cli_path = QLineEdit()
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_cli)
        search_btn = QPushButton("Поиск")
        search_btn.clicked.connect(self.search_cli)
        cli_path_layout.addWidget(self.cli_path_label)
        cli_path_layout.addWidget(self.cli_path)
        cli_path_layout.addWidget(browse_btn)
        cli_path_layout.addWidget(search_btn)
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

    def browse_cli(self):
        """Открывает диалог для выбора файла"""
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать STM32_Programmer_CLI.exe", "", "Executables (*.exe)")
        if file_name:
            if self.validate_stm32_cli(file_name):
                self.cli_path.setText(file_name)
                self.save_cli_path(file_name)
                self.check_stlink()
            else:
                QMessageBox.warning(self, "Ошибка", "Это не STM32CubeProgrammer CLI! Выберите правильный файл.")

    def search_cli(self):
        self.cli_path.setText("")
        self.search_thread = SearchThread()
        self.search_thread.finished.connect(self.on_search_finished)

        self.progress_dialog = QProgressDialog("Поиск STM32_Programmer_CLI.exe... Это может занять время.", "Отмена", 0, 0, self)
        self.progress_dialog.setWindowTitle("Поиск CLI")
        self.progress_dialog.setMinimumWidth(400)
        self.progress_dialog.setMinimumHeight(int(self.progress_dialog.height() * 1.1))
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self.on_search_canceled)

        self.search_thread.start()
        self.progress_dialog.exec_()

    def on_search_finished(self, path):
        if self.progress_dialog:
            self.progress_dialog.setRange(0, 100)
            self.progress_dialog.setValue(100)
            if path and self.validate_stm32_cli(path):
                self.progress_dialog.setLabelText(f"CLI найден: {path}")
                self.cli_path.setText(path)
                self.save_cli_path(path)
            else:
                self.progress_dialog.setLabelText("CLI не найден или неверный.")
            self.progress_dialog.setCancelButtonText("Ok")
            self.progress_dialog.canceled.disconnect(self.on_search_canceled)
            self.progress_dialog.canceled.connect(self.progress_dialog.close)

    def on_search_canceled(self):
        if self.search_thread.isRunning():
            self.search_thread.requestInterruption()
            self.search_thread.wait()

    def validate_stm32_cli(self, path):
        try:
            result = subprocess.run([path, "--help"], capture_output=True, text=True, timeout=5)
            return "STM32CubeProgrammer" in result.stdout
        except Exception:
            return False

    def save_cli_path(self, path):
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
        else:
            settings = {}
        settings['stm32_cli_path'] = path
        with open(settings_path, 'w') as f:
            json.dump(settings, f)

    def load_cli_path(self):
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                path = settings.get('stm32_cli_path', '')
                if path and self.validate_stm32_cli(path):
                    self.cli_path.setText(path)
                    self.check_stlink()  # Автоматически проверяем, если путь загружен
                else:
                    self.cli_path.setText('')

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
        if not self.validate_stm32_cli(cli_path):
            QMessageBox.warning(self, "Ошибка", "Это не STM32CubeProgrammer CLI! Укажите правильный путь.")
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