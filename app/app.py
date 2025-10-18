"""Точка входа графического интерфейса Arduino RoboLab."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtWidgets import QApplication


# Убедимся, что корень проекта в sys.path для локального запуска
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT.parent) not in sys.path:
    sys.path.append(str(PROJECT_ROOT.parent))


def main() -> int:
    """Запустить предварительную версию GUI."""
    app = QApplication(sys.argv)

    blocks_path = PROJECT_ROOT.parent / "data" / "blocks" / "blocks.json"
    print(f"[RoboLab] PySide6 version: {PYSIDE_VERSION}")
    print(f"[RoboLab] Blocks catalog: {blocks_path}")

    from app.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
