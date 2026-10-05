# core/stlink_flash.py
from PyQt5.QtCore import QThread, pyqtSignal
import os
import subprocess

from utils import proc

class STM32FlashThread(QThread):
    log = pyqtSignal(str)
    # done, а не finished: QThread уже имеет свой сигнал finished(),
    # и объявление с тем же именем перекрывало его для всего класса
    done = pyqtSignal(bool)

    def __init__(self, bin_path, cli_path):
        super().__init__()
        self.bin_path = bin_path
        self.cli_path = cli_path

    def run(self):
        try:
            # Проверка ST-Link
            self.log.emit("Проверка ST-Link...")
            result = proc.run([self.cli_path, "-c", "port=SWD"], timeout=10)
            self.log.emit(result.stdout + result.stderr)
            if "ST-LINK" not in result.stdout:
                self.log.emit("ST-Link не найден!")
                self.done.emit(False)
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

            result = proc.run(cmd)
            self.log.emit(result.stdout + result.stderr)

            # Проверка успеха (расширенная)
            success_keywords = ["Verification OK", "Download verified successfully", "Programming Complete", "File download complete"]
            if any(keyword in result.stdout for keyword in success_keywords):
                self.log.emit("Прошивка STM32 завершена успешно!")
                self.done.emit(True)
            else:
                self.log.emit("Ошибка прошивки!")
                self.done.emit(False)
        except FileNotFoundError:
            self.log.emit("Ошибка: STM32_Programmer_CLI.exe не найден! Проверьте путь.")
            self.done.emit(False)
        except subprocess.TimeoutExpired:
            self.log.emit("Ошибка: Таймаут выполнения команды!")
            self.done.emit(False)
        except Exception as e:
            self.log.emit(f"Ошибка: {e}")
            self.done.emit(False)