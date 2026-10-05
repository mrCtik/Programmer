# logic/logic_type_2.py
# Реализация логики для type_2 с учетом протокола из bootloader
# Поддержка версии, даты и серийного номера

import time
import struct
import binascii

# CRC32 таблица и функция (без изменений)
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
        version = date_str = serial_num = None

        while time.time() - start_time < 10:  # 10 секунд таймаут
            bytes_read = serial_port.read(1024)
            if bytes_read:
                buffer.extend(bytes_read)
                buffer_str = buffer.decode('utf-8', errors='ignore')
                print(f"Received (decoded): {buffer_str}")  # debug

                if "Bootloader started" in buffer_str:
                    print("Найдено 'Bootloader started'")
                    lines = buffer_str.split('\r\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith("Version: ") and "Date:" in line and "Serial:" in line:
                            # Ожидаемый формат: Version: V2.39  Date: 2026-02-01  Serial: SN00000001
                            try:
                                parts = line.split("  ")
                                if len(parts) >= 3:
                                    version_part = parts[0].replace("Version: ", "").strip()
                                    date_part   = parts[1].replace("Date: ",   "").strip()
                                    serial_part = parts[2].replace("Serial: ", "").strip()

                                    version    = version_part
                                    date_str   = date_part
                                    serial_num = serial_part

                                    print(f"Parsed → Version: {version}, Date: {date_str}, Serial: {serial_num}")
                                    break
                            except Exception as e:
                                print(f"Ошибка парсинга строки версии: {e} → {line}")

                    if version and date_str:
                        # Обновляем UI
                        parent_widget.version_label.setText(f"Версия прошивки: {version}")
                        parent_widget.date_label.setText(  f"Дата прошивки:   {date_str}")
                        parent_widget.serial_label.setText(f"Серийный номер:  {serial_num or '—'}")

                        parent_widget.original_version = version
                        parent_widget.original_date    = date_str
                        parent_widget.original_serial  = serial_num or ""

                        parent_widget.version_input.setText(version)
                        parent_widget.date_input.setText(date_str)
                        parent_widget.serial_input.setText(serial_num or "")

                        parent_widget.check_changes()
                        return True

        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка",
                            "Не удалось найти строку с версией, датой и серийным номером за 10 секунд.")
        return False

    except Exception as e:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка", f"Ошибка чтения информации: {e}")
        return False


def send_update(serial_port, version, date, serial, parent_widget):
    """
    Отправка команды 0x05 с данными: version\0date\0serial\0
    """
    try:
        # 1. Ждём появления Bootloader started
        serial_port.reset_input_buffer()
        buffer = bytearray()
        start_time = time.time()
        bootloader_detected = False

        while time.time() - start_time < 10 and not bootloader_detected:
            bytes_read = serial_port.read(1024)
            if bytes_read:
                buffer.extend(bytes_read)
                buffer_str = buffer.decode('utf-8', errors='ignore')
                if "Bootloader started" in buffer_str:
                    bootloader_detected = True
                    print("Обнаружен Bootloader started → можно отправлять команду")
                    break

        if not bootloader_detected:
            raise Exception("Не получено 'Bootloader started' за 10 секунд.")

        # 2. Формируем полезную нагрузку: version\0date\0serial\0
        # Если serial пустой — отправляем пустую строку (устройство сохранит старое значение)
        payload = (
            (version or "").encode('utf-8') + b'\x00' +
            (date    or "").encode('utf-8') + b'\x00' +
            (serial  or "").encode('utf-8') + b'\x00'
        )

        data_len = len(payload)
        if data_len > 1024:
            raise Exception(f"Данные слишком длинные: {data_len} байт (макс 1024)")

        print(f"Payload length: {data_len}, payload: {payload!r}")

        # 3. Формируем середину пакета: len_low, len_high, cmd(0x05), data
        packet_mid = bytearray([
            data_len & 0xFF,
            (data_len >> 8) & 0x7F,
            0x05
        ]) + payload

        # 4. CRC32 над [len_low, len_high, cmd, data]
        crc = calc_crc(packet_mid)

        # 5. Полный пакет: AA + mid + CRC (4 байта LE)
        packet = bytearray([0xAA]) + packet_mid + struct.pack('<I', crc)

        print(f"Отправляем пакет (hex): {binascii.hexlify(packet).decode()}")

        # 6. Отправка
        serial_port.write(packet)
        serial_port.flush()
        print(f"Отправлено {len(packet)} байт")

        # 7. Ожидание ACK (8 байт пакет с len=0, cmd=0x05)
        ack_start = time.time()
        ack_buffer = bytearray()

        while time.time() - ack_start < 5:
            chunk = serial_port.read(8)
            if chunk:
                ack_buffer.extend(chunk)
                print(f"Получен ACK фрагмент: {binascii.hexlify(chunk)}")

                while len(ack_buffer) >= 8:
                    if ack_buffer[0] != 0xAA:
                        ack_buffer = ack_buffer[1:]
                        continue

                    len_low  = ack_buffer[1]
                    len_high = ack_buffer[2]
                    cmd      = ack_buffer[3]

                    if len_low == 0 and (len_high & 0x7F) == 0 and cmd == 0x05:
                        error_bit = (len_high & 0x80) != 0
                        received_crc = struct.unpack('<I', ack_buffer[4:8])[0]
                        calc_crc_ack = calc_crc(ack_buffer[1:4])

                        print(f"ACK разобран: error={error_bit}, CRC recv={hex(received_crc)}, calc={hex(calc_crc_ack)}")

                        if received_crc == calc_crc_ack:
                            if not error_bit:
                                from PyQt5.QtWidgets import QMessageBox
                                QMessageBox.information(parent_widget, "Успех",
                                                        "Версия, дата и серийный номер успешно обновлены.")
                                return True
                            else:
                                raise Exception("Устройство вернуло NACK (ошибка при записи)")
                    # Если не подошло — сдвигаем на 1 байт
                    ack_buffer = ack_buffer[1:]

        raise Exception("Не получен корректный ACK за 5 секунд.")

    except Exception as e:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка отправки",
                            f"Не удалось установить информацию о прошивке:\n{e}")
        return False