# utils/helpers.py
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