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
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QActionGroup
from core.blcl_protocol import FlashThread
from core.jlink_flash import JLinkFlashThread, JLinkEraseThread
from core.stlink_flash import STM32FlashThread
from core.xilinx_flash import XilinxFlashThread
from ui.blcl_tab import BlclTab
from ui.stlink_tab import StlinkTab
from ui.xilinx_tab import XilinxTab
from ui.jlink_tab import JlinkTab
from ui.version_tab import VersionPanel  # Теперь включает COM
from ui.styles import THEME, apply_dark_theme, load_accent, save_accent
from ui.kit import theme as T
from ui.kit.appicon import app_icon
from ui.kit.glass import GlassRoot
from ui.kit.winstyle import dark_titlebars, taskbar_identity
from utils.markdown_formatter import markdown_to_html  # Новый импорт
from utils.helpers import resource_path, data_path

APP_TITLE = "BLCL Programmer"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(app_icon(THEME))
        self.resize(1400, 860)

        self._build_menu()

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
        right_layout.setContentsMargins(4, 0, 0, 0)

        self.version_panel = VersionPanel(self)
        right_layout.addWidget(self.version_panel)

        right_layout.addStretch()  # Чтобы всё прижалось к верху

        splitter.addWidget(right_panel)
        splitter.setSizes([1000, 350])  # Левая часть шире

        # Подложка окна — фон кита (градиент, акцентные пятна, зерно);
        # setStyleSheet ей не задаём, иначе обесцветится всё поддерево
        central_widget = GlassRoot(THEME)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(12, 10, 12, 10)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

        self.statusBar().showMessage("Готов к работе")
        self._set_accent(load_accent(), save=False)

    # ---------------- меню: на виду частое, в меню редкое ----------------
    def _build_menu(self):
        mb = self.menuBar()

        m_file = mb.addMenu("Файл")
        m_file.addAction("Папка с прошивками", self._open_firmware_dir)
        m_file.addSeparator()
        m_file.addAction("Выход", self.close)

        m_view = mb.addMenu("Вид")
        m_color = m_view.addMenu("Цвет элементов")
        self._accent_group = QActionGroup(self)
        self._accent_group.setExclusive(True)
        for name, color in T.ACCENTS:
            act = QAction(name, self, checkable=True)
            act.setData(color)
            act.triggered.connect(lambda _c, c=color: self._set_accent(c))
            self._accent_group.addAction(act)
            m_color.addAction(act)

        m_help = mb.addMenu("Помощь")
        m_help.addAction("Инструкция", self.show_about_dialog)
        m_help.addAction("О программе", self._about)

    def _open_firmware_dir(self):
        path = data_path("firmware")
        if os.path.isdir(path):
            os.startfile(path)
        else:
            QMessageBox.information(self, APP_TITLE,
                                    f"Папка не найдена:\n{path}")

    def _about(self):
        QMessageBox.about(
            self, APP_TITLE,
            f"<b>{APP_TITLE}</b><br><br>"
            "Прошивка плат: BLCL по COM-порту, STM32 через ST-Link,<br>"
            "Xilinx по JTAG, микроконтроллеры через J-Link.<br>"
            "Оформление — по UI_KIT.md.<br><br>"
            f"<span style='color:{T.TEXT_DIM}'>github.com/mrCtik/Programmer"
            "</span>")

    # ---------------- акцент ----------------
    def _set_accent(self, color, save=True):
        """Один акцент на всю программу. QSS перестраивается целиком,
        нарисованное руками (фон, иконка) — обновляется отдельно."""
        apply_dark_theme(color)
        icon = app_icon(THEME)
        self.setWindowIcon(icon)
        for root in self.findChildren(GlassRoot):
            root.update()
        for act in self._accent_group.actions():
            act.setChecked(str(act.data()).lower() == THEME.accent.lower())
        if save:
            save_accent(THEME.accent)
        self.update()

    def closeEvent(self, event):
        """Закрытие посреди прошивки раньше уничтожало работающий QThread
        («QThread: Destroyed while thread is still running») и бросало
        плату с недописанным образом. Теперь спрашиваем и ждём."""
        # спрашиваем только про работу с платой; проверки программатора
        # и поиск утилит останавливаем молча
        running = [t for t in self._worker_threads() if t.isRunning()]
        busy = [t for t in running if isinstance(t, self.FLASH_THREADS)]
        for t in running:
            if t not in busy:
                t.requestInterruption()
        if busy:
            answer = QMessageBox.question(
                self, APP_TITLE,
                "Идёт работа с платой (прошивка или стирание).\n\n"
                "Прервать её и выйти? Плата может остаться с неполной\n"
                "прошивкой.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            for t in busy:
                t.requestInterruption()
                if not t.wait(5000):
                    t.terminate()      # последнее средство, но лучше, чем
                    t.wait(1000)       # уничтожение работающего QThread
        self._close_serial()
        event.accept()

    FLASH_THREADS = (FlashThread, JLinkFlashThread, JLinkEraseThread,
                     STM32FlashThread, XilinxFlashThread)

    # потоки вкладок живут в своих атрибутах: с parent=self их видно
    # через findChildren, созданные без родителя — только по именам
    THREAD_ATTRS = ('thread', 'flash_thread', 'stm32_thread',
                    'check_thread', 'target_thread', 'search_thread')

    def _worker_threads(self):
        found = list(self.findChildren(QThread))
        tabs = self.findChildren((BlclTab, StlinkTab, XilinxTab, JlinkTab,
                                  VersionPanel))
        for tab in tabs:
            for name in self.THREAD_ATTRS:
                t = getattr(tab, name, None)
                if isinstance(t, QThread) and t not in found:
                    found.append(t)
        return found

    def _close_serial(self):
        panel = getattr(self, 'version_panel', None)
        port = getattr(panel, 'serial_port', None)
        if port:
            try:
                port.close()
            except Exception:
                pass
            panel.serial_port = None
            panel.is_com_connected = False

    def show_about_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Инструкция")
        dialog.setMinimumSize(700, 500)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        glass = GlassRoot(THEME, dialog)
        dialog_layout.addWidget(glass)
        inner = QVBoxLayout(glass)
        inner.setContentsMargins(12, 12, 12, 12)

        about_tabs = QTabWidget()
        # Вкладка Инструкция
        instr_widget = QWidget()
        instr_layout = QVBoxLayout()
        instr_text = QTextBrowser()
        instr_text.setOpenExternalLinks(True)
        instr_text.document().setDefaultStyleSheet(f"""
            body {{ color: {T.TEXT_SOFT}; }}
            a:link {{ color: {THEME.n1}; text-decoration: underline; }}
            a:visited {{ color: {THEME.n2}; }}
            h1 {{ font-size: 2em; font-weight: bold; color: {T.TEXT}; }}
            h2 {{ font-size: 1.5em; font-weight: bold; color: {T.TEXT}; }}
            h3 {{ font-size: 1.2em; font-weight: bold; color: {T.TEXT}; }}
            p {{ margin-bottom: 10px; }}
            ul {{ list-style-type: disc; margin-left: 20px; }}
        """)
        instr_text.setHtml(self.load_documentation())
        instr_layout.addWidget(instr_text)
        instr_widget.setLayout(instr_layout)
        about_tabs.addTab(instr_widget, "Инструкция")

        # Вкладка Скачивания
        download_widget = QWidget()
        download_layout = QVBoxLayout()
        download_text = QTextBrowser()
        download_text.document().setDefaultStyleSheet(f"""
            body {{ color: {T.TEXT_SOFT}; }}
            a:link {{ color: {THEME.n1}; text-decoration: underline; }}
            a:visited {{ color: {THEME.n2}; }}
            h2 {{ font-size: 1.5em; font-weight: bold; color: {T.TEXT}; }}
            p {{ margin-bottom: 10px; }}
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

        inner.addWidget(about_tabs)
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
    # Без этого Windows считает окно частью python.exe и показывает
    # на панели задач его значок
    taskbar_identity("IMX.BLCLProgrammer")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_theme(load_accent())
    dark_titlebars(app)     # тёмные рамки всем окнам, включая диалоги

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())