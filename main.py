# main.py
# Главный файл запуска программы

import sys
import time
import serial.tools.list_ports
import serial
import os
import re
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
from ui.styles import apply_dark_theme

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLCL + STM32 + Xilinx Programmer")
        self.setWindowIcon(QIcon("icon.ico"))
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

        # Правая панель с COM-портом и информацией о прошивке
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)

        # Группа COM-порта
        com_group = QGroupBox("COM Settings")
        com_vbox = QVBoxLayout()

        # Строка COM-порт
        com_row = QHBoxLayout()
        com_row.addWidget(QLabel("COM-порт:"))
        self.com_combo = QComboBox()
        self.refresh_com_ports()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_com_ports)
        com_row.addWidget(self.com_combo)
        com_row.addWidget(refresh_btn)
        com_vbox.addLayout(com_row)

        # Строка Baudrate
        baud_row = QHBoxLayout()
        baud_row.addWidget(QLabel("Baudrate:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud_combo.setCurrentText('115200')
        baud_row.addWidget(self.baud_combo)
        com_vbox.addLayout(baud_row)

        com_group.setLayout(com_vbox)
        right_layout.addWidget(com_group)

        # Кнопка подключения
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.setFixedHeight(40)
        self.connect_btn.clicked.connect(self.toggle_com_connection)
        right_layout.addWidget(self.connect_btn)

        # Текущая информация о прошивке
        current_group = QGroupBox("Current Firmware Info")
        current_vbox = QVBoxLayout()
        self.version_label = QLabel("Версия прошивки: Неизвестно")
        self.date_label = QLabel("Дата прошивки: Неизвестно")
        current_vbox.addWidget(self.version_label)
        current_vbox.addWidget(self.date_label)
        current_group.setLayout(current_vbox)
        right_layout.addWidget(current_group)

        # Кнопка обновления информации
        self.update_info_btn = QPushButton("Обновить информацию")
        self.update_info_btn.setEnabled(False)
        self.update_info_btn.clicked.connect(self.update_firmware_info)
        right_layout.addWidget(self.update_info_btn)

        # Новая информация о прошивке
        new_group = QGroupBox("New Firmware Info")
        new_vbox = QVBoxLayout()

        version_row = QHBoxLayout()
        version_row.addWidget(QLabel("Новая версия:"))
        self.version_input = QLineEdit()
        version_row.addWidget(self.version_input)
        new_vbox.addLayout(version_row)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Новая дата:"))
        self.date_input = QLineEdit(time.strftime("%Y-%m-%d"))
        date_row.addWidget(self.date_input)
        new_vbox.addLayout(date_row)

        new_group.setLayout(new_vbox)
        right_layout.addWidget(new_group)

        # Кнопка установки новой информации
        self.set_info_btn = QPushButton("Установить информацию")
        self.set_info_btn.setEnabled(False)
        self.set_info_btn.clicked.connect(self.set_firmware_info)
        right_layout.addWidget(self.set_info_btn)

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

        self.serial_port = None
        self.is_com_connected = False

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
        doc_path = 'documentation.md'
        if os.path.exists(doc_path):
            with open(doc_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
                # Простая конвертация Markdown в HTML для отображения
                html = self.markdown_to_html(md_content)
                return html
        return "<p>Документация не найдена.</p>"

    def markdown_to_html(self, md):
        # Экранирование специальных символов
        md = re.sub(r'&', '&amp;', md)
        md = re.sub(r'<', '&lt;', md)
        md = re.sub(r'>', '&gt;', md)

        # Ссылки [text](url)
        md = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', md)

        # Жирный **text**
        md = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', md)

        # Курсив *text*
        md = re.sub(r'\*(.*?)\*', r'<i>\1</i>', md)

        # Обработка строк
        lines = md.split('\n')
        html_lines = []
        in_list = False
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<p></p>')
                continue
            if line.startswith('# '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<h1>' + line[2:].strip() + '</h1>')
            elif line.startswith('## '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<h2>' + line[3:].strip() + '</h2>')
            elif line.startswith('### '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<h3>' + line[4:].strip() + '</h3>')
            elif line.startswith('- ') or line.startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append('<li>' + line[2:].strip() + '</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<p>' + line + '</p>')
        if in_list:
            html_lines.append('</ul>')
        return ''.join(html_lines)

    def refresh_com_ports(self):
        self.com_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.com_combo.addItem(port.device)

    def toggle_com_connection(self):
        if self.is_com_connected:
            self.disconnect_com()
        else:
            self.connect_com()

    def connect_com(self):
        com_port = self.com_combo.currentText()
        baud = int(self.baud_combo.currentText())
        if not com_port:
            QMessageBox.warning(self, "Ошибка", "Выберите COM-порт!")
            return
        try:
            self.serial_port = serial.Serial(com_port, baudrate=baud, timeout=1)  # Настройте baudrate по необходимости
            self.connect_btn.setText("Отключиться")
            self.update_info_btn.setEnabled(True)
            self.set_info_btn.setEnabled(True)
            self.is_com_connected = True
            QMessageBox.information(self, "Успех", f"Подключено к {com_port}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось подключиться: {e}")

    def disconnect_com(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        self.connect_btn.setText("Подключиться")
        self.update_info_btn.setEnabled(False)
        self.set_info_btn.setEnabled(False)
        self.is_com_connected = False
        self.version_label.setText("Версия прошивки: Неизвестно")
        self.date_label.setText("Дата прошивки: Неизвестно")
        QMessageBox.information(self, "Успех", "Отключено от COM-порта")

    def update_firmware_info(self):
        if not self.is_com_connected:
            return
        try:
            # Предполагаем команды для чтения версии и даты (замените на реальные)
            self.serial_port.write(b'VER?\n')  # Команда для версии
            version = self.serial_port.readline().decode().strip()
            self.serial_port.write(b'DATE?\n')  # Команда для даты
            date = self.serial_port.readline().decode().strip()

            self.version_label.setText(f"Версия прошивки: {version}")
            self.date_label.setText(f"Дата прошивки: {date}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить информацию: {e}")

    def set_firmware_info(self):
        if not self.is_com_connected:
            return
        version = self.version_input.text().strip()
        date = self.date_input.text().strip()
        if not version or not date:
            QMessageBox.warning(self, "Ошибка", "Заполните поля версии и даты!")
            return
        try:
            # Предполагаем команды для установки версии и даты (замените на реальные)
            self.serial_port.write(f'SET_VER {version}\n'.encode())
            response = self.serial_port.readline().decode().strip()
            # self.log.append(response)  # Лог, если нужно
            self.serial_port.write(f'SET_DATE {date}\n'.encode())
            response = self.serial_port.readline().decode().strip()
            # self.log.append(response)
            QMessageBox.information(self, "Успех", "Информация установлена!")
            self.update_firmware_info()  # Обновляем отображение
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось установить информацию: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())