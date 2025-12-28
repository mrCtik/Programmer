# main.py
# Главный файл запуска программы
# Обновлён: логика COM вынесена в ui/version_tab.py

import sys
import time
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QMessageBox, QGroupBox, QSplitter, QMenuBar, QDialog, QTextBrowser
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from ui.blcl_tab import BlclTab
from ui.stlink_tab import StlinkTab
from ui.xilinx_tab import XilinxTab
from ui.jlink_tab import JlinkTab
from ui.version_tab import VersionPanel  # Теперь включает COM
from ui.styles import apply_dark_theme
from utils.markdown_formatter import markdown_to_html  # Новый импорт
from utils.helpers import resource_path  # Импорт resource_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLCL + STM32 + Xilinx Programmer")
        self.setWindowIcon(QIcon(resource_path("resources/icon.ico")))  # Путь к иконке в resources
        self.resize(1400, 800)

        # Меню бар
        menubar = self.menuBar()
        help_menu = menubar.addMenu("О программе")
        about_action = help_menu.addAction("Инструкция")
        about_action.triggered.connect(self.show_about_dialog)

        # Главный сплиттер: слева — вкладки, справа — панель COM + версия
        splitter = QSplitter(Qt.Horizontal)

        # Вкладки (левая часть)
        tabs = QTabWidget()
        tabs.addTab(BlclTab(self), "BLCL Loader")
        tabs.addTab(StlinkTab(self), "STM32 ST-Link")
        tabs.addTab(XilinxTab(self), "Xilinx JTAG")
        tabs.addTab(JlinkTab(self), "J-Link Flash")
        splitter.addWidget(tabs)

        # Правая панель с COM-портом и информацией о прошивке (теперь только VersionPanel)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)

        # Вынесенная панель версии (теперь включает COM)
        self.version_panel = VersionPanel(self)
        right_layout.addWidget(self.version_panel)

        right_layout.addStretch()  # Чтобы всё прижалось к верху

        splitter.addWidget(right_panel)
        splitter.setSizes([1000, 350])  # Левая часть шире

        # Устанавливаем центральный виджет
        central_widget = QWidget()
        central_widget.setLayout(QVBoxLayout())
        central_widget.layout().addWidget(splitter)
        self.setCentralWidget(central_widget)
        apply_dark_theme()

        # Дополнительные стили для меню в темной теме
        self.setStyleSheet("""
            QMenuBar {
                background-color: #333333;
                color: white;
            }
            QMenuBar::item {
                background-color: #333333;
                color: white;
            }
            QMenuBar::item:selected {
                background-color: #4a90e2;
                color: white;
            }
            QMenu {
                background-color: #333333;
                color: white;
            }
            QMenu::item:selected {
                background-color: #4a90e2;
                color: white;
            }
        """)

    def show_about_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("О программе")
        dialog.setMinimumSize(600, 400)
        dialog_layout = QVBoxLayout()

        about_tabs = QTabWidget()
        # Вкладка Инструкция
        instr_widget = QWidget()
        instr_layout = QVBoxLayout()
        instr_text = QTextBrowser()
        instr_text.setOpenExternalLinks(True)
        instr_text.document().setDefaultStyleSheet("""
            body { color: white; }
            a:link { color: white; text-decoration: underline; }
            a:visited { color: white; }
            h1 { font-size: 2em; font-weight: bold; }
            h2 { font-size: 1.5em; font-weight: bold; }
            h3 { font-size: 1.2em; font-weight: bold; }
            p { margin-bottom: 10px; }
            ul { list-style-type: disc; margin-left: 20px; }
        """)
        instr_text.setHtml(self.load_documentation())
        instr_layout.addWidget(instr_text)
        instr_widget.setLayout(instr_layout)
        about_tabs.addTab(instr_widget, "Инструкция")

        # Вкладка Скачивания
        download_widget = QWidget()
        download_layout = QVBoxLayout()
        download_text = QTextBrowser()
        download_text.document().setDefaultStyleSheet("""
            body { color: white; }
            a:link { color: white; text-decoration: underline; }
            a:visited { color: white; }
            h2 { font-size: 1.5em; font-weight: bold; }
            p { margin-bottom: 10px; }
        """)
        download_text.setHtml("""
<h2>Ссылки на скачивание необходимых программ</h2>
<p><a href="https://www.segger.com/downloads/jlink/">SEGGER J-Link Software</a> - Программное обеспечение для отладчика J-Link, используется для прошивки через J-Link.</p>
<p><a href="https://www.st.com/en/development-tools/stm32cubeprog.html">STM32CubeProgrammer</a> - Инструмент для программирования STM32 микроконтроллеров, используется для ST-Link.</p>
<p><a href="https://www.xilinx.com/support/download.html">Xilinx Tools</a> - Инструменты для Xilinx FPGA, используются для JTAG прошивки.</p>
""")
        download_text.setOpenExternalLinks(True)
        download_layout.addWidget(download_text)
        download_widget.setLayout(download_layout)
        about_tabs.addTab(download_widget, "Скачивания")

        dialog_layout.addWidget(about_tabs)
        dialog.setLayout(dialog_layout)
        dialog.exec_()

    def load_documentation(self):
        doc_path = resource_path('resources/documentation.md')  # Путь к документации в resources
        if os.path.exists(doc_path):
            with open(doc_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
                # Конвертация Markdown в HTML с использованием вынесенной функции
                html = markdown_to_html(md_content)
                return html
        return "<p>Документация не найдена.</p>"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())