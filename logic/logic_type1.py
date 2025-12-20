# logic/logic_type_1.py
# Это текущая реализация с пакетами AA

import time

def calculate_crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
        crc &= 0xFF
    return crc

def read_firmware_info(serial_port, parent_widget):
    try:
        serial_port.reset_input_buffer()
        buffer = bytearray()
        start_time = time.time()
        while time.time() - start_time < 10:
            byte = serial_port.read(1)
            if byte:
                buffer.extend(byte)
                while len(buffer) > 0 and buffer[0] != 0xAA:
                    buffer = buffer[1:]
                if len(buffer) >= 4:
                    cmd = buffer[1]
                    data_len = buffer[2]
                    if len(buffer) >= 3 + data_len + 1:
                        data = buffer[3:3 + data_len]
                        crc_received = buffer[3 + data_len]
                        msg_for_crc = buffer[:3 + data_len]
                        crc_calc = calculate_crc8(msg_for_crc)
                        if crc_calc == crc_received and cmd == 0x01:
                            parts = data.split(b'\x00')
                            if len(parts) >= 2:
                                version = parts[0].decode('utf-8', errors='ignore')
                                date = parts[1].decode('utf-8', errors='ignore')
                                parent_widget.version_label.setText(f"Версия прошивки: {version}")
                                parent_widget.date_label.setText(f"Дата прошивки: {date}")
                                parent_widget.version_input.setText(version)
                                parent_widget.date_input.setText(date)
                                parent_widget.original_version = version
                                parent_widget.original_date = date
                                parent_widget.check_changes()
                                return True
                        buffer = buffer[1:]
        return False
    except Exception as e:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка", f"Не удалось прочитать информацию: {e}")
        return False

def send_update(serial_port, version, date, parent_widget):
    try:
        # Сначала ждем получения "Start User App" в ASCII
        serial_port.reset_input_buffer()
        buffer = bytearray()
        start_time = time.time()
        start_user_app_received = False
        while time.time() - start_time < 10 and not start_user_app_received:
            byte = serial_port.read(1)
            if byte:
                buffer.extend(byte)
                if b'Start User App' in buffer:
                    start_user_app_received = True
                    # Очистка буфера после получения
                    serial_port.reset_input_buffer()
                    break

        if not start_user_app_received:
            raise Exception("Не получено 'Start User App' в течение 10 секунд после перезапуска.")

        # Теперь формируем и отправляем обновление
        data = version.encode('utf-8') + b'\x00' + date.encode('utf-8') + b'\x00'
        data_len = len(data)
        msg = bytearray([0xAA, 0x02, data_len]) + data
        crc = calculate_crc8(msg)
        msg.append(crc)
        serial_port.write(msg)

        # Ждем подтверждения
        response = ""
        start_time = time.time()
        while time.time() - start_time < 5:
            line = serial_port.readline().decode('utf-8', errors='ignore').strip()
            if line:
                response += line
                if "updated" in response.lower():
                    return True
        raise Exception(f"Нет подтверждения. Получено: {response}")
    except Exception as e:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(parent_widget, "Ошибка", f"Не удалось установить информацию: {e}")
        return False