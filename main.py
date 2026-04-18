"""Тонкий launcher для PyInstaller и обратной совместимости.

Весь код живёт в src/bot/. Этот файл — точка входа для:
    python main.py
    PyInstaller при сборке в EXE

Для разработки рекомендуется использовать:
    python -m bot
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if __name__ == "__main__":
    from bot.__main__ import run
    run()
