# logic/__init__.py
import importlib
import os
from typing import Optional

# Последняя ошибка импорта: ImportError ловится целиком, и ошибка
# внутри самого модуля логики выглядела как «логика не найдена».
last_error = ""


def get_logic_module(logic_type: str):
    """Динамически импортирует модуль логики по типу"""
    global last_error
    module_name = f"logic.logic_{logic_type}"
    try:
        last_error = ""
        return importlib.import_module(module_name)
    except ImportError as e:
        last_error = str(e)
        print(f"[logic] не удалось загрузить {module_name}: {e}")
        return None