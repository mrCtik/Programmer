from PyQt5.QtCore import QThread, pyqtSignal
import time
import os
from utils.helpers import create_blcl_packet

class FlashThread(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    # done, а не finished: QThread уже имеет свой сигнал finished(),
    # и объявление с тем же именем перекрывало его для всего класса
    done = pyqtSignal(bool)

    def __init__(self, ser, files_info, verbose=False, try_cmd=0x7F, clear_buffer=True):
        super().__init__()
        self.ser = ser
        self.files_info = files_info
        self.chunk_size = 1024
        self.verbose = verbose  # Флаг детального лога
        self.try_cmd = try_cmd
        self.clear_buffer = clear_buffer

    def read_with_trace(self, n, timeout_s, label):
        """Читает до n байт, логируя КАЖДЫЙ подошедший кусок с таймингом.
        Диагностика для случая, когда response = self.ser.read(n) молча
        возвращает меньше байт, чем ожидалось - показывает, что реально
        приходит и когда, вместо одной строки "Ошибка"."""
        buf = bytearray()
        t0 = time.time()
        chunks = 0
        self.log.emit(f"[trace:{label}] жду {n} байт, timeout={timeout_s}s")
        while len(buf) < n and (time.time() - t0) < timeout_s:
            chunk = self.ser.read(n - len(buf))
            if chunk:
                chunks += 1
                buf += chunk
                dt = time.time() - t0
                self.log.emit(f"[trace:{label}] +{len(chunk)} байт @ {dt:.3f}s: " +
                               ' '.join(f'{b:02X}' for b in chunk) +
                               f"  (всего {len(buf)}/{n})")
        dt = time.time() - t0
        if len(buf) < n:
            self.log.emit(f"[trace:{label}] ИТОГ: получено {len(buf)}/{n} байт за {dt:.3f}s "
                           f"в {chunks} кусках -> " + (' '.join(f'{b:02X}' for b in buf) if buf else "(пусто)"))
        else:
            self.log.emit(f"[trace:{label}] ИТОГ: все {n} байт получены за {dt:.3f}s в {chunks} кусках")
        return bytes(buf)

    def drain_and_dump(self, seconds, label, prefix=b''):
        """Дочитывает всё, что ещё присылает устройство, и печатает как текст.
        Нужно, когда вместо 8-байтного ACK прилетает диагностическое
        сообщение бутлоадера - иначе оно обрезается на первых 8 байтах."""
        buf = bytearray(prefix)
        t0 = time.time()
        while (time.time() - t0) < seconds:
            chunk = self.ser.read(256)
            if chunk:
                buf += chunk
                t0 = time.time()   # продлеваем, пока данные идут
        if not buf:
            self.log.emit(f"[dump:{label}] ничего не пришло")
            return bytes(buf)
        text = buf.decode('utf-8', errors='replace').replace('\r\n', ' | ').replace('\r', ' ').replace('\n', ' | ')
        self.log.emit(f"[dump:{label}] {len(buf)} байт текстом: {text}")
        self.log.emit(f"[dump:{label}] hex: " + ' '.join(f'{b:02X}' for b in buf))
        return bytes(buf)

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
                    self.done.emit(False)
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
                self.log.emit("Запрос (WriteAddress): " + ' '.join(f'{b:02X}' for b in write_addr) +
                              f"  [addr=0x{addr:08X} size={size}]")
                n_written = self.ser.write(write_addr)
                self.ser.flush()
                self.log.emit(f"[trace] ser.write() вернул {n_written} (ожидалось {len(write_addr)}), "
                              f"in_waiting сразу после записи: {self.ser.in_waiting}")
                response = self.read_with_trace(8, 12.0, "WriteAddress")
                if len(response) != 8 or response[0] != 0xAA or response[2] & 0x80:
                    # Прилетел не ACK, а скорее всего диагностический текст от
                    # бутлоадера - дочитываем его целиком, иначе видно только
                    # первые 8 байт.
                    self.drain_and_dump(2.0, "WriteAddress", prefix=response)
                    self.log.emit("Ошибка: Ответ WriteAddress!")
                    self.done.emit(False)
                    return

                self.log.emit("Успех: Получен ответ WriteAddress")

                # WriteData chunks
                for j in range(0, size, self.chunk_size):
                    if self.isInterruptionRequested():
                        self.log.emit("Прошивка прервана по запросу")
                        self.done.emit(False)
                        return
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
                        self.done.emit(False)
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
                self.done.emit(False)
                return

            self.done.emit(True)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {e}")
            self.done.emit(False)