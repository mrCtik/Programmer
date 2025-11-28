# ui/xilinx_tab.py
# Вкладка для прошивки Xilinx Configuration Memory Device через JTAG (.mcs)

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox, QProgressBar
from PyQt5.QtCore import QTimer
from core.xilinx_flash import XilinxFlashThread
import os
import subprocess
import tempfile

class XilinxTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Путь к CLI
        cli_path_layout = QHBoxLayout()
        self.cli_path_label = QLabel("Путь к CLI (vivado.bat, vivado_lab.bat или xsdb.bat):")
        self.cli_path = QLineEdit("C:/Xilinx/Vivado/2019.2/bin/vivado.bat")
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_cli)
        cli_path_layout.addWidget(self.cli_path_label)
        cli_path_layout.addWidget(self.cli_path)
        cli_path_layout.addWidget(browse_btn)
        layout.addLayout(cli_path_layout)

        # Тип Config Memory
        flash_part_layout = QHBoxLayout()
        self.flash_part_label = QLabel("Тип Config Memory (например, mx25v1635f-spi-x1_x2_x4):")
        self.flash_part = QLineEdit("mx25v1635f-spi-x1_x2_x4")
        flash_part_layout.addWidget(self.flash_part_label)
        flash_part_layout.addWidget(self.flash_part)
        layout.addLayout(flash_part_layout)

        # Путь к .bit (опционально, но рекомендуется для прошивки)
        bit_layout = QHBoxLayout()
        self.bit_label = QLabel("Путь к .bit (для очистки FPGA, опционально):")
        self.bit_path = QLineEdit("c:/PTT/fpga_4/fpga/TTP_spartan_1/TTP_spartan_1.runs/impl_1/board_top_wrapper.bit")
        browse_bit = QPushButton("Обзор...")
        browse_bit.clicked.connect(self.browse_bit)
        bit_layout.addWidget(self.bit_label)
        bit_layout.addWidget(self.bit_path)
        bit_layout.addWidget(browse_bit)
        layout.addLayout(bit_layout)

        # Статус JTAG
        jtag_layout = QHBoxLayout()
        self.jtag_status = QLabel("JTAG: Не обнаружен")
        self.jtag_status.setStyleSheet("color: red;")
        self.connect_btn = QPushButton("Проверить JTAG")
        self.connect_btn.clicked.connect(self.check_jtag)
        jtag_layout.addWidget(QLabel("Программатор:"))
        jtag_layout.addWidget(self.jtag_status)
        jtag_layout.addWidget(self.connect_btn)
        layout.addLayout(jtag_layout)

        # .mcs файл
        mcs_layout = QHBoxLayout()
        self.mcs_combo = QComboBox()
        self.mcs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcs')
        os.makedirs(self.mcs_dir, exist_ok=True)
        self.refresh_mcs_list()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_mcs_list)
        mcs_layout.addWidget(QLabel(".mcs файл:"))
        mcs_layout.addWidget(self.mcs_combo)
        mcs_layout.addWidget(refresh_btn)
        layout.addLayout(mcs_layout)

        self.flash_btn = QPushButton("Прошить Xilinx Config Memory")
        self.flash_btn.clicked.connect(self.start_xilinx_flash)
        self.flash_btn.setEnabled(False)
        layout.addWidget(self.flash_btn)

        # Прогресс бар
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Таймер
        self.timer_label = QLabel("Время прошивки: 00:00")
        self.timer_label.setVisible(False)
        layout.addWidget(self.timer_label)

        # Лог
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.elapsed_time = 0

    def update_timer(self):
        self.elapsed_time += 1
        minutes = self.elapsed_time // 60
        seconds = self.elapsed_time % 60
        self.timer_label.setText(f"Время прошивки: {minutes:02}:{seconds:02}")

    def browse_cli(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать CLI", "", "Batch files (*.bat);;Executables (*.exe)")
        if file_name:
            self.cli_path.setText(file_name)

    def browse_bit(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать .bit", "", "Bitstream (*.bit)")
        if file_name:
            self.bit_path.setText(file_name)

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
        cli_path = self.cli_path.text()
        if not cli_path:
            QMessageBox.warning(self, "Ошибка", "Укажите путь к CLI!")
            return
        if not os.path.exists(cli_path):
            self.log.append(f"CLI файл не найден: {cli_path}")
            return
        is_vivado = self.is_vivado_cli(cli_path)
        try:
            # TCL для проверки
            if is_vivado:
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

            with tempfile.NamedTemporaryFile(delete=False, suffix='.tcl', mode='w') as tcl_file:
                tcl_file.write(tcl_script)
                tcl_path = tcl_file.name

            cmd = self.get_cmd(cli_path, tcl_path)
            self.log.append(f"Выполнение команды: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            os.unlink(tcl_path)
            self.log.append(self.filter_output(result.stdout + result.stderr))

            if result.returncode != 0:
                self.log.append(f"Ошибка выполнения: код {result.returncode}")
                return

            output = result.stdout + result.stderr
            filtered_output = self.filter_output(output)
            stdout_lower = filtered_output.lower()

            if "error" in stdout_lower or "no targets found" in stdout_lower or "no devices found" in stdout_lower or "unable to connect" in stdout_lower:
                self.jtag_status.setText("JTAG: Не найден")
                self.jtag_status.setStyleSheet("color: red;")
                self.flash_btn.setEnabled(False)
                self.log.append("Проверьте: 1) Подключен ли JTAG-кабель? 2) Установлены ли драйверы? 3) Запитана ли плата? 4) Нет ли ошибок в Device Manager? 5) Убейте все процессы hw_server.exe в Диспетчере задач и попробуйте снова.")
            elif ("targets found" in stdout_lower or "connect successful" in stdout_lower or "devices found" in stdout_lower) and ("xc" in stdout_lower or "jtag" in stdout_lower or "fpga" in stdout_lower or "digilent" in stdout_lower or "xilinx_tcf" in stdout_lower or "xc7s25" in stdout_lower):
                self.jtag_status.setText("JTAG: Подключен")
                self.jtag_status.setStyleSheet("color: green;")
                self.flash_btn.setEnabled(True)
            else:
                self.jtag_status.setText("JTAG: Не найден")
                self.jtag_status.setStyleSheet("color: red;")
                self.flash_btn.setEnabled(False)
                self.log.append("Неизвестный статус. Проверьте вывод.")
        except subprocess.TimeoutExpired:
            self.log.append("Таймаут выполнения!")
        except Exception as e:
            self.log.append(f"Ошибка: {str(e)}")

    def start_xilinx_flash(self):
        if self.mcs_combo.count() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет .mcs файлов!")
            return
        mcs_path = os.path.join(self.mcs_dir, self.mcs_combo.currentText())
        cli_path = self.cli_path.text()
        flash_part = self.flash_part.text().strip()
        bit_path = self.bit_path.text()
        if not flash_part:
            QMessageBox.warning(self, "Ошибка", "Укажите тип Config Memory!")
            return
        self.log.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.timer_label.setText("Время прошивки: 00:00")
        self.timer_label.setVisible(True)
        self.elapsed_time = 0
        self.timer.start(1000)
        self.flash_btn.setEnabled(False)
        self.thread = XilinxFlashThread(mcs_path, cli_path, flash_part, bit_path)
        self.thread.log.connect(self.log.append)
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.finished.connect(lambda s: (self.timer.stop(), self.flash_btn.setEnabled(True), self.progress_bar.setVisible(False), self.timer_label.setVisible(False), QMessageBox.information(self, "Успех", f"Прошивка завершена! Время: {self.elapsed_time // 60:02}:{self.elapsed_time % 60:02}") if s else QMessageBox.warning(self, "Ошибка", "Прошивка не удалась!")))
        self.thread.start()