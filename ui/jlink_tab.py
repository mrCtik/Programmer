# ui/jlink_tab.py
# Вкладка для прошивки hex и bin файлов через Segger J-Link
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication
from core.jlink_flash import JLinkFlashThread, JLinkEraseThread
import os
from utils import proc, tools
from utils.helpers import find_jlink_exe, data_path
from ui.kit.glass import glow
from ui.kit.widgets import Pill
from ui.styles import THEME, group, role

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
        role(browse_btn, "ghost")
        browse_btn.clicked.connect(self.browse_cli)
        search_btn = QPushButton("Поиск")
        role(search_btn, "ghost")
        search_btn.clicked.connect(self.search_cli)
        cli_path_layout.addWidget(self.cli_path_label)
        cli_path_layout.addWidget(self.cli_path)
        cli_path_layout.addWidget(browse_btn)
        cli_path_layout.addWidget(search_btn)
        # Комбо-бокс для выбора контроллера
        device_layout = QHBoxLayout()
        self.device_label = QLabel("Контроллер:")
        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)
        self.device_combo.setInsertPolicy(QComboBox.InsertAtTop)
        device_layout.addWidget(self.device_label)
        device_layout.addWidget(self.device_combo)
        # Статус J-Link программатора
        jlink_layout = QHBoxLayout()
        self.jlink_status = Pill("Не обнаружен", "off")
        self.connect_btn = QPushButton("Проверить J-Link")
        role(self.connect_btn, "ghost")
        self.connect_btn.clicked.connect(self.check_jlink)
        jlink_layout.addWidget(QLabel("Программатор:"))
        jlink_layout.addWidget(self.jlink_status)
        jlink_layout.addWidget(self.connect_btn)
        # Статус подключения к устройству (target)
        target_layout = QHBoxLayout()
        self.target_status = Pill("Не подключен", "off")
        self.target_btn = QPushButton("Подключиться")
        role(self.target_btn, "ghost")
        self.target_btn.clicked.connect(self.toggle_target)
        self.target_btn.setEnabled(False)
        target_layout.addWidget(QLabel("Устройство:"))
        target_layout.addWidget(self.target_status)
        target_layout.addWidget(self.target_btn)
        # Файл для прошивки
        file_layout = QHBoxLayout()
        self.file_combo = QComboBox()
        self.file_dir = data_path('firmware')
        os.makedirs(self.file_dir, exist_ok=True)
        self.refresh_file_list()
        refresh_btn = QPushButton("Обновить")
        role(refresh_btn, "ghost")
        refresh_btn.clicked.connect(self.refresh_file_list)
        file_layout.addWidget(QLabel("Файл (.hex/.bin):"))
        file_layout.addWidget(self.file_combo)
        file_layout.addWidget(refresh_btn)
        # Кнопки Прошить и Очистить в одной строке
        buttons_layout = QHBoxLayout()
        self.flash_btn = QPushButton("Прошить")
        glow(self.flash_btn, THEME.g1, 22, 90)
        self.flash_btn.clicked.connect(self.start_jlink_flash)
        self.flash_btn.setEnabled(False)
        buttons_layout.addWidget(self.flash_btn)
        self.erase_btn = QPushButton("Очистить")
        role(self.erase_btn, "danger")
        self.erase_btn.clicked.connect(self.start_erase)
        self.erase_btn.setEnabled(False)
        buttons_layout.addWidget(self.erase_btn)
        # Лог
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(group("Программатор", cli_path_layout,
                               device_layout, jlink_layout, target_layout))
        layout.addWidget(group("Прошивка", file_layout, buttons_layout))
        layout.addWidget(group("Журнал", self.log), 1)
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
        self.search_thread = tools.SearchThread(find_jlink_exe, self)
        self.search_thread.found.connect(self.on_search_finished)
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
        # просто просим остановиться: обход проверяет флаг на каждой папке
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.requestInterruption()

    def validate_jlink_exe(self, path):
        """Быстрая проверка «тот ли это файл». Ответ приходит сразу,
        но курсор всё равно меняем — вдруг диск спит."""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            result = proc.run([path, "-?"], timeout=5)
            out = result.stdout or ''
            return "SEGGER J-Link Commander" in out or "SEGGER J-Link" in out
        except Exception:
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def save_cli_path(self, path):
        tools.save_setting('jlink_cli_path', path)

    def load_cli_path(self):
        path = tools.get_setting('jlink_cli_path')
        if path and self.validate_jlink_exe(path):
            self.cli_path.setText(path)
        else:
            self.cli_path.setText('')

    def save_mcu_model(self, model):
        if not model:
            return
        models = tools.load_list('mcu.json')
        if model not in models:
            models.append(model)
            tools.save_list('mcu.json', models)

    def load_mcu_models(self):
        models = tools.load_list('mcu.json')
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
        script = tools.temp_script("ShowEmuList USB\nexit\n", '.jlink')
        self.connect_btn.setEnabled(False)
        self.jlink_status.set_state("move", "Проверка…")
        self.check_thread = tools.CommandThread(
            [cli_path, "-CommanderScript", script], timeout=10, parent=self)
        self.check_thread.done.connect(
            lambda code, out, s=script: self._on_jlink_checked(out, s))
        self.check_thread.failed.connect(
            lambda msg, s=script: self._on_jlink_check_failed(msg, s))
        self.check_thread.start()

    def _set_jlink_found(self, found):
        self.target_btn.setEnabled(found)
        self.flash_btn.setEnabled(found)
        self.erase_btn.setEnabled(found)

    def _on_jlink_checked(self, out, script):
        tools.drop_temp(script)
        self.connect_btn.setEnabled(True)
        self.log.append(out)
        if "J-Link" in out:
            self.jlink_status.set_state("on", "Подключен")
            self._set_jlink_found(True)
        else:
            self.jlink_status.set_state("err", "Не найден")
            self._set_jlink_found(False)

    def _on_jlink_check_failed(self, msg, script):
        tools.drop_temp(script)
        self.connect_btn.setEnabled(True)
        self.jlink_status.set_state("err", "Не найден")
        self._set_jlink_found(False)
        self.log.append(f"Ошибка: {msg}")
        QMessageBox.warning(self, "Ошибка", msg)

    def toggle_target(self):
        cli_path = self.cli_path.text()
        device = self.device_combo.currentText().strip()
        if not device:
            QMessageBox.warning(self, "Ошибка", "Укажите контроллер!")
            return
        if self.is_target_connected:
            script_content = f"device {device}\nsi SWD\nspeed 4000\nr\nh\ng\nexit\n"
        else:
            script_content = f"device {device}\nsi SWD\nspeed 4000\nr\nh\nregs\nexit\n"
        script = tools.temp_script(script_content, '.jlink')
        self.target_btn.setEnabled(False)
        self.target_status.set_state("move", "Ждём…")
        self.target_thread = tools.CommandThread(
            [cli_path, "-CommanderScript", script], timeout=20, parent=self)
        self.target_thread.done.connect(
            lambda code, out, s=script: self._on_target_done(code, out, s))
        self.target_thread.failed.connect(
            lambda msg, s=script: self._on_target_failed(msg, s))
        self.target_thread.start()

    def _restore_target_state(self):
        if self.is_target_connected:
            self.target_btn.setText("Отключиться")
            self.target_status.set_state("on", "Подключен")
        else:
            self.target_btn.setText("Подключиться")
            self.target_status.set_state("off", "Не подключен")

    def _on_target_done(self, code, out, script):
        tools.drop_temp(script)
        self.target_btn.setEnabled(True)
        self.log.append(out)
        if code != 0 or "ERROR" in out.upper():
            # состояние переключаем только по факту успеха, иначе кнопка
            # и плашка начинали врать после первой же ошибки
            self._restore_target_state()
            QMessageBox.warning(self, "Ошибка", "Ошибка при подключении/отключении!")
            return
        self.is_target_connected = not self.is_target_connected
        self._restore_target_state()

    def _on_target_failed(self, msg, script):
        tools.drop_temp(script)
        self.target_btn.setEnabled(True)
        self._restore_target_state()
        self.log.append(f"Ошибка: {msg}")
        QMessageBox.warning(self, "Ошибка", msg)

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
        self.thread.done.connect(self.on_flash_finished)
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
        if QMessageBox.question(
                self, "Очистить память",
                f"Стереть всю флеш-память {device}?\n\n"
                "Прошивка на плате будет потеряна, восстановить её можно\n"
                "только повторной записью.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        self.log.clear()
        self.erase_btn.setEnabled(False)
        self.thread = JLinkEraseThread(cli_path, device)
        self.thread.log.connect(self.log.append)
        self.thread.done.connect(self.on_erase_finished)
        self.thread.start()

    def on_erase_finished(self, success):
        self.erase_btn.setEnabled(True)
        if success:
            self.save_mcu_model(self.device_combo.currentText().strip())
            QMessageBox.information(self, "Успех", "Очистка завершена успешно!")
        else:
            QMessageBox.warning(self, "Ошибка", "Очистка не удалась!")