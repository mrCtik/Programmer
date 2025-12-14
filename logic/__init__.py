# logic/__init__.py
import importlib
import os
from typing import Optional

def get_logic_module(logic_type: str):
    """Динамически импортирует модуль логики по типу"""
    module_name = f"logic.logic_{logic_type}"
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None