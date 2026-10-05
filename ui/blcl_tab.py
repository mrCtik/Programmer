# ui/blcl_tab.py
# Вкладка для загрузки по BLCL

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QCheckBox, QProgressBar, QFileDialog, QSplitter, QMessageBox, QGroupBox
from PyQt5.QtCore import Qt
from core.blcl_protocol import FlashThread
from utils import tools
from utils.helpers import calc_crc, create_blcl_packet, data_path
from ui.kit.glass import glow
from ui.styles import THEME, group, role
import os
import re
import time
import struct

class BlclTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent  # Ссылка на MainWindow
        self.firmware_dir = data_path('firmware')
        self._known_files = []
        self.file_fields = []
        self.file_exts = []
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
            ("FPGA Bitstream 1 (.bit)", "0x00000", ".bit"),
            ("FPGA Bitstream 2 (.bit)", "0x40000", ".bit"),
            ("MCU Firmware (.bin)", "0x80000", ".bin")  # <-- Старый default, обновим при смене режима
        ]
        for label, default_addr, extension in files:
            self.add_file_row(left, label, default_addr, extension)

        self.refresh_fw_btn = QPushButton("Обновить список прошивок")
        role(self.refresh_fw_btn, "ghost")
        self.refresh_fw_btn.clicked.connect(self.refresh_firmware_lists)
        left.addWidget(self.refresh_fw_btn)

        self.status_label = QLabel("config_file.bin → 0x100000 (будет создан только для FPGA если нужно)")
        role(self.status_label, "dim")
        left.addWidget(self.status_label)

        # Чекбокс для детального лога
        self.verbose_log_chk = QCheckBox("Детальный лог (все посылки)")
        self.verbose_log_chk.setChecked(False)
        left.addWidget(self.verbose_log_chk)

        self.flash_btn = QPushButton("Flash via COM Port")
        glow(self.flash_btn, THEME.g1, 22, 90)
        self.flash_btn.clicked.connect(self.start_flash)
        left.addWidget(self.flash_btn)

        self.progress = QProgressBar()
        left.addWidget(self.progress)

        self.save_log_btn = QPushButton("Save Log to TXT")
        role(self.save_log_btn, "ghost")
        self.save_log_btn.clicked.connect(self.save_log)
        left.addWidget(self.save_log_btn)

        left.addStretch()

        # Правая панель — лог
        right = QVBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right)
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.clear_log_btn = QPushButton("Clear Log")
        role(self.clear_log_btn, "ghost")
        self.clear_log_btn.clicked.connect(self.log.clear)

        right.addWidget(group("Журнал", self.log, self.clear_log_btn))

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([750, 500])
        layout.addWidget(splitter)
        self.setLayout(layout)

        # Инициализируем начальную команду и адрес
        self.update_mcu_address()  # <-- НОВОЕ: начальное обновление адреса
        self.log_expected_command()

        # Подключаем сигнал для MCU комбо
        self.file_fields[2].currentTextChanged.connect(self.update_version_from_file)

        # запоминаем исходный состав папки тем же способом, которым
        # он потом сверяется, иначе первое же срабатывание сторожа
        # напишет в журнал «обновлён» на ровном месте
        self.refresh_firmware_lists(announce=False)
        self.fw_watcher = tools.FolderWatcher(
            self.firmware_dir, self.refresh_firmware_lists, parent=self)

    def update_mcu_address(self):
        """НОВОЕ: Обновление default-адреса MCU при смене режима"""
        mode_text = self.mode_combo.currentText()
        try_cmd = int(mode_text.split('(')[1].split(')')[0], 16)
        mcu_addr_field = self.addr_fields[2]  # Поле адреса для MCU (индекс 2)
        if try_cmd == 0x7E:  # MCU-режим
            mcu_addr_field.setText("0x8000")  # Offset для app после бутлоадера
            self.log.append("MCU-режим: Адрес MCU изменён на 0x8000 (offset для STM32 app)")
            self.checkboxes[0].setChecked(False)
            self.checkboxes[1].setChecked(False)
            self.checkboxes[2].setChecked(True)
        else:  # FPGA-режим
            mcu_addr_field.setText("0x80000")  # Старый default для совместимости
            self.log.append("FPGA-режим: Адрес MCU восстановлен на 0x80000")
            self.checkboxes[0].setChecked(True)
            self.checkboxes[1].setChecked(True)
            self.checkboxes[2].setChecked(True)

    def log_expected_command(self):
        mode_text = self.mode_combo.currentText()
        try_cmd = int(mode_text.split('(')[1].split(')')[0], 16)
        try_pkt = create_blcl_packet(try_cmd)
        device_type = "FPGA" if try_cmd == 0x7F else "MCU"
        self.log.append(f"Ожидаемая команда TryConnection для {device_type}: {' '.join(f'{b:02X}' for b in try_pkt)}")

    def _fill_file_combo(self, field, extension):
        """Перечитывает папку firmware, сохраняя текущий выбор, если файл на месте."""
        return tools.fill_combo(field, self.firmware_dir, (extension,),
                                empty_first=True)

    def refresh_firmware_lists(self, announce=True):
        """Обновляет выпадающие списки прошивок — перезапуск не нужен ни
        после новой сборки, ни когда файл положили в папку при открытой
        программе."""
        found = []
        for field, ext in zip(self.file_fields, self.file_exts):
            found += self._fill_file_combo(field, ext)
        if announce and found != self._known_files:
            self.log.append(
                f"Список прошивок обновлён ({self.firmware_dir}): "
                f"найдено файлов — {len(found)}")
        self._known_files = found

    def add_file_row(self, layout, label_text, default_addr, extension):
        group = QGroupBox(label_text)
        vbox = QVBoxLayout()

        h1 = QHBoxLayout()
        field = QComboBox()
        self._fill_file_combo(field, extension)
        h1.addWidget(field)
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
        self.file_exts.append(extension)
        self.addr_fields.append(addr_field)
        self.checkboxes.append(chk)

    def update_version_from_file(self, text):
        if text:
            match = re.search(r'V(\d+\.\d+)', text)
            if match:
                version = match.group(1)
                version_panel = self.main_window.version_panel
                version_panel.version_input.setText(f"V{version}")

    def browse(self, field):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл", "", "Binaries (*.bin *.bit)")
        if path:
            field.setText(path)

    def start_flash(self):
        version_panel = self.main_window.version_panel
        if not version_panel.is_com_connected or not version_panel.serial_port:
            QMessageBox.warning(self, "Ошибка", "Сначала подключитесь к COM-порту в правой панели!")
            return

        ser = version_panel.serial_port
        current_text = version_panel.com_combo.currentText()
        baud = int(version_panel.baud_combo.currentText())
        if baud != 115200:
            reply = QMessageBox.question(self, "Предупреждение", f"BLCL требует 115200 baud, но выбран {baud}. Продолжить?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        verbose = self.verbose_log_chk.isChecked()

        # Получаем try_cmd из комбо
        mode_text = self.mode_combo.currentText()
        try_cmd = int(mode_text.split('(')[1].split(')')[0], 16)

        paths = [os.path.join(self.firmware_dir, self.file_fields[i].currentText()) if self.file_fields[i].currentText() else '' for i in range(3)]
        addrs = [int(self.addr_fields[i].text(), 16) for i in range(3)]
        selected = [self.checkboxes[i].isChecked() for i in range(3)]

        files_info = []

        if try_cmd == 0x7E:  # MCU-режим: только MCU, без config/FPGA
            if selected[2] and paths[2] and os.path.exists(paths[2]):
                with open(paths[2], 'rb') as f:
                    data = f.read()
                crc = calc_crc(data)
                prog_data = data + crc.to_bytes(4, 'little')
                prog_dir = data_path('files')
                os.makedirs(prog_dir, exist_ok=True)
                prog_path = os.path.join(prog_dir, "mcu_prog.bin")
                with open(prog_path, 'wb') as f:
                    f.write(prog_data)
                files_info.append((prog_path, addrs[2]))
            if selected[0] or selected[1]:
                self.log.append("Предупреждение: В MCU-режиме игнорируем FPGA-файлы. Config не создаётся.")
        else:  # FPGA-режим
            # Собираем записи для config (всегда 3, с size=0 для не выбранных)
            config_entries = []
            for i in range(3):
                path = paths[i]
                addr = addrs[i]
                if selected[i] and path and os.path.exists(path):
                    if i == 2:  # MCU: size без CRC
                        with open(path, 'rb') as f:
                            data = f.read()
                        size = len(data)
                    else:  # FPGA
                        size = os.path.getsize(path)
                else:
                    size = 0
                config_entries.append((addr, size))

            num_nonzero = sum(size > 0 for _, size in config_entries)

            if num_nonzero > 1:
                config_bin = bytearray()
                for addr, size in config_entries:
                    config_bin += addr.to_bytes(4, 'little') + size.to_bytes(4, 'little')
                crc = calc_crc(config_bin)
                config_bin += crc.to_bytes(4, 'little')
                self.log.append("Config file HEX: " + ' '.join(f'{b:02X}' for b in config_bin))
                config_dir = data_path('files')
                os.makedirs(config_dir, exist_ok=True)
                config_path = os.path.join(config_dir, "config_file.bin")
                with open(config_path, 'wb') as f:
                    f.write(config_bin)
                files_info.append((config_path, 0x100000))

            # Добавляем выбранные файлы для прошивки (MCU с +CRC)
            for i in range(3):
                path = paths[i]
                addr = addrs[i]
                if selected[i] and path and os.path.exists(path):
                    if i == 2:  # MCU
                        with open(path, 'rb') as f:
                            data = f.read()
                        crc = calc_crc(data)
                        prog_data = data + crc.to_bytes(4, 'little')
                        prog_dir = data_path('files')
                        os.makedirs(prog_dir, exist_ok=True)
                        prog_path = os.path.join(prog_dir, "mcu_prog.bin")
                        with open(prog_path, 'wb') as f:
                            f.write(prog_data)
                        files_info.append((prog_path, addr))
                    else:  # FPGA
                        files_info.append((path, addr))

        if not files_info:
            QMessageBox.warning(self, "Ошибка", "Нет файлов для загрузки!")
            return

        # Перед прошивкой обновляем версию и дату (для MCU-режима)
        if try_cmd == 0x7E:
            reply = QMessageBox.information(self, "Инструкция", "Перезапустите устройство (STM32) сейчас, и нажмите OK для обновления версии/даты и начала прошивки.")
            if reply != QMessageBox.Ok:
                return

            # Ждем "Bootloader started"
            self.log.append("Ожидание Bootloader started...")
            buffer = bytearray()
            start_time = time.time()
            bootloader_started = False
            while time.time() - start_time < 10 and not bootloader_started:
                bytes_read = ser.read(1024)
                if bytes_read:
                    buffer.extend(bytes_read)
                    buffer_str = buffer.decode('utf-8', errors='ignore')
                    if "Bootloader started" in buffer_str:
                        bootloader_started = True
                        self.log.append("Получено Bootloader started")

            if not bootloader_started:
                self.log.append("Ошибка: Не получено Bootloader started")
                return

            # Обновляем версию и дату
            version = version_panel.version_input.text().strip()
            date = version_panel.date_input.text().strip()
            if version and date:
                self.log.append(f"Обновление версии: {version}, даты: {date}")
                data = version.encode('utf-8') + b'\x00' + date.encode('utf-8') + b'\x00'
                data_len = len(data)
                if data_len > 1024:
                    self.log.append("Ошибка: Длина данных превышает 1024")
                    return

                packet_mid = bytearray([data_len & 0xFF, (data_len >> 8) & 0x7F, 0x05]) + data
                crc = calc_crc(packet_mid)
                packet = bytearray([0xAA]) + packet_mid + struct.pack('<I', crc)

                ser.write(packet)
                self.log.append("Отправлен пакет SetFirmwareInfo")

                # Ждем ACK
                ack_buffer = bytearray()
                start_time = time.time()
                ack_received = False
                while time.time() - start_time < 5 and not ack_received:
                    bytes_read = ser.read(8)
                    if bytes_read:
                        ack_buffer.extend(bytes_read)
                        if len(ack_buffer) >= 8 and ack_buffer[0] == 0xAA:
                            len_low = ack_buffer[1]
                            len_high = ack_buffer[2]
                            cmd = ack_buffer[3]
                            if len_low == 0 and (len_high & 0x7F) == 0 and cmd == 0x05:
                                error = 1 if (len_high & 0x80) else 0
                                crc_received = struct.unpack('<I', ack_buffer[4:8])[0]
                                crc_calc = calc_crc(ack_buffer[1:4])
                                if crc_calc == crc_received:
                                    if error == 0:
                                        self.log.append("Получен ACK: Версия/дата обновлены")
                                        ack_received = True
                                    else:
                                        self.log.append("Получен NACK: Ошибка обновления")
                                        return

                if not ack_received:
                    self.log.append("Ошибка: Не получен ACK на SetFirmwareInfo")
                    return

                time.sleep(0.2)  # Небольшая задержка для получения TryConnection

        self.log.append(f"Прошивка {len(files_info)} файлов... Используется порт: {current_text.split(' - ')[0]} на {baud} baud")
        self.progress.setValue(0)
        self.flash_thread = FlashThread(ser, files_info, verbose, try_cmd, clear_buffer=(try_cmd != 0x7E))
        self.flash_thread.log.connect(self.log.append)
        self.flash_thread.progress.connect(self.progress.setValue)
        self.flash_thread.done.connect(self.on_flash_finished)
        self._lock_port(True)
        self.flash_thread.start()

    def _lock_port(self, busy):
        """Порт один на всю программу: пока в него пишет поток прошивки,
        панель версии не должна из него читать — иначе ответы платы
        достанутся не тому, кто их ждёт."""
        self.flash_btn.setEnabled(not busy)
        panel = getattr(self.main_window, 'version_panel', None)
        if not panel:
            return
        buttons = (panel.connect_btn, panel.update_info_btn,
                   panel.set_info_btn)
        if busy:
            self._saved_states = [b.isEnabled() for b in buttons]
            for b in buttons:
                b.setEnabled(False)
        else:
            saved = getattr(self, '_saved_states', [True] * len(buttons))
            for b, state in zip(buttons, saved):
                b.setEnabled(state)

    def on_flash_finished(self, success):
        self._lock_port(False)
        if success:
            self.log.append("Загрузка завершена успешно!")
        else:
            self.log.append("Загрузка прервана с ошибкой!")

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить лог", "", "Text (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.log.toPlainText())
            self.log.append("Лог сохранён!")