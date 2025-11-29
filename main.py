# main.py
# Главный файл запуска программы

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
from PyQt5.QtGui import QIcon
from ui.blcl_tab import BlclTab
from ui.stlink_tab import StlinkTab
from ui.xilinx_tab import XilinxTab  
from ui.styles import apply_dark_theme

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLCL + STM32 + Xilinx Programmer")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(1300, 750)

        tabs = QTabWidget()
        tabs.addTab(BlclTab(self), "BLCL Loader")
        tabs.addTab(StlinkTab(self), "STM32 ST-Link")
        tabs.addTab(XilinxTab(self), "Xilinx JTAG")  

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(tabs)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setCentralWidget(central)
        apply_dark_theme()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())