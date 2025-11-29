# core/jlink_flash.py
# Поток для прошивки hex и bin файлов через Segger J-Link

from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import os
import tempfile

class JLinkFlashThread(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, file_path, cli_path, device):
        super().__init__()
        self.file_path = file_path
        self.cli_path = cli_path
        self.device = device

    def run(self):
        try:
            if not os.path.exists(self.cli_path):
                self.log.emit(f"JLink.exe не найден: {self.cli_path}")
                self.finished.emit(False)
                return

            self.log.emit("Начинаем прошивку...")

            # Создаем временный скрипт .jlink с разблокировкой flash для STM32L4 (адрес 0x40022004)
            script_content = f"""
exitonerror 1
device {self.device}
si SWD
speed 4000
r
h
w4 0x40022004 0x45670123
w4 0x40022004 0xCDEF89AB
erase
loadfile {self.file_path}
r
g
exit
"""

            with tempfile.NamedTemporaryFile(delete=False, suffix='.jlink', mode='w') as script_file:
                script_file.write(script_content)
                script_path = script_file.name

            cmd = [self.cli_path, "-CommanderScript", script_path]
            self.log.emit(f"Выполнение команды: {' '.join(cmd)}")

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                self.log.emit(line.strip())
            process.wait()
            os.unlink(script_path)

            if process.returncode != 0:
                self.log.emit(f"Ошибка выполнения: код {process.returncode}")
                self.finished.emit(False)
                return

            self.log.emit("Прошивка завершена успешно!")
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {str(e)}")
            self.finished.emit(False)

class JLinkEraseThread(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, cli_path, device):
        super().__init__()
        self.cli_path = cli_path
        self.device = device

    def run(self):
        try:
            if not os.path.exists(self.cli_path):
                self.log.emit(f"JLink.exe не найден: {self.cli_path}")
                self.finished.emit(False)
                return

            self.log.emit("Начинаем очистку...")

            # Создаем временный скрипт .jlink с разблокировкой flash для STM32L4 (адрес 0x40022004)
            script_content = f"""
exitonerror 1
device {self.device}
si SWD
speed 4000
r
h
w4 0x40022004 0x45670123
w4 0x40022004 0xCDEF89AB
erase
r
g
exit
"""

            with tempfile.NamedTemporaryFile(delete=False, suffix='.jlink', mode='w') as script_file:
                script_file.write(script_content)
                script_path = script_file.name

            cmd = [self.cli_path, "-CommanderScript", script_path]
            self.log.emit(f"Выполнение команды: {' '.join(cmd)}")

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                self.log.emit(line.strip())
            process.wait()
            os.unlink(script_path)

            if process.returncode != 0:
                self.log.emit(f"Ошибка выполнения: код {process.returncode}")
                self.finished.emit(False)
                return

            self.log.emit("Очистка завершена успешно!")
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {str(e)}")
            self.finished.emit(False)