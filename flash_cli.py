"""
Прошивка платы из командной строки, без графического интерфейса.

Тот же самый FlashThread, что использует вкладка BLCL, — просто вызванный
напрямую. Нужен для сценариев, где прошивка это шаг скрипта, а не действие
человека: прогнать калибровку, поправить прошивку, залить, прогнать снова.

Порядок обмена задан бутлоадером и права на ошибку почти не оставляет:
после сброса он печатает приветствие, даёт пять секунд на SetFirmwareInfo,
а затем посылает TryConnection РОВНО ОДИН РАЗ. Пропустив этот единственный
пакет, повторить попытку без нового сброса нельзя — поэтому скрипт ждёт
приветствия сколько нужно, а дальше идёт без пауз.

Если на плате прошивка V0.5 и новее, сброс делается командой RESET по тому
же порту (ключ --reset), иначе плату надо перезапустить руками.

ВАЖНО: не отправляйте вывод этого скрипта в head. Когда head закроет канал,
питон получит SIGPIPE и умрёт посреди прошивки — а если это случится после
стирания, плата останется без приложения. Пишите в файл или в tail.

Примеры:
  python flash_cli.py COM12 firmware/V0.8_OPU_app.bin --reset
  python flash_cli.py COM12 firmware/V0.8_OPU_app.bin --wait 300
"""
import argparse
import os
import re
import sys
import time

import serial
from PyQt5.QtCore import QCoreApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.blcl_protocol import FlashThread          # noqa: E402
from utils.helpers import calc_crc, create_blcl_packet   # noqa: E402

APP_ADDRESS = 0x08008000
TRY_CMD_MCU = 0x7E
NUL = bytes([0])          # разделитель полей в SetFirmwareInfo


def wait_bootloader(ser, timeout_s, quiet_s=0.15):
    """Дождаться приветствия бутлоадера И тишины в линии.

    Ждать одного лишь "Bootloader started" мало: следом печатается строка
    Version, а у STM32F4 в приёмнике один байт без FIFO. Пакет, посланный
    в этот момент, потеряется весь, кроме последнего байта — раньше это
    сходило с рук только за счёт буферизации в ОС, то есть по везению.
    Поэтому ждём ещё и паузы: она означает, что плата договорила и слушает.
    """
    buf = b""
    seen = False
    last = time.time()
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        # Читаем только то, что уже пришло. ser.read(N) с большим таймаутом
        # порта ждал бы все N байт: приветствие короче, и возврат происходил
        # через пять секунд - когда бутлоадер давно ушёл в приложение.
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            last = time.time()
            if b"Bootloader started" in buf:
                seen = True
            continue
        # Блокирующего чтения тут быть не должно вовсе: ser.read(1) при пустом
        # буфере ждёт весь таймаут порта (пять секунд), а окно бутлоадера на
        # SetFirmwareInfo ровно столько и длится - к моменту возврата оно уже
        # закрыто, и единственный TryConnection пропущен. Просто спим коротко.
        time.sleep(0.005)
        if seen and (time.time() - last) > quiet_s:
            return True
    return False


def set_firmware_info(ser, version, date, serial):
    """Записать версию, дату и серийный номер в метаданные бутлоадера.

    Поля разделяются нулевым байтом; пустое поле бутлоадер оставляет прежним.
    Без этой команды в метаданных остаётся версия, залитая когда-то через
    графический Programmer, и `Bootloader started` рапортует не о том, что
    реально лежит в плате.

    Запись метаданных включает стирание сектора, поэтому ответа ждём долго.
    """
    data = (version.encode("utf-8") + NUL +
            date.encode("utf-8") + NUL +
            serial.encode("utf-8") + NUL)
    ser.write(create_blcl_packet(0x05, data))
    ser.flush()

    deadline = time.time() + 10.0
    ack = b""
    while time.time() < deadline and len(ack) < 8:
        ack += ser.read(8 - len(ack))
    if len(ack) == 8 and ack[0] == 0xAA and not (ack[2] & 0x80):
        print(f"метаданные обновлены: {version} / {date} / {serial}")
        return True
    print(f"не удалось обновить метаданные (ответ {ack.hex(' ') or 'пусто'})")
    return False


def main():
    ap = argparse.ArgumentParser(description="Прошивка ОПУ через бутлоадер BLCL")
    ap.add_argument("port", help="COM-порт, например COM12")
    ap.add_argument("binary", help="файл прошивки .bin")
    ap.add_argument("--addr", type=lambda v: int(v, 0), default=APP_ADDRESS,
                    help=f"адрес загрузки (по умолчанию 0x{APP_ADDRESS:08X})")
    ap.add_argument("--reset", action="store_true",
                    help="послать команду RESET работающей прошивке вместо ручного сброса")
    ap.add_argument("--wait", type=float, default=30.0,
                    help="сколько секунд ждать приветствия бутлоадера "
                         "(удобно увеличить, когда сброс делает человек)")
    ap.add_argument("--version", help="версия для метаданных бутлоадера "
                                      "(по умолчанию берётся из имени файла)")
    ap.add_argument("--date", help="дата для метаданных (по умолчанию дата файла)")
    ap.add_argument("--serial", default="", help="серийный номер; пусто = не менять")
    ap.add_argument("--no-info", action="store_true",
                    help="не трогать метаданные бутлоадера")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.binary):
        sys.exit(f"нет файла {args.binary}")

    # ОБЯЗАТЕЛЬНО: к образу дописывается CRC32 (тот же полином, что в пакетах).
    # Получив финальный TryConnection, бутлоадер считает CRC по всему залитому
    # куску без последних четырёх байт и сверяет с ними. Не сошлось - он пишет
    # "CRC verify fail" и уходит в while(1), то есть плата замолкает до сброса.
    # Вкладка BLCL делает ровно это же, складывая результат в ui/files/mcu_prog.bin.
    with open(args.binary, "rb") as f:
        data = f.read()
    payload = data + calc_crc(data).to_bytes(4, "little")
    prog_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "files")
    os.makedirs(prog_dir, exist_ok=True)
    prog_path = os.path.join(prog_dir, "mcu_prog_cli.bin")
    with open(prog_path, "wb") as f:
        f.write(payload)
    print(f"{os.path.basename(args.binary)}: {len(data)} байт + CRC32 = {len(payload)}")

    QCoreApplication(sys.argv)          # QThread без приложения не создаётся

    # Таймаут порта должен перекрывать самый долгий шаг обмена. Узкое место -
    # не стирание флеша, а сама передача: кусок WriteData это 1024 байта плюс
    # заголовок, на 115200 бод это около 90 мс, и ответ приходит уже после них.
    # С коротким таймаутом ser.read(8) возвращает пустоту, и прошивка падает на
    # первом же куске с "Ошибка: Ответ WriteData".
    ser = serial.Serial(args.port, 115200, timeout=5.0)
    try:
        if args.reset:
            # Сброс должен уйти ДО того, как начнём ловить TryConnection,
            # иначе двухсекундное окно бутлоадера закроется раньше, чем мы
            # начнём слушать.
            ser.reset_input_buffer()
            ser.write(b"RESET\n")
            ser.flush()
            print("отправлена команда RESET, жду бутлоадер...")
            time.sleep(0.2)
        else:
            print(f"ПЕРЕЗАПУСТИТЕ ПЛАТУ (кнопка сброса или питание). "
                  f"Жду до {args.wait:.0f} с...")

        # Порядок жёстко задан устройством бутлоадера: он печатает приветствие,
        # даёт пять секунд на SetFirmwareInfo, а затем посылает TryConnection
        # РОВНО ОДИН РАЗ. Поэтому ждать приветствия можно сколько угодно, но
        # дальше тянуть нельзя: пропустив единственный пакет, повторить попытку
        # без нового сброса невозможно.
        if not wait_bootloader(ser, args.wait):
            print("приветствие бутлоадера не получено")
            return 1

        if not args.no_info:
            ver = args.version
            if not ver:
                m = re.search(r"V(\d+\.\d+)", os.path.basename(args.binary))
                ver = "V" + m.group(1) if m else ""
            dt = args.date or time.strftime(
                "%Y-%m-%d", time.localtime(os.path.getmtime(args.binary)))
            if ver:
                set_firmware_info(ser, ver, dt, args.serial)

        ok = {"value": False}
        th = FlashThread(ser, [(prog_path, args.addr)],
                         verbose=args.verbose, try_cmd=TRY_CMD_MCU)
        th.log.connect(print)
        th.finished.connect(lambda v: ok.update(value=v))
        th.run()                        # синхронно, в этом же потоке
    finally:
        ser.close()

    print("ГОТОВО" if ok["value"] else "НЕ УДАЛОСЬ")
    return 0 if ok["value"] else 1


if __name__ == "__main__":
    sys.exit(main())
