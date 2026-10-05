# ui/xilinx_tab.py
# Вкладка для прошивки Xilinx Configuration Memory Device через JTAG (.mcs)
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox, QProgressBar, QProgressDialog
from PyQt5.QtCore import QTimer, Qt
from core.xilinx_flash import XilinxFlashThread
import os
from utils import tools
from utils.helpers import find_xilinx_cli, data_path
from ui.kit.glass import glow
from ui.kit.widgets import Pill
from ui.styles import THEME, group, role

class XilinxTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_cli_path()

    def setup_ui(self):
        layout = QVBoxLayout()
        # Путь к CLI
        cli_path_layout = QHBoxLayout()
        self.cli_path_label = QLabel("Путь к CLI:")
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
        # Тип Config Memory
        flash_part_layout = QHBoxLayout()
        self.flash_part_label = QLabel("Тип Config Memory:")
        self.flash_part = QLineEdit("mx25v1635f-spi-x1_x2_x4")
        flash_part_layout.addWidget(self.flash_part_label)
        flash_part_layout.addWidget(self.flash_part)
        # Статус JTAG
        jtag_layout = QHBoxLayout()
        self.jtag_status = Pill("Не обнаружен", "off")
        self.connect_btn = QPushButton("Подключиться к JTAG")
        role(self.connect_btn, "ghost")
        self.connect_btn.clicked.connect(self.check_jtag)
        jtag_layout.addWidget(QLabel("Программатор:"))
        jtag_layout.addWidget(self.jtag_status)
        jtag_layout.addWidget(self.connect_btn)
        # .mcs файл
        mcs_layout = QHBoxLayout()
        self.mcs_combo = QComboBox()
        self.mcs_dir = data_path('mcs')
        os.makedirs(self.mcs_dir, exist_ok=True)
        self.refresh_mcs_list()
        refresh_btn = QPushButton("Обновить")
        role(refresh_btn, "ghost")
        refresh_btn.clicked.connect(self.refresh_mcs_list)
        mcs_layout.addWidget(QLabel(".mcs файл:"))
        mcs_layout.addWidget(self.mcs_combo)
        mcs_layout.addWidget(refresh_btn)
        # Кнопки для прошивки и очистки
        buttons_layout = QHBoxLayout()
        self.flash_btn = QPushButton("Прошить Xilinx Config Memory")
        glow(self.flash_btn, THEME.g1, 22, 90)
        self.flash_btn.clicked.connect(self.start_xilinx_flash)
        self.flash_btn.setEnabled(False)
        buttons_layout.addWidget(self.flash_btn)
        self.erase_btn = QPushButton("Очистить Xilinx Config Memory")
        role(self.erase_btn, "danger")
        self.erase_btn.clicked.connect(self.start_xilinx_erase)
        self.erase_btn.setEnabled(False)
        buttons_layout.addWidget(self.erase_btn)
        # Прогресс бар
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        # Таймер
        self.timer_label = QLabel("Время операции: 00:00")
        self.timer_label.setVisible(False)
        # Лог
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(group("Программатор", cli_path_layout,
                               flash_part_layout, jtag_layout))
        layout.addWidget(group("Прошивка", mcs_layout, buttons_layout,
                               self.progress_bar, self.timer_label))
        layout.addWidget(group("Журнал", self.log), 1)
        self.setLayout(layout)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.elapsed_time = 0

    def update_timer(self):
        self.elapsed_time += 1
        minutes = self.elapsed_time // 60
        seconds = self.elapsed_time % 60
        self.timer_label.setText(f"Время операции: {minutes:02}:{seconds:02}")

    def browse_cli(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать CLI", "", "Batch files (*.bat);;Executables (*.exe)")
        if file_name:
            self.cli_path.setText(file_name)
            self.save_cli_path(file_name)

    def search_cli(self):
        self.cli_path.setText("")
        self.search_thread = tools.SearchThread(find_xilinx_cli, self)
        self.search_thread.found.connect(self.on_search_finished)
        self.progress_dialog = QProgressDialog("Поиск CLI... Это может занять время.", "Отмена", 0, 0, self)
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
            if path:
                self.progress_dialog.setLabelText(f"CLI найден: {path}")
                self.cli_path.setText(path)
                self.save_cli_path(path)
            else:
                self.progress_dialog.setLabelText("CLI не найден.")
            self.progress_dialog.setCancelButtonText("Ok")
            self.progress_dialog.canceled.disconnect(self.on_search_canceled)
            self.progress_dialog.canceled.connect(self.progress_dialog.close)

    def on_search_canceled(self):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.requestInterruption()

    def save_cli_path(self, path):
        tools.save_setting('xilinx_cli_path', path)

    def load_cli_path(self):
        path = tools.get_setting('xilinx_cli_path')
        self.cli_path.setText(path if path and os.path.exists(path) else '')

    def refresh_mcs_list(self):
        self.mcs_combo.clear()
        if os.path.exists(self.mcs_dir):
            for f in os.listdir(self.mcs_dir):
                if f.lower().endswith('.mcs'):
                    self.mcs_combo.addItem(f)

    def get_cmd(self, cli_path, tcl_path):
        base_name = os.path.basename(cli_path).lower()
        if 'vivado' in base_name:
            return [cli_path, '-mode', 'batch', '-nolog', '-nojournal', '-source', tcl_path]
        else:
            return [cli_path, tcl_path]

    def is_vivado_cli(self, cli_path):
        return 'vivado' in os.path.basename(cli_path).lower()

    def filter_output(self, output):
        lines = output.split('\n')
        filtered_lines = []
        skip_webtalk = False
        for line in lines:
            if line.strip().startswith('#'):
                continue
            if "Webtalk" in line or "webtalk" in line.lower():
                skip_webtalk = True
                continue
            if skip_webtalk:
                if "Exiting Webtalk" in line:
                    skip_webtalk = False
                continue
            if "vivado.log" in line or ".jou" in line or ".Xil" in line or "Vivado-" in line:
                continue
            filtered_lines.append(line)
        return '\n'.join(filtered_lines)

    def check_jtag(self):
        """Опрос JTAG занимает до минуты, поэтому идёт в фоне —
        иначе всё это время окно висит «Не отвечает»."""
        cli_path = self.cli_path.text()
        if not cli_path:
            QMessageBox.warning(self, "Ошибка", "Укажите путь к CLI!")
            return
        if not os.path.exists(cli_path):
            self.log.append(f"CLI файл не найден: {cli_path}")
            return

        if self.is_vivado_cli(cli_path):
            tcl_script = """
open_hw_manager
connect_hw_server -url TCP:localhost:3121 -allow_non_jtag
set targets [get_hw_targets]
if {[llength $targets] > 0} {
    puts "Targets found: $targets"
    set target [lindex $targets 0]
    open_hw_target $target
    set devices [get_hw_devices]
    if {[llength $devices] > 0} {
        puts "Devices found: $devices"
    } else {
        puts "No devices found"
    }
    close_hw_target
} else {
    puts "No targets found"
}
close_hw_manager
exit
"""
        else:
            tcl_script = """
set url "TCP:localhost:3121"
connect -url $url
targets
exit
"""
        tcl_path = tools.temp_script(tcl_script, '.tcl')
        cmd = self.get_cmd(cli_path, tcl_path)
        self.log.append(f"Выполнение команды: {' '.join(cmd)}")
        self.connect_btn.setEnabled(False)
        self.jtag_status.set_state("move", "Опрос…")
        self.check_thread = tools.CommandThread(cmd, timeout=60, parent=self)
        self.check_thread.done.connect(
            lambda code, out, t=tcl_path: self._on_jtag_checked(code, out, t))
        self.check_thread.failed.connect(
            lambda msg, t=tcl_path: self._on_jtag_check_failed(msg, t))
        self.check_thread.start()

    def _set_jtag_found(self, found):
        self.flash_btn.setEnabled(found)
        self.erase_btn.setEnabled(found)

    def _on_jtag_checked(self, code, out, tcl_path):
        tools.drop_temp(tcl_path)
        self.connect_btn.setEnabled(True)
        filtered = self.filter_output(out)
        self.log.append(filtered)
        if code != 0:
            self.log.append(f"Ошибка выполнения: код {code}")
            self.jtag_status.set_state("err", "Не найден")
            self._set_jtag_found(False)
            return
        low = filtered.lower()
        if "error" in low or "no targets found" in low or "no devices found" in low or "unable to connect" in low:
            self.jtag_status.set_state("err", "Не найден")
            self._set_jtag_found(False)
            self.log.append("Проверьте: 1) Подключен ли JTAG-кабель? 2) Установлены ли драйверы? 3) Запитана ли плата? 4) Нет ли ошибок в Device Manager? 5) Убейте все процессы hw_server.exe в Диспетчере задач и попробуйте снова.")
        elif ("targets found" in low or "connect successful" in low or "devices found" in low) and ("xc" in low or "jtag" in low or "fpga" in low or "digilent" in low or "xilinx_tcf" in low or "xc7s25" in low):
            self.jtag_status.set_state("on", "Подключен")
            self._set_jtag_found(True)
        else:
            self.jtag_status.set_state("err", "Не найден")
            self._set_jtag_found(False)
            self.log.append("Неизвестный статус. Проверьте вывод.")

    def _on_jtag_check_failed(self, msg, tcl_path):
        tools.drop_temp(tcl_path)
        self.connect_btn.setEnabled(True)
        self.jtag_status.set_state("err", "Не найден")
        self._set_jtag_found(False)
        self.log.append(f"Ошибка: {msg}")

    def start_xilinx_flash(self):
        if self.mcs_combo.count() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет .mcs файлов!")
            return
        mcs_path = os.path.join(self.mcs_dir, self.mcs_combo.currentText())
        cli_path = self.cli_path.text()
        flash_part = self.flash_part.text().strip()
        if not flash_part:
            QMessageBox.warning(self, "Ошибка", "Укажите тип Config Memory!")
            return
        self.log.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.timer_label.setText("Время операции: 00:00")
        self.timer_label.setVisible(True)
        self.elapsed_time = 0
        self.timer.start(1000)
        self.flash_btn.setEnabled(False)
        self.erase_btn.setEnabled(False)
        self.thread = XilinxFlashThread(mcs_path, cli_path, flash_part, erase_only=False)
        self.thread.log.connect(self.log.append)
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.done.connect(self.on_operation_finished)
        self.thread.start()

    def start_xilinx_erase(self):
        if QMessageBox.question(
                self, "Очистить Config Memory",
                "Стереть Configuration Memory ПЛИС?\n\n"
                "Образ в памяти будет потерян, после стирания плата не\n"
                "загрузится, пока не записать .mcs заново.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        if self.mcs_combo.count() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет .mcs файлов! Выберите .mcs для определения размера (не будет прошит).")
            return
        mcs_path = os.path.join(self.mcs_dir, self.mcs_combo.currentText())
        cli_path = self.cli_path.text()
        flash_part = self.flash_part.text().strip()
        if not flash_part:
            QMessageBox.warning(self, "Ошибка", "Укажите тип Config Memory!")
            return
        self.log.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.timer_label.setText("Время операции: 00:00")
        self.timer_label.setVisible(True)
        self.elapsed_time = 0
        self.timer.start(1000)
        self.flash_btn.setEnabled(False)
        self.erase_btn.setEnabled(False)
        self.thread = XilinxFlashThread(mcs_path, cli_path, flash_part, erase_only=True)
        self.thread.log.connect(self.log.append)
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.done.connect(self.on_operation_finished)
        self.thread.start()

    def on_operation_finished(self, success):
        self.timer.stop()
        self.flash_btn.setEnabled(True)
        self.erase_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.timer_label.setVisible(False)
        if success:
            QMessageBox.information(self, "Успех", f"Операция завершена! Время: {self.elapsed_time // 60:02}:{self.elapsed_time % 60:02}")
        else:
            QMessageBox.warning(self, "Ошибка", "Операция не удалась!")