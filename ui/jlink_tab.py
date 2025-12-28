# ui/jlink_tab.py
# Вкладка для прошивки hex и bin файлов через Segger J-Link
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox, QProgressDialog
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from core.jlink_flash import JLinkFlashThread, JLinkEraseThread
import os
import subprocess
import json
import tempfile
from utils.helpers import resource_path, find_jlink_exe  # Импорт resource_path и find_jlink_exe

class SearchThread(QThread):
    finished = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._stop_requested = False
    def requestInterruption(self):
        self._stop_requested = True
        super().requestInterruption()
    def run(self):
        path = find_jlink_exe()
        self.finished.emit(path)

class JlinkTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_target_connected = False
        self.setup_ui()
        self.load_cli_path() # Загружаем сохраненный путь (без автоматической проверки)
        self.load_mcu_models() # Загружаем сохраненные модели контроллеров

    def setup_ui(self):
        layout = QVBoxLayout()
        # Путь к JLink.exe или JLinkExe.exe
        cli_path_layout = QHBoxLayout()
        self.cli_path_label = QLabel("Путь к JLink.exe:")
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
        # Комбо-бокс для выбора контроллера
        device_layout = QHBoxLayout()
        self.device_label = QLabel("Контроллер:")
        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)
        self.device_combo.setInsertPolicy(QComboBox.InsertAtTop)
        device_layout.addWidget(self.device_label)
        device_layout.addWidget(self.device_combo)
        layout.addLayout(device_layout)
        # Статус J-Link программатора
        jlink_layout = QHBoxLayout()
        self.jlink_status = QLabel("J-Link: Не обнаружен")
        self.jlink_status.setStyleSheet("color: red;")
        self.connect_btn = QPushButton("Проверить J-Link")
        self.connect_btn.clicked.connect(self.check_jlink)
        jlink_layout.addWidget(QLabel("Программатор:"))
        jlink_layout.addWidget(self.jlink_status)
        jlink_layout.addWidget(self.connect_btn)
        layout.addLayout(jlink_layout)
        # Статус подключения к устройству (target)
        target_layout = QHBoxLayout()
        self.target_status = QLabel("Target: Не подключен")
        self.target_status.setStyleSheet("color: red;")
        self.target_btn = QPushButton("Подключиться")
        self.target_btn.clicked.connect(self.toggle_target)
        self.target_btn.setEnabled(False)
        target_layout.addWidget(QLabel("Устройство:"))
        target_layout.addWidget(self.target_status)
        target_layout.addWidget(self.target_btn)
        layout.addLayout(target_layout)
        # Файл для прошивки
        file_layout = QHBoxLayout()
        self.file_combo = QComboBox()
        self.file_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'firmware')
        os.makedirs(self.file_dir, exist_ok=True)
        self.refresh_file_list()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_file_list)
        file_layout.addWidget(QLabel("Файл (.hex/.bin):"))
        file_layout.addWidget(self.file_combo)
        file_layout.addWidget(refresh_btn)
        layout.addLayout(file_layout)
        # Кнопки Прошить и Очистить в одной строке
        buttons_layout = QHBoxLayout()
        self.flash_btn = QPushButton("Прошить")
        self.flash_btn.clicked.connect(self.start_jlink_flash)
        self.flash_btn.setEnabled(False)
        buttons_layout.addWidget(self.flash_btn)
        self.erase_btn = QPushButton("Очистить")
        self.erase_btn.clicked.connect(self.start_erase)
        self.erase_btn.setEnabled(False)
        buttons_layout.addWidget(self.erase_btn)
        layout.addLayout(buttons_layout)
        # Лог
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        self.setLayout(layout)

    def browse_cli(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать JLink.exe", "", "Executables (*.exe)")
        if file_name:
            if self.validate_jlink_exe(file_name):
                self.cli_path.setText(file_name)
                self.save_cli_path(file_name)
                self.check_jlink()
            else:
                QMessageBox.warning(self, "Ошибка", "Это не Segger J-Link Commander! Выберите правильный файл.")

    def search_cli(self):
        self.cli_path.setText("")
        self.search_thread = SearchThread()
        self.search_thread.finished.connect(self.on_search_finished)
        self.progress_dialog = QProgressDialog("Поиск JLink.exe... Это может занять время.", "Отмена", 0, 0, self)
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
            if path and self.validate_jlink_exe(path):
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

    def validate_jlink_exe(self, path):
        try:
            result = subprocess.run([path, "-?"], capture_output=True, text=True, timeout=5)
            return "SEGGER J-Link Commander" in result.stdout or "SEGGER J-Link" in result.stdout
        except Exception:
            return False

    def save_cli_path(self, path):
        resources_dir = resource_path(os.path.join('resources'))
        settings_path = os.path.join(resources_dir, 'settings.json')
        os.makedirs(resources_dir, exist_ok=True)
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
        else:
            settings = {}
        settings['jlink_cli_path'] = path
        with open(settings_path, 'w') as f:
            json.dump(settings, f)

    def load_cli_path(self):
        resources_dir = resource_path(os.path.join('resources'))
        settings_path = os.path.join(resources_dir, 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                path = settings.get('jlink_cli_path', '')
                if path and self.validate_jlink_exe(path):
                    self.cli_path.setText(path)
                else:
                    self.cli_path.setText('')

    def save_mcu_model(self, model):
        if not model:
            return
        resources_dir = resource_path(os.path.join('resources'))
        mcu_path = os.path.join(resources_dir, 'mcu.json')
        os.makedirs(resources_dir, exist_ok=True)
        if os.path.exists(mcu_path):
            with open(mcu_path, 'r') as f:
                models = json.load(f)
        else:
            models = []
        if model not in models:
            models.append(model)
        with open(mcu_path, 'w') as f:
            json.dump(models, f)

    def load_mcu_models(self):
        resources_dir = resource_path(os.path.join('resources'))
        mcu_path = os.path.join(resources_dir, 'mcu.json')
        if os.path.exists(mcu_path):
            with open(mcu_path, 'r') as f:
                models = json.load(f)
                if models:
                    self.device_combo.addItems(models)
                    self.device_combo.setCurrentText(models[-1])

    def refresh_file_list(self):
        self.file_combo.clear()
        if os.path.exists(self.file_dir):
            for f in os.listdir(self.file_dir):
                if f.lower().endswith(('.hex', '.bin')):
                    self.file_combo.addItem(f)

    def check_jlink(self):
        cli_path = self.cli_path.text()
        if not cli_path:
            QMessageBox.warning(self, "Ошибка", "Укажите путь к JLink.exe!")
            return
        if not self.validate_jlink_exe(cli_path):
            QMessageBox.warning(self, "Ошибка", "Это не Segger J-Link Commander! Укажите правильный путь.")
            return
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jlink', mode='w') as script_file:
                script_file.write("ShowEmuList USB\nexit\n")
                script_path = script_file.name
            result = subprocess.run([cli_path, "-CommanderScript", script_path], capture_output=True, text=True, timeout=10)
            os.unlink(script_path)
            self.log.append(result.stdout + result.stderr)
            if "J-Link" in result.stdout:
                self.jlink_status.setText("J-Link: Подключен")
                self.jlink_status.setStyleSheet("color: green;")
                self.target_btn.setEnabled(True)
                self.flash_btn.setEnabled(True)
                self.erase_btn.setEnabled(True)
            else:
                self.jlink_status.setText("J-Link: Не найден")
                self.jlink_status.setStyleSheet("color: red;")
                self.target_btn.setEnabled(False)
                self.flash_btn.setEnabled(False)
                self.erase_btn.setEnabled(False)
        except FileNotFoundError:
            QMessageBox.warning(self, "Ошибка", "JLink.exe не найден! Укажите полный путь.")
            self.log.append("Ошибка: Файл не найден. Укажите полный путь к JLink.exe.")
        except Exception as e:
            self.log.append(f"Ошибка: {e}")

    def toggle_target(self):
        cli_path = self.cli_path.text()
        device = self.device_combo.currentText().strip()
        if not device:
            QMessageBox.warning(self, "Ошибка", "Укажите контроллер!")
            return
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jlink', mode='w') as script_file:
                if self.is_target_connected:
                    # Полный скрипт для отключения с инициализацией
                    script_content = f"device {device}\nsi SWD\nspeed 4000\nr\nh\ng\nexit\n"
                    new_button_text = "Подключиться"
                    new_status_text = "Target: Не подключен"
                    new_color = "red"
                    self.is_target_connected = False
                else:
                    # Скрипт для подключения
                    script_content = f"device {device}\nsi SWD\nspeed 4000\nr\nh\nregs\nexit\n"
                    new_button_text = "Отключиться"
                    new_status_text = "Target: Подключен"
                    new_color = "green"
                    self.is_target_connected = True
                script_file.write(script_content)
                script_path = script_file.name
            # Увеличили таймаут до 20 секунд для стабильности
            result = subprocess.run([cli_path, "-CommanderScript", script_path], capture_output=True, text=True, timeout=20)
            os.unlink(script_path)
            self.log.append(result.stdout + result.stderr)
            if result.returncode != 0 or "ERROR" in result.stderr.upper():
                QMessageBox.warning(self, "Ошибка", "Ошибка при подключении/отключении!")
                return
            self.target_btn.setText(new_button_text)
            self.target_status.setText(new_status_text)
            self.target_status.setStyleSheet(f"color: {new_color};")
        except subprocess.TimeoutExpired:
            self.log.append("Ошибка: Таймаут при выполнении команды.")
            QMessageBox.warning(self, "Ошибка", "Таймаут при подключении/отключении! Проверьте устройство.")
        except Exception as e:
            self.log.append(f"Ошибка: {e}")
            QMessageBox.warning(self, "Ошибка", f"Исключение: {e}")

    def start_jlink_flash(self):
        if self.file_combo.count() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет файлов в папке firmware!")
            return
        file_path = os.path.join(self.file_dir, self.file_combo.currentText())
        cli_path = self.cli_path.text()
        device = self.device_combo.currentText().strip()
        if not device:
            QMessageBox.warning(self, "Ошибка", "Укажите контроллер!")
            return
        self.log.clear()
        self.flash_btn.setEnabled(False)
        self.thread = JLinkFlashThread(file_path, cli_path, device)
        self.thread.log.connect(self.log.append)
        self.thread.finished.connect(self.on_flash_finished)
        self.thread.start()

    def on_flash_finished(self, success):
        self.flash_btn.setEnabled(True)
        if success:
            self.save_mcu_model(self.device_combo.currentText().strip())
            QMessageBox.information(self, "Успех", "Прошивка завершена успешно!")
        else:
            QMessageBox.warning(self, "Ошибка", "Прошивка не удалась!")

    def start_erase(self):
        cli_path = self.cli_path.text()
        device = self.device_combo.currentText().strip()
        if not device:
            QMessageBox.warning(self, "Ошибка", "Укажите контроллер!")
            return
        self.log.clear()
        self.erase_btn.setEnabled(False)
        self.thread = JLinkEraseThread(cli_path, device)
        self.thread.log.connect(self.log.append)
        self.thread.finished.connect(self.on_erase_finished)
        self.thread.start()

    def on_erase_finished(self, success):
        self.erase_btn.setEnabled(True)
        if success:
            self.save_mcu_model(self.device_combo.currentText().strip())
            QMessageBox.information(self, "Успех", "Очистка завершена успешно!")
        else:
            QMessageBox.warning(self, "Ошибка", "Очистка не удалась!")