# core/stlink_flash.py
from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import os

class STM32FlashThread(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, bin_path, cli_path):
        super().__init__()
        self.bin_path = bin_path
        self.cli_path = cli_path

    def run(self):
        try:
            # Проверка ST-Link
            self.log.emit("Проверка ST-Link...")
            result = subprocess.run([self.cli_path, "-c", "port=SWD"], capture_output=True, text=True, timeout=10)
            self.log.emit(result.stdout + result.stderr)
            if "ST-LINK" not in result.stdout:
                self.log.emit("ST-Link не найден!")
                self.finished.emit(False)
                return

            self.log.emit("ST-Link найден. Прошивка...")

            # Определение типа файла
            ext = os.path.splitext(self.bin_path)[1].lower()

            if ext == '.hex':
                # Для .hex используем -d (CubeProgrammer сам обрабатывает .hex без адреса)
                cmd = [self.cli_path, "-c", "port=SWD", "freq=4000", "-d", self.bin_path, "-v", "-rst"]
            else:
                # Для .bin указываем адрес
                cmd = [self.cli_path, "-c", "port=SWD", "freq=4000", "-w", self.bin_path, "0x8000000", "-v", "-rst"]

            result = subprocess.run(cmd, capture_output=True, text=True)
            self.log.emit(result.stdout + result.stderr)

            # Проверка успеха (расширенная)
            success_keywords = ["Verification OK", "Download verified successfully", "Programming Complete", "File download complete"]
            if any(keyword in result.stdout for keyword in success_keywords):
                self.log.emit("Прошивка STM32 завершена успешно!")
                self.finished.emit(True)
            else:
                self.log.emit("Ошибка прошивки!")
                self.finished.emit(False)
        except FileNotFoundError:
            self.log.emit("Ошибка: STM32_Programmer_CLI.exe не найден! Проверьте путь.")
            self.finished.emit(False)
        except subprocess.TimeoutExpired:
            self.log.emit("Ошибка: Таймаут выполнения команды!")
            self.finished.emit(False)
        except Exception as e:
            self.log.emit(f"Ошибка: {e}")
            self.finished.emit(False)