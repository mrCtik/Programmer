# utils/helpers.py
import os
import sys
import glob

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

def find_stm32_cli(drives=['C:', 'D:', 'E:']):
    exe_names = ['STM32_Programmer_CLI.exe']
    patterns = [f"{drive}\\Program Files\\STMicroelectronics\\**\\{exe}" for drive in drives for exe in exe_names]
    for pattern in patterns:
        print(f"Searching with pattern: {pattern}")
        paths = glob.glob(pattern, recursive=True)
        if paths:
            return paths[0]
    return None

def find_xilinx_cli(drives=['C:', 'D:', 'E:']):
    exe_names = ['vivado.bat', 'vivado_lab.bat', 'xsdb.bat']
    patterns = [f"{drive}\\Xilinx\\**\\{exe}" for drive in drives for exe in exe_names]
    for pattern in patterns:
        print(f"Searching with pattern: {pattern}")
        paths = glob.glob(pattern, recursive=True)
        if paths:
            return paths[0]
    return None

def find_jlink_exe(drives=['C:', 'D:', 'E:']):
    exe_names = ['JLink.exe', 'JLinkExe.exe']
    patterns = [f"{drive}\\Program Files\\SEGGER\\**\\{exe}" for drive in drives for exe in exe_names]
    for pattern in patterns:
        print(f"Searching with pattern: {pattern}")
        paths = glob.glob(pattern, recursive=True)
        if paths:
            return paths[0]
    return None