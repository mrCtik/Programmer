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
        left.addLayout(com_row)

        # Файлы
        files = [
            ("FPGA Bitstream 1 (.bit)", "0x00000"),
            ("FPGA Bitstream 2 (.bit)", "0x40000"),
            ("MCU Firmware (.bin)",     "0x80000")
        ]
        for label, default_addr in files:
            self.add_file_row(left, label, default_addr)

        self.status_label = QLabel("config_file.bin → 0x100000 (будет создан)")
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
        splitter.setSizes([650, 500])
        layout.addWidget(splitter)
        self.setLayout(layout)

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
            self.com_combo.addItem(p.device)

    def start_flash(self):
        port = self.com_combo.currentText()
        baud = int(self.baud_combo.currentText())
        if not port:
            QMessageBox.warning(self, "Ошибка", "Выберите COM порт!")
            return

        verbose = self.verbose_log_chk.isChecked()  # Получаем состояние чекбокса

        files_info = []
        selected = [self.checkboxes[i].isChecked() for i in range(3)]

        # MCU
        mcu_path = self.file_fields[2].text()
        if selected[2] and mcu_path and os.path.exists(mcu_path):
            with open(mcu_path, 'rb') as f:
                mcu_data = f.read()
            crc = calc_crc(mcu_data)
            mcu_prog_bin = mcu_data + crc.to_bytes(4, 'little')
            mcu_prog_dir = os.path.join(os.path.dirname(__file__), 'files')
            os.makedirs(mcu_prog_dir, exist_ok=True)  # Создаём папку 'files' если не существует
            mcu_prog_path = os.path.join(mcu_prog_dir, "mcu_prog.bin")
            with open(mcu_prog_path, 'wb') as f:
                f.write(mcu_prog_bin)
            files_info.append((mcu_prog_path, int(self.addr_fields[2].text(), 16)))

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

        num_selected = sum(selected)
        if num_selected > 1:
            config_bin = self.generate_config_file()
            config_dir = os.path.join(os.path.dirname(__file__), 'files')
            os.makedirs(config_dir, exist_ok=True)  # Создаём папку 'files' если не существует
            config_path = os.path.join(config_dir, "config_file.bin")
            with open(config_path, 'wb') as f:
                f.write(config_bin)
            files_info = [(config_path, 0x100000)] + files_info  # config всегда 0x100000

        if not files_info:
            QMessageBox.warning(self, "Ошибка", "Нет файлов для загрузки!")
            return

        self.log.append(f"Прошивка {len(files_info)} файлов...")
        self.progress.setValue(0)
        self.flash_thread = FlashThread(port, baud, files_info, verbose)  # Передаём verbose в поток
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

# core/blcl_protocol.py
from PyQt5.QtCore import QThread, pyqtSignal
import serial
import time
import os
from utils.helpers import create_blcl_packet

class FlashThread(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool)

    def __init__(self, port, baud, files_info, verbose=False):
        super().__init__()
        self.port = port
        self.baud = baud
        self.files_info = files_info
        self.chunk_size = 1024
        self.timeout = 1.0
        self.verbose = verbose  # Флаг детального лога

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            self.log.emit(f"Подключено к {self.port} на {self.baud} baud")

            try_pkt = create_blcl_packet(0x7F)
            self.log.emit("Ожидание запроса TryConnection от MCU...")
            buffer = b''
            start_time = time.time()
            while True:
                if time.time() - start_time > 30:
                    self.log.emit("Таймаут: запрос TryConnection не получен за 30 секунд")
                    self.finished.emit(False)
                    return

                byte = ser.read(1)
                if byte:
                    buffer += byte
                    if self.verbose:
                        self.log.emit(f"Получен байт: {byte[0]:02X} | Буфер: {' '.join(f'{b:02X}' for b in buffer)}")

                if len(buffer) >= len(try_pkt):
                    if buffer[-len(try_pkt):] == try_pkt:
                        self.log.emit("Получен полный запрос TryConnection: " + ' '.join(f'{b:02X}' for b in try_pkt))
                        ser.write(try_pkt)
                        self.log.emit("Отправлен ответ TryConnection: " + ' '.join(f'{b:02X}' for b in try_pkt))
                        break
                    else:
                        buffer = buffer[1:]

            total_chunks = sum((os.path.getsize(p) + self.chunk_size - 1) // self.chunk_size
                               for p, _ in self.files_info if p and os.path.exists(p))

            current_chunk = 0

            for path, addr in self.files_info:
                if not path or not os.path.exists(path):
                    continue

                with open(path, 'rb') as f:
                    bin_data = f.read()

                size = len(bin_data)
                if size == 0:
                    continue

                addr_bytes = addr.to_bytes(4, 'little')
                size_bytes = size.to_bytes(4, 'little')
                write_addr = create_blcl_packet(0x01, addr_bytes + size_bytes)
                ser.write(write_addr)
                if self.verbose:
                    self.log.emit("Запрос: " + ' '.join(f'{b:02X}' for b in write_addr))
                response = ser.read(8)
                if self.verbose:
                    self.log.emit("Ответ: " + ' '.join(f'{b:02X}' for b in response))
                if len(response) != 8 or response[0] != 0xAA or response[3] & 0x80:
                    self.log.emit("Ошибка: Ответ WriteAddress!")
                    self.finished.emit(False)
                    return

                self.log.emit("Успех: Получен ответ WriteAddress")

                # WriteData chunks
                for j in range(0, size, self.chunk_size):
                    chunk = bin_data[j:j+self.chunk_size]
                    write_data = create_blcl_packet(0x03, chunk)
                    ser.write(write_data)
                    if self.verbose:
                        self.log.emit("Запрос: " + ' '.join(f'{b:02X}' for b in write_data))
                    response = ser.read(8)
                    if self.verbose:
                        self.log.emit("Ответ: " + ' '.join(f'{b:02X}' for b in response))
                    if len(response) != 8 or response[0] != 0xAA or response[3] & 0x80:
                        self.log.emit("Ошибка: Ответ WriteData!")
                        self.finished.emit(False)
                        return

                    self.log.emit("Успех: Получен ответ WriteData")
                    current_chunk += 1
                    self.progress.emit(int((current_chunk / total_chunks) * 100))

            # Final TryConnection
            ser.write(try_pkt)
            if self.verbose:
                self.log.emit("Запрос: " + ' '.join(f'{b:02X}' for b in try_pkt))
            response = ser.read(32)
            if self.verbose:
                self.log.emit("Ответ: " + ' '.join(f'{b:02X}' for b in response))
            if b'Start User App \r\n' in response:
                self.log.emit("Получен Start User App")
            else:
                self.log.emit("Ошибка: Не получен Start User App")
                self.finished.emit(False)
                return

            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {e}")
            self.finished.emit(False)