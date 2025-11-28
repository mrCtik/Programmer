# ui/styles.py
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

def apply_dark_theme():
    app = QApplication.instance()
    if not app:
        return

    # Палитра
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(40, 40, 40))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(60, 60, 60))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)

    # CSS
    app.setStyleSheet("""
        QWidget { background-color: #2d2d2d; color: white; }
        QGroupBox { 
            border: 1px solid #555; 
            border-radius: 6px; 
            margin: 6px; 
            padding-top: 10px; 
            background-color: #333;
        }
        QGroupBox::title { 
            subcontrol-origin: margin; 
            left: 10px; 
            padding: 0 5px; 
            color: #ddd; 
            font-weight: bold; 
        }
        QPushButton { 
            background-color: #007bff; 
            color: white; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 6px; 
            font-weight: bold; 
        }
        QPushButton:hover { background-color: #0056b3; }
        QPushButton:disabled { background-color: #555; }
        QPushButton#danger { background-color: #dc3545; }
        QPushButton#danger:hover { background-color: #c82333; }
        
        QLineEdit, QTextEdit, QComboBox { 
            background-color: #1e1e1e; 
            color: white; 
            border: 1px solid #555; 
            border-radius: 6px; 
            padding: 8px; 
        }
        QComboBox::drop-down { border: none; }
        QComboBox::down-arrow { image: none; border: none; }
        
        QLabel { color: #ddd; font-weight: bold; }
        
        QProgressBar { 
            background-color: #1e1e1e; 
            border: 1px solid #555; 
            border-radius: 6px; 
            text-align: center; 
        }
        QProgressBar::chunk { background-color: #00ff00; border-radius: 5px; }
        
        QTabWidget::pane { border: 1px solid #555; background: #2d2d2d; }
        QTabBar::tab { 
            background: #333; 
            color: white; 
            padding: 10px 20px; 
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }
        QTabBar::tab:selected { background: #007bff; }
    """)