# ui/stlink_tab.py
# Вкладка для прошивки STM32 через ST-Link
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox, QProgressDialog
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication
from core.stlink_flash import STM32FlashThread
import os
from utils import proc, tools
from utils.helpers import find_stm32_cli, data_path
from ui.kit.glass import glow
from ui.kit.widgets import Pill
from ui.styles import THEME, group, role

class StlinkTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_cli_path() # Загружаем сохраненный путь

    def setup_ui(self):
        layout = QVBoxLayout()
        # Путь к STM32_Programmer_CLI.exe
        cli_path_layout = QHBoxLayout()
        self.cli_path_label = QLabel("Путь к STM32_Programmer_CLI.exe:")
        self.cli_path = QLineEdit()
        browse_btn = QPushButton("Обзор...")
        role(browse_btn, "ghost")
        browse_btn.clicked.connect(self.browse_cli)
        search_btn = QPushButton("Поиск")
        role(search_btn, "ghost")
        search_btn.clicked.connect(self.search_cli)
        cli_path_layout.addWidget(self.cli_path_label)
        cli_path_layout.addWidget(self.cli_path)
        cli_path_layout.addWidget(browse_btn)
        cli_path_layout.addWidget(search_btn)
        # Статус ST-Link
        stlink_layout = QHBoxLayout()
        self.stlink_status = Pill("Не обнаружен", "off")
        self.connect_btn = QPushButton("Проверить ST-Link")
        role(self.connect_btn, "ghost")
        self.connect_btn.clicked.connect(self.check_stlink)
        stlink_layout.addWidget(QLabel("Программатор:"))
        stlink_layout.addWidget(self.stlink_status)
        stlink_layout.addWidget(self.connect_btn)
        # Выбор прошивки
        firmware_layout = QHBoxLayout()
        self.firmware_combo = QComboBox()
        self.firmware_dir = data_path('firmware')
        self.refresh_firmware_list()
        refresh_btn = QPushButton("Обновить")
        role(refresh_btn, "ghost")
        refresh_btn.clicked.connect(self.refresh_firmware_list)
        firmware_layout.addWidget(QLabel("Прошивка:"))
        firmware_layout.addWidget(self.firmware_combo)
        firmware_layout.addWidget(refresh_btn)
        self.stm32_flash_btn = QPushButton("Прошить STM32")
        glow(self.stm32_flash_btn, THEME.g1, 22, 90)
        self.stm32_flash_btn.clicked.connect(self.start_stm32_flash)
        self.stm32_flash_btn.setEnabled(False)
        # Лог
        self.stm32_log = QTextEdit()
        self.stm32_log.setReadOnly(True)
        layout.addWidget(group("Программатор", cli_path_layout,
                               stlink_layout))
        layout.addWidget(group("Прошивка", firmware_layout,
                               self.stm32_flash_btn))
        layout.addWidget(group("Журнал", self.stm32_log), 1)
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
        self.search_thread = tools.SearchThread(find_stm32_cli, self)
        self.search_thread.found.connect(self.on_search_finished)
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
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.requestInterruption()

    def validate_stm32_cli(self, path):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            result = proc.run([path, "--help"], timeout=5)
            return "STM32CubeProgrammer" in (result.stdout or '')
        except Exception:
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def save_cli_path(self, path):
        tools.save_setting('stm32_cli_path', path)

    def load_cli_path(self):
        path = tools.get_setting('stm32_cli_path')
        if path and self.validate_stm32_cli(path):
            self.cli_path.setText(path)
            self.check_stlink()   # путь знаем — сразу смотрим, на месте ли ST-Link
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
        """Проверяет подключение ST-Link. В фоне: раньше окно замирало
        на всё время опроса."""
        cli_path = self.cli_path.text()
        if not cli_path:
            QMessageBox.warning(self, "Ошибка", "Укажите путь к STM32_Programmer_CLI.exe!")
            return
        if not self.validate_stm32_cli(cli_path):
            QMessageBox.warning(self, "Ошибка", "Это не STM32CubeProgrammer CLI! Укажите правильный путь.")
            return
        self.connect_btn.setEnabled(False)
        self.stlink_status.set_state("move", "Проверка…")
        self.check_thread = tools.CommandThread(
            [cli_path, "-c", "port=SWD"], timeout=10, parent=self)
        self.check_thread.done.connect(lambda code, out: self._on_stlink_checked(out))
        self.check_thread.failed.connect(self._on_stlink_check_failed)
        self.check_thread.start()

    def _on_stlink_checked(self, out):
        self.connect_btn.setEnabled(True)
        self.stm32_log.append(out)
        found = "ST-LINK" in out
        self.stlink_status.set_state("on" if found else "err",
                                     "Подключен" if found else "Не найден")
        self.stm32_flash_btn.setEnabled(found)

    def _on_stlink_check_failed(self, msg):
        self.connect_btn.setEnabled(True)
        self.stlink_status.set_state("err", "Не найден")
        self.stm32_flash_btn.setEnabled(False)
        self.stm32_log.append(f"Ошибка: {msg}")
        QMessageBox.warning(self, "Ошибка", msg)

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
        self.stm32_thread.done.connect(lambda s: self.stm32_flash_btn.setEnabled(True))
        self.stm32_thread.start()