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

    def __init__(self, port, baud, files_info):
        super().__init__()
        self.port = port
        self.baud = baud
        self.files_info = files_info
        self.chunk_size = 1024
        self.timeout = 1.0

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            self.log.emit(f"Подключено к {self.port}")

            try_pkt = create_blcl_packet(0x7F)
            self.log.emit("Ожидание TryConnection...")
            buffer = b''
            start_time = time.time()
            while time.time() - start_time < 30:
                byte = ser.read(1)
                if byte:
                    buffer += byte
                if len(buffer) >= len(try_pkt) and buffer[-len(try_pkt):] == try_pkt:
                    self.log.emit("Получен TryConnection → отвечаем")
                    ser.write(try_pkt)
                    break
                elif len(buffer) >= len(try_pkt):
                    buffer = buffer[1:]

            total_chunks = sum((os.path.getsize(p) + self.chunk_size - 1) // self.chunk_size
                               for p, _ in self.files_info if p)

            current_chunk = 0
            for path, addr in self.files_info:
                if not path or not os.path.exists(path):
                    continue
                with open(path, 'rb') as f:
                    data = f.read()

                write_addr = create_blcl_packet(0x01, addr.to_bytes(4, 'little') + len(data).to_bytes(4, 'little'))
                ser.write(write_addr)
                ser.read(8)

                for i in range(0, len(data), self.chunk_size):
                    chunk = data[i:i+self.chunk_size]
                    ser.write(create_blcl_packet(0x03, chunk))
                    ser.read(8)
                    current_chunk += 1
                    self.progress.emit(int(current_chunk / total_chunks * 100))

            ser.write(try_pkt)
            response = ser.read(32)
            if b'Start User App' in response:
                self.log.emit("Успешно! Запущено пользовательское ПО")
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {e}")
            self.finished.emit(False)