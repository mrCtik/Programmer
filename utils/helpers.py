# utils/helpers.py
import os
import sys

def make_crc_table():
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ (0xEDB88320 if (c & 1) else 0)
        table.append(c & 0xFFFFFFFF)
    return table

CRC_TABLE = make_crc_table()

def calc_crc(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc = CRC_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF

def create_blcl_packet(opcode: int, data: bytes = b'') -> bytes:
    payload = len(data).to_bytes(2, 'little') + bytes([opcode]) + data
    crc = calc_crc(payload)
    return b'\xAA' + payload + crc.to_bytes(4, 'little')

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def _find_exe(roots, names, should_stop=None):
    """Первый подошедший файл из names в дереве roots.

    Обход свой, а не glob('**'): glob нельзя прервать, и кнопка «Отмена»
    в диалоге поиска закрывала окно, пока поток ещё минутами молотил
    диск. Здесь should_stop спрашивается на каждой папке.
    """
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            if should_stop and should_stop():
                return None
            for name in names:
                if name in filenames:
                    return os.path.join(dirpath, name)
    return None


def find_stm32_cli(drives=('C:', 'D:', 'E:'), should_stop=None):
    roots = [f"{d}\\Program Files\\STMicroelectronics" for d in drives]
    return _find_exe(roots, ['STM32_Programmer_CLI.exe'], should_stop)


def find_xilinx_cli(drives=('C:', 'D:', 'E:'), should_stop=None):
    roots = [f"{d}\\Xilinx" for d in drives]
    return _find_exe(roots, ['vivado.bat', 'vivado_lab.bat', 'xsdb.bat'],
                     should_stop)


def find_jlink_exe(drives=('C:', 'D:', 'E:'), should_stop=None):
    roots = [f"{d}\\Program Files\\SEGGER" for d in drives]
    return _find_exe(roots, ['JLink.exe', 'JLinkExe.exe'], should_stop)


def app_dir():
    """Папка, рядом с которой лежат рабочие данные.

    В собранном виде это папка с .exe, при запуске из исходников —
    корень проекта. Не путать с resource_path(): тот отдаёт путь внутрь
    временной распаковки PyInstaller, годный только на чтение —
    записанное туда пропадает при выходе из программы.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_path(*parts):
    """Путь к рабочим данным рядом с программой: firmware, mcs,
    настройки, промежуточные файлы прошивки."""
    return os.path.join(app_dir(), *parts)
