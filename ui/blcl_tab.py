# ui/blcl_tab.py
# Вкладка для загрузки по BLCL

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QCheckBox, QProgressBar, QFileDialog, QSplitter, QMessageBox, QGroupBox
from PyQt5.QtCore import Qt
from core.blcl_protocol import FlashThread
from utils.helpers import calc_crc, create_blcl_packet
import os

class BlclTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_fields = []
        self.addr_fields = []
        self.checkboxes = []
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        splitter = QSplitter(Qt.Horizontal)

        # Левая панель
        left = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left)

        # Настройки COM
        com_row = QHBoxLayout()
        com_row.addWidget(QLabel("COM Port:"))
        self.com_combo = QComboBox()
        self.refresh_ports()
        com_row.addWidget(self.com_combo)
        com_row.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200"])
        self.baud_combo.setCurrentText("115200")
        com_row.addWidget(self.baud_combo)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_ports)
        com_row.addWidget(refresh_btn)
        left.addLayout(com_row)

        # Выбор режима прошивки
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Режим прошивки:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["FPGA (0x7F)", "MCU (0x7E)"])
        self.mode_combo.currentIndexChanged.connect(self.update_mcu_address)  # <-- НОВОЕ: сигнал для обновления адреса MCU
        self.mode_combo.currentIndexChanged.connect(self.log_expected_command)
        mode_row.addWidget(self.mode_combo)
        left.addLayout(mode_row)

        # Файлы (default адреса статические, но MCU обновим динамически)
        files = [
            ("FPGA Bitstream 1 (.bit)", "0x00000"),
            ("FPGA Bitstream 2 (.bit)", "0x40000"),
            ("MCU Firmware (.bin)", "0x80000")  # <-- Старый default, обновим при смене режима
        ]
        for label, default_addr in files:
            self.add_file_row(left, label, default_addr)

        self.status_label = QLabel("config_file.bin → 0x100000 (будет создан только для FPGA если нужно)")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        left.addWidget(self.status_label)

        # Чекбокс для детального лога
        self.verbose_log_chk = QCheckBox("Детальный лог (все посылки)")
        self.verbose_log_chk.setChecked(False)
        left.addWidget(self.verbose_log_chk)

        self.flash_btn = QPushButton("Flash via COM Port")
        self.flash_btn.clicked.connect(self.start_flash)
        left.addWidget(self.flash_btn)

        self.progress = QProgressBar()
        left.addWidget(self.progress)

        self.save_log_btn = QPushButton("Save Log to TXT")
        self.save_log_btn.clicked.connect(self.save_log)
        left.addWidget(self.save_log_btn)

        left.addStretch()

        # Правая панель — лог
        right = QVBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        right.addWidget(self.log)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([750, 500])
        layout.addWidget(splitter)
        self.setLayout(layout)

        # Инициализируем начальную команду и адрес
        self.update_mcu_address()  # <-- НОВОЕ: начальное обновление адреса
        self.log_expected_command()

    def update_mcu_address(self):
        """НОВОЕ: Обновление default-адреса MCU при смене режима"""
        mode_text = self.mode_combo.currentText()
        try_cmd = int(mode_text.split('(')[1].split(')')[0], 16)
        mcu_addr_field = self.addr_fields[2]  # Поле адреса для MCU (индекс 2)
        if try_cmd == 0x7E:  # MCU-режим
            mcu_addr_field.setText("0x8000")  # Offset для app после бутлоадера
            self.log.append("MCU-режим: Адрес MCU изменён на 0x8000 (offset для STM32 app)")
        else:  # FPGA-режим
            mcu_addr_field.setText("0x80000")  # Старый default для совместимости
            self.log.append("FPGA-режим: Адрес MCU восстановлен на 0x80000")

    def log_expected_command(self):
        mode_text = self.mode_combo.currentText()
        try_cmd = int(mode_text.split('(')[1].split(')')[0], 16)
        try_pkt = create_blcl_packet(try_cmd)
        device_type = "FPGA" if try_cmd == 0x7F else "MCU"
        self.log.append(f"Ожидаемая команда TryConnection для {device_type}: {' '.join(f'{b:02X}' for b in try_pkt)}")

    def add_file_row(self, layout, label_text, default_addr):
        group = QGroupBox(label_text)
        vbox = QVBoxLayout()

        h1 = QHBoxLayout()
        field = QLineEdit()
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: self.browse(field))
        h1.addWidget(field)
        h1.addWidget(btn)
        vbox.addLayout(h1)

        h2 = QHBoxLayout()
        chk = QCheckBox("Flash")
        chk.setChecked(True)
        addr_field = QLineEdit(default_addr)
        addr_field.setFixedWidth(100)
        h2.addWidget(chk)
        h2.addStretch()
        h2.addWidget(QLabel("Адрес:"))
        h2.addWidget(addr_field)
        vbox.addLayout(h2)

        group.setLayout(vbox)
        layout.addWidget(group)

        self.file_fields.append(field)
        self.addr_fields.append(addr_field)
        self.checkboxes.append(chk)

    def browse(self, field):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл", "", "Binaries (*.bin *.bit)")
        if path:
            field.setText(path)

    def refresh_ports(self):
        import serial.tools.list_ports
        self.com_combo.clear()
        for p in serial.tools.list_ports.comports():
            description = p.description
            port_suffix = f" ({p.device})"
            if description.endswith(port_suffix):
                description = description[:-len(port_suffix)]
            self.com_combo.addItem(f"{p.device} - {description}")

    def start_flash(self):
        current_text = self.com_combo.currentText()
        port = current_text.split(' - ')[0] if current_text else ''
        baud = int(self.baud_combo.currentText())
        if not port:
            QMessageBox.warning(self, "Ошибка", "Выберите COM порт!")
            return

        verbose = self.verbose_log_chk.isChecked()

        # Получаем try_cmd из комбо
        mode_text = self.mode_combo.currentText()
        try_cmd = int(mode_text.split('(')[1].split(')')[0], 16)

        selected = [self.checkboxes[i].isChecked() for i in range(3)]
        files_info = []

        if try_cmd == 0x7E:  # MCU-режим: только MCU, без config/FPGA
            mcu_path = self.file_fields[2].text()
            if selected[2] and mcu_path and os.path.exists(mcu_path):
                with open(mcu_path, 'rb') as f:
                    mcu_data = f.read()
                crc = calc_crc(mcu_data)
                mcu_prog_bin = mcu_data + crc.to_bytes(4, 'little')
                mcu_prog_dir = os.path.join(os.path.dirname(__file__), 'files')
                os.makedirs(mcu_prog_dir, exist_ok=True)
                mcu_prog_path = os.path.join(mcu_prog_dir, "mcu_prog.bin")
                with open(mcu_prog_path, 'wb') as f:
                    f.write(mcu_prog_bin)
                files_info.append((mcu_prog_path, int(self.addr_fields[2].text(), 16)))
            if selected[0] or selected[1]:
                self.log.append("Предупреждение: В MCU-режиме игнорируем FPGA-файлы. Config не создаётся.")
        else:  # FPGA-режим: FPGA1/FPGA2 + config если >1
            # FPGA2
            if selected[1]:
                fpga2_path = self.file_fields[1].text()
                if fpga2_path and os.path.exists(fpga2_path):
                    files_info.append((fpga2_path, int(self.addr_fields[1].text(), 16)))

            # FPGA1
            if selected[0]:
                fpga1_path = self.file_fields[0].text()
                if fpga1_path and os.path.exists(fpga1_path):
                    files_info.append((fpga1_path, int(self.addr_fields[0].text(), 16)))

            if selected[2]:
                self.log.append("Предупреждение: В FPGA-режиме игнорируем MCU-файл.")

            num_selected_fpga = len(files_info)
            if num_selected_fpga > 1:
                config_bin = self.generate_config_file()
                config_dir = os.path.join(os.path.dirname(__file__), 'files')
                os.makedirs(config_dir, exist_ok=True)
                config_path = os.path.join(config_dir, "config_file.bin")
                with open(config_path, 'wb') as f:
                    f.write(config_bin)
                files_info = [(config_path, 0x100000)] + files_info  # config всегда 0x100000

        if not files_info:
            QMessageBox.warning(self, "Ошибка", "Нет файлов для загрузки!")
            return

        self.log.append(f"Прошивка {len(files_info)} файлов...")
        self.progress.setValue(0)
        self.flash_thread = FlashThread(port, baud, files_info, verbose, try_cmd)
        self.flash_thread.log.connect(self.log.append)
        self.flash_thread.progress.connect(self.progress.setValue)
        self.flash_thread.finished.connect(self.on_flash_finished)
        self.flash_thread.start()

    def on_flash_finished(self, success):
        if success:
            self.log.append("Загрузка завершена успешно!")
        else:
            self.log.append("Загрузка прервана с ошибкой!")

    def generate_config_file(self):
        config_data = bytearray()
        files_info = [
            (self.file_fields[0].text(), int(self.addr_fields[0].text(), 16)),
            (self.file_fields[1].text(), int(self.addr_fields[1].text(), 16)),
            (self.file_fields[2].text(), int(self.addr_fields[2].text(), 16)),
        ]
        for path, addr in files_info:
            if not path or not os.path.exists(path):
                continue
            size = os.path.getsize(path)
            config_data += addr.to_bytes(4, 'little')
            config_data += size.to_bytes(4, 'little')
        crc = calc_crc(config_data)
        config_data += crc.to_bytes(4, 'little')
        self.log.append("Config file HEX: " + ' '.join(f'{b:02X}' for b in config_data))
        return bytes(config_data)

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить лог", "", "Text (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.log.toPlainText())
            self.log.append("Лог сохранён!")