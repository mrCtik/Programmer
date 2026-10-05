# core/jlink_flash.py
# Поток для прошивки hex и bin файлов через Segger J-Link

from PyQt5.QtCore import QThread, pyqtSignal
import os

from utils import proc, tools

# Разблокировка флеша STM32L4 (регистр FLASH_KEYR). Для другого
# семейства этот адрес значит иное, поэтому ключи шлём только когда
# контроллер действительно из L4.
L4_UNLOCK = "w4 0x40022004 0x45670123\nw4 0x40022004 0xCDEF89AB\n"


def unlock_for(device):
    return L4_UNLOCK if device.upper().startswith('STM32L4') else ""

class JLinkFlashThread(QThread):
    log = pyqtSignal(str)
    # done, а не finished: QThread уже имеет свой сигнал finished(),
    # и объявление с тем же именем перекрывало его для всего класса
    done = pyqtSignal(bool)

    def __init__(self, file_path, cli_path, device):
        super().__init__()
        self.file_path = file_path
        self.cli_path = cli_path
        self.device = device

    def run(self):
        try:
            if not os.path.exists(self.cli_path):
                self.log.emit(f"JLink.exe не найден: {self.cli_path}")
                self.done.emit(False)
                return

            self.log.emit("Начинаем прошивку...")

            # Создаем временный скрипт .jlink с разблокировкой flash для STM32L4 (адрес 0x40022004)
            script_content = (
                "exitonerror 1\n"
                f"device {self.device}\nsi SWD\nspeed 4000\nr\nh\n"
                + unlock_for(self.device) +
                f"erase\nloadfile {self.file_path}\nr\ng\nexit\n")

            script_path = tools.temp_script(script_content, '.jlink')
            try:
                cmd = [self.cli_path, "-CommanderScript", script_path]
                self.log.emit(f"Выполнение команды: {' '.join(cmd)}")

                process = proc.popen(cmd)
                for line in process.stdout:
                    self.log.emit(line.strip())
                process.wait()
            finally:
                tools.drop_temp(script_path)

            if process.returncode != 0:
                self.log.emit(f"Ошибка выполнения: код {process.returncode}")
                self.done.emit(False)
                return

            self.log.emit("Прошивка завершена успешно!")
            self.done.emit(True)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {str(e)}")
            self.done.emit(False)

class JLinkEraseThread(QThread):
    log = pyqtSignal(str)
    # done, а не finished: QThread уже имеет свой сигнал finished(),
    # и объявление с тем же именем перекрывало его для всего класса
    done = pyqtSignal(bool)

    def __init__(self, cli_path, device):
        super().__init__()
        self.cli_path = cli_path
        self.device = device

    def run(self):
        try:
            if not os.path.exists(self.cli_path):
                self.log.emit(f"JLink.exe не найден: {self.cli_path}")
                self.done.emit(False)
                return

            self.log.emit("Начинаем очистку...")

            # Создаем временный скрипт .jlink с разблокировкой flash для STM32L4 (адрес 0x40022004)
            script_content = (
                "exitonerror 1\n"
                f"device {self.device}\nsi SWD\nspeed 4000\nr\nh\n"
                + unlock_for(self.device) +
                "erase\nr\ng\nexit\n")

            script_path = tools.temp_script(script_content, '.jlink')
            try:
                cmd = [self.cli_path, "-CommanderScript", script_path]
                self.log.emit(f"Выполнение команды: {' '.join(cmd)}")

                process = proc.popen(cmd)
                for line in process.stdout:
                    self.log.emit(line.strip())
                process.wait()
            finally:
                tools.drop_temp(script_path)

            if process.returncode != 0:
                self.log.emit(f"Ошибка выполнения: код {process.returncode}")
                self.done.emit(False)
                return

            self.log.emit("Очистка завершена успешно!")
            self.done.emit(True)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {str(e)}")
            self.done.emit(False)