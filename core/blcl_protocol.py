from PyQt5.QtCore import QThread, pyqtSignal
import time
import os
from utils.helpers import create_blcl_packet

class FlashThread(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool)

    def __init__(self, ser, files_info, verbose=False, try_cmd=0x7F, clear_buffer=True):
        super().__init__()
        self.ser = ser
        self.files_info = files_info
        self.chunk_size = 1024
        self.timeout = 10.0
        self.verbose = verbose  # Флаг детального лога
        self.try_cmd = try_cmd
        self.clear_buffer = clear_buffer

    def run(self):
        try:
            if self.clear_buffer:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            self.log.emit("Используется существующий открытый порт для прошивки")

            try_pkt = create_blcl_packet(self.try_cmd)
            device_type = "FPGA" if self.try_cmd == 0x7F else "MCU"
            self.log.emit(f"Ожидание запроса TryConnection от {device_type}: {' '.join(f'{b:02X}' for b in try_pkt)}")
            buffer = b''
            start_time = time.time()
            while True:
                if time.time() - start_time > 30:
                    self.log.emit("Таймаут: запрос TryConnection не получен за 30 секунд")
                    self.finished.emit(False)
                    return

                byte = self.ser.read(1)
                if byte:
                    buffer += byte
                    if self.verbose:
                        self.log.emit(f"Получен байт: {byte[0]:02X} | Буфер: {' '.join(f'{b:02X}' for b in buffer)}")

                if len(buffer) >= len(try_pkt):
                    if buffer[-len(try_pkt):] == try_pkt:
                        self.log.emit("Получен полный запрос TryConnection: " + ' '.join(f'{b:02X}' for b in try_pkt))
                        self.ser.write(try_pkt)
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
                self.ser.write(write_addr)
                if self.verbose:
                    self.log.emit("Запрос: " + ' '.join(f'{b:02X}' for b in write_addr))
                response = self.ser.read(8)
                if self.verbose:
                    self.log.emit("Ответ: " + ' '.join(f'{b:02X}' for b in response))
                if len(response) != 8 or response[0] != 0xAA or response[2] & 0x80:
                    self.log.emit("Ошибка: Ответ WriteAddress!")
                    self.finished.emit(False)
                    return

                self.log.emit("Успех: Получен ответ WriteAddress")

                # WriteData chunks
                for j in range(0, size, self.chunk_size):
                    chunk = bin_data[j:j+self.chunk_size]
                    write_data = create_blcl_packet(0x03, chunk)
                    self.ser.write(write_data)
                    if self.verbose:
                        self.log.emit("Запрос: " + ' '.join(f'{b:02X}' for b in write_data))
                    response = self.ser.read(8)
                    if self.verbose:
                        self.log.emit("Ответ: " + ' '.join(f'{b:02X}' for b in response))
                    if len(response) != 8 or response[0] != 0xAA or response[2] & 0x80:
                        self.log.emit("Ошибка: Ответ WriteData!")
                        self.finished.emit(False)
                        return

                    self.log.emit("Успех: Получен ответ WriteData")
                    current_chunk += 1
                    self.progress.emit(int((current_chunk / total_chunks) * 100))

            # Final TryConnection
            self.ser.write(try_pkt)
            if self.verbose:
                self.log.emit("Запрос: " + ' '.join(f'{b:02X}' for b in try_pkt))
            response = self.ser.read(32)
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