# core/xilinx_flash.py
# Поток для прошивки Xilinx Configuration Memory Device через JTAG файлом .mcs

from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import os
import tempfile

class XilinxFlashThread(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)
    progress = pyqtSignal(int)

    def __init__(self, mcs_path, cli_path, flash_part, bit_path=''):
        super().__init__()
        self.mcs_path = mcs_path
        self.cli_path = cli_path
        self.flash_part = flash_part
        self.bit_path = bit_path
        self.is_vivado = 'vivado' in os.path.basename(self.cli_path).lower()

    def run(self):
        try:
            if not os.path.exists(self.cli_path):
                self.log.emit(f"CLI файл не найден: {self.cli_path}")
                self.finished.emit(False)
                return

            self.log.emit("Проверка JTAG...")

            # TCL для проверки с дебагом
            if self.is_vivado:
                check_tcl_script = """
open_hw_manager
connect_hw_server -url TCP:localhost:3121 -allow_non_jtag
set targets [get_hw_targets]
if {[llength $targets] > 0} {
    puts "Targets found: $targets"
    set target [lindex $targets 0]
    open_hw_target $target
    set devices [get_hw_devices]
    if {[llength $devices] > 0} {
        puts "Devices found: $devices"
    } else {
        puts "No devices found"
    }
    close_hw_target
} else {
    puts "No targets found"
}
close_hw_manager
exit
"""
            else:
                check_tcl_script = """
set url "TCP:localhost:3121"
connect -url $url
targets
exit
"""

            with tempfile.NamedTemporaryFile(delete=False, suffix='.tcl', mode='w') as tcl_file:
                tcl_file.write(check_tcl_script)
                check_tcl_path = tcl_file.name

            cmd = self.get_cmd(check_tcl_path)
            self.log.emit(f"Выполнение команды: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            os.unlink(check_tcl_path)
            self.log.emit(self.filter_output(result.stdout + result.stderr))

            if result.returncode != 0:
                self.log.emit(f"Ошибка выполнения CLI: код возврата {result.returncode}")
                self.finished.emit(False)
                return

            output = result.stdout + result.stderr
            filtered_output = self.filter_output(output)
            stdout_lower = filtered_output.lower()

            if "error" in stdout_lower or "no targets found" in stdout_lower or "no devices found" in stdout_lower or "unable to connect" in stdout_lower:
                self.log.emit("JTAG или устройство не найдено! Проверьте подключение, драйверы, питание. Убедитесь, что нет конфликтующих процессов hw_server (убейте в Диспетчере задач).")
                self.finished.emit(False)
                return
            if ("targets found" in stdout_lower or "connect successful" in stdout_lower or "devices found" in stdout_lower) and ("xc" in stdout_lower or "jtag" in stdout_lower or "fpga" in stdout_lower or "digilent" in stdout_lower or "xilinx_tcf" in stdout_lower or "xc7s25" in stdout_lower):
                self.log.emit("JTAG найден.")
            else:
                self.log.emit("Не удалось подтвердить наличие JTAG. Проверьте полный вывод команды.")
                self.finished.emit(False)
                return

            self.log.emit("Начинаем прошивку Configuration Memory Device...")

            # TCL для прошивки, адаптированный из лога Vivado
            if self.is_vivado:
                tcl_script = f"""
open_hw_manager
connect_hw_server -url TCP:localhost:3121 -allow_non_jtag
set targets [get_hw_targets]
if {{[llength $targets] == 0}} {{
    puts "No targets found"
    exit
}}
set target [lindex $targets 0]
open_hw_target $target
set device [lindex [get_hw_devices *xc*] 0]
set_property PROGRAM.FILE "{self.bit_path.replace('\\', '/')}" [get_hw_devices $device]
program_hw_devices [get_hw_devices $device]
refresh_hw_device -update_hw_probes false $device
set cfgmem [create_hw_cfgmem -hw_device $device [lindex [get_cfgmem_parts {{{self.flash_part}}}] 0]]
set_property PROGRAM.ADDRESS_RANGE {{use_file}} $cfgmem
set_property PROGRAM.FILES [list "{self.mcs_path.replace('\\', '/')}" ] $cfgmem
set_property PROGRAM.PRM_FILE {{}} $cfgmem
set_property PROGRAM.UNUSED_PIN_TERMINATION {{pull-none}} $cfgmem
set_property PROGRAM.BLANK_CHECK 0 $cfgmem
set_property PROGRAM.ERASE 1 $cfgmem
set_property PROGRAM.CFG_PROGRAM 1 $cfgmem
set_property PROGRAM.VERIFY 1 $cfgmem
set_property PROGRAM.CHECKSUM 0 $cfgmem
startgroup
create_hw_bitstream -hw_device $device [get_property PROGRAM.HW_CFGMEM_BITFILE $device]
program_hw_devices $device
refresh_hw_device $device
program_hw_cfgmem -hw_cfgmem $cfgmem -verbose
endgroup
close_hw_target
close_hw_manager
exit
"""
            else:
                tcl_script = f"""
set url "TCP:localhost:3121"
connect -url $url
targets -set -filter {{name =~ "*xc*"}}
set device [lindex [get_hw_devices *xc*] 0]
set_property PROGRAM.FILE "{self.bit_path.replace('\\', '/')}" [get_hw_devices $device]
program_hw_devices [get_hw_devices $device]
refresh_hw_device -update_hw_probes false $device
set cfgmem [create_hw_cfgmem -hw_device $device [lindex [get_cfgmem_parts {{{self.flash_part}}}] 0]]
set_property PROGRAM.ADDRESS_RANGE {{use_file}} $cfgmem
set_property PROGRAM.FILES [list "{self.mcs_path.replace('\\', '/')}" ] $cfgmem
set_property PROGRAM.PRM_FILE {{}} $cfgmem
set_property PROGRAM.UNUSED_PIN_TERMINATION {{pull-none}} $cfgmem
set_property PROGRAM.BLANK_CHECK 0 $cfgmem
set_property PROGRAM.ERASE 1 $cfgmem
set_property PROGRAM.CFG_PROGRAM 1 $cfgmem
set_property PROGRAM.VERIFY 1 $cfgmem
set_property PROGRAM.CHECKSUM 0 $cfgmem
startgroup
create_hw_bitstream -hw_device $device [get_property PROGRAM.HW_CFGMEM_BITFILE $device]
program_hw_devices $device
refresh_hw_device $device
program_hw_cfgmem -hw_cfgmem $cfgmem -verbose
endgroup
exit
"""

            with tempfile.NamedTemporaryFile(delete=False, suffix='.tcl', mode='w') as tcl_file:
                tcl_file.write(tcl_script)
                tcl_path = tcl_file.name

            cmd = self.get_cmd(tcl_path)
            self.log.emit(f"Выполнение команды: {' '.join(cmd)}")

            # Используем Popen для чтения вывода в реальном времени
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                self.log.emit(line.strip())
                self.update_progress(line.lower())
            process.wait()

            if process.returncode != 0:
                self.log.emit(f"Ошибка выполнения CLI: код возврата {process.returncode}")
                self.finished.emit(False)
                return

            self.log.emit("Прошивка завершена успешно!")
            self.progress.emit(100)
            self.finished.emit(True)
        except subprocess.TimeoutExpired:
            self.log.emit("Таймаут выполнения команды!")
            self.finished.emit(False)
        except Exception as e:
            self.log.emit(f"ОШИБКА: {str(e)}")
            self.finished.emit(False)

    def update_progress(self, line):
        if "performing erase operation" in line:
            self.progress.emit(30)
        elif "erase operation successful" in line:
            self.progress.emit(50)
        elif "performing program and verify operations" in line:
            self.progress.emit(60)
        elif "program/verify operation successful" in line:
            self.progress.emit(80)
        elif "flash programming completed successfully" in line:
            self.progress.emit(100)

    def get_cmd(self, tcl_path):
        base_name = os.path.basename(self.cli_path).lower()
        if 'vivado' in base_name:
            return [self.cli_path, '-mode', 'batch', '-nolog', '-nojournal', '-source', tcl_path]
        else:
            return [self.cli_path, tcl_path]

    def filter_output(self, output):
        lines = output.split('\n')
        filtered_lines = []
        skip_webtalk = False
        for line in lines:
            if line.strip().startswith('#'):
                continue
            if "Webtalk" in line or "webtalk" in line.lower():
                skip_webtalk = True
                continue
            if skip_webtalk:
                if "Exiting Webtalk" in line:
                    skip_webtalk = False
                continue
            if "vivado.log" in line or ".jou" in line or ".Xil" in line or "Vivado-" in line:
                continue
            filtered_lines.append(line)
        return '\n'.join(filtered_lines)