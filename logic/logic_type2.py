# logic/logic_type_2.py
# Реализация логики для type_2 с учетом протокола из bootloader: ASCII строки для чтения, бинарный пакет для обновления с CRC32

import time
import struct
import binascii  # Для отладки, если нужно

# Функция для расчета CRC32, аналогично C коду
def make_crc_table():
    CRC_TABLE = [0] * 256
    for i in range(256):
        c = i
        for j in range(8):
            c = (c >> 1) ^ ((c & 1) * 0xEDB88320)
        CRC_TABLE[i] = c
    return CRC_TABLE

CRC_TABLE = make_crc_table()

def calc_crc(data):
    crc = 0xFFFFFFFF
    for byte in data:
        crc = CRC_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF

def read_firmware_info(serial_port, parent_widget):
    try:
        serial_port.reset_input_buffer()
        buffer = bytearray()
        start_time = time.time()
        version = None
        date = None
        while time.time() - start_time < 10:  # Таймаут 10 сек
            bytes_read = serial_port.read(1024)
            if bytes_read:
                buffer.extend(bytes_read)
                print(f"Received bytes: {bytes_read}")  # Debug: print received bytes
                buffer_str = buffer.decode('utf-8', errors='ignore')
                print(f"Buffer string: {buffer_str}")  # Debug: print decoded buffer
                if "Bootloader started" in buffer_str:
                    print("Found 'Bootloader started'")  # Debug
                    # Ищем строку версии после Bootloader started
                    lines = buffer_str.split('\r\n')
                    for line in lines:
                        if line.startswith("Version: "):
                            parts = line.split(" Date: ")
                            if len(parts) == 2:
                                version = parts[0].replace("Version: ", "").strip()
                                date = parts[1].strip()
                                print(f"Parsed version: {version}, date: {date}")  # Debug
                                break
                    if version and date:
                        parent_widget.version_label.setText(f"Версия прошивки: {version}")
                        parent_widget.date_label.setText(f"Дата прошивки: {date}")
                        parent_widget.version_input.setText(version)
                        parent_widget.date_input.setText(time.strftime("%Y-%m-%d"))
                        parent_widget.original_version = version
                        parent_widget.original_date = date
                        parent_widget.check_changes()
                        return True
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка", "Не удалось найти информацию о версии и дате в течение 10 секунд.")
        return False
    except Exception as e:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка", f"Не удалось прочитать информацию: {e}")
        return False

def send_update(serial_port, version, date, parent_widget):
    try:
        # Ждем "Bootloader started"
        serial_port.reset_input_buffer()
        buffer = bytearray()
        start_time = time.time()
        bootloader_started = False
        while time.time() - start_time < 10 and not bootloader_started:
            bytes_read = serial_port.read(1024)
            if bytes_read:
                buffer.extend(bytes_read)
                print(f"Received bytes for send_update: {bytes_read}")  # Debug
                buffer_str = buffer.decode('utf-8', errors='ignore')
                print(f"Buffer string for send_update: {buffer_str}")  # Debug
                if "Bootloader started" in buffer_str:
                    bootloader_started = True
                    print("Found 'Bootloader started' in send_update")  # Debug
                    break

        if not bootloader_started:
            raise Exception("Не получено 'Bootloader started' в течение 10 секунд после перезапуска.")

        # Формируем data: version\0 date\0
        data = version.encode('utf-8') + b'\x00' + date.encode('utf-8') + b'\x00'
        data_len = len(data)
        if data_len > 1024:
            raise Exception("Длина данных превышает 1024 байта.")
        print(f"Data length: {data_len}, Data: {data}")  # Additional debug

        # Формируем пакет без стартового AA и CRC
        packet_mid = bytearray([data_len & 0xFF, (data_len >> 8) & 0x7F, 0x05]) + data
        print(f"Packet mid: {binascii.hexlify(packet_mid)}")  # Additional debug

        # Вычисляем CRC над [len_low, len_high, cmd, data]
        crc = calc_crc(packet_mid)
        print(f"Calculated CRC: {hex(crc)}")  # Debug

        # Полный пакет: AA + packet_mid + CRC (4 байта little-endian)
        packet = bytearray([0xAA]) + packet_mid + struct.pack('<I', crc)
        print(f"Sending packet: {binascii.hexlify(packet)}")  # Debug: print packet in hex

        # Отправляем
        bytes_written = serial_port.write(packet)
        print(f"Bytes written: {bytes_written}")  # Additional debug

        # Ждем ACK (опционально, но для надежности: пакет len=0, error bit, cmd=0x05, CRC)
        ack_buffer = bytearray()
        start_time = time.time()
        while time.time() - start_time < 5:
            bytes_read = serial_port.read(8)  # ACK - 8 байт
            if bytes_read:
                ack_buffer.extend(bytes_read)
                print(f"Received ACK bytes: {binascii.hexlify(bytes_read)}")  # Debug
                print(f"Current ACK buffer: {binascii.hexlify(ack_buffer)}")  # Additional debug
                if len(ack_buffer) >= 8 and ack_buffer[0] == 0xAA:
                    len_low = ack_buffer[1]
                    len_high = ack_buffer[2]
                    cmd = ack_buffer[3]
                    print(f"Parsed ACK: len_low={len_low}, len_high={len_high}, cmd={cmd}")  # Additional debug
                    if len_low == 0 and (len_high & 0x7F) == 0 and cmd == 0x05:
                        error = 1 if (len_high & 0x80) else 0
                        crc_received = struct.unpack('<I', ack_buffer[4:8])[0]
                        crc_calc = calc_crc(ack_buffer[1:4])
                        print(f"Received CRC: {hex(crc_received)}, Calculated CRC: {hex(crc_calc)}")  # Debug
                        if crc_calc == crc_received:
                            if error == 0:
                                from PyQt5.QtWidgets import QMessageBox
                                QMessageBox.information(parent_widget, "Успех", "Информация о прошивке обновлена успешно.")
                                return True
                            else:
                                raise Exception("Получен NACK (error=1) от устройства.")
                    # If not matching, shift buffer if needed
                    if ack_buffer[0] != 0xAA:
                        ack_buffer = ack_buffer[1:]
        raise Exception("Не получен ACK в течение 5 секунд.")
    except Exception as e:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка", f"Не удалось установить информацию: {e}")
        return False