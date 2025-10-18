"""Проверки построения главного меню и хоткеев."""
from __future__ import annotations

from typing import Iterator

import pytest

try:  # pragma: no cover - skip on headless environments without GL
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QApplication
except ImportError as exc:  # pragma: no cover - import guard
    pytest.skip(f"PySide6 runtime is not available: {exc}", allow_module_level=True)

from app.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def main_window(qt_app: QApplication) -> Iterator[MainWindow]:
    window = MainWindow()
    yield window
    window.close()


def test_menu_titles_present(main_window: MainWindow) -> None:
    titles = [action.text().replace("&", "") for action in main_window.menuBar().actions()]
    for title in ["Файл", "Правка", "Устройство", "Прошивка", "Вид", "Инструменты", "Справка"]:
        assert title in titles


def test_core_actions_have_shortcuts(main_window: MainWindow) -> None:
    sequences = {
        shortcut.key().toString(QKeySequence.SequenceFormat.PortableText)
        for shortcut in main_window._shortcuts
    }
    assert {"Ctrl+N", "Ctrl+O", "Ctrl+S"}.issubset(sequences)
    assert any(seq in sequences for seq in {"Del", "Delete"})


def test_menu_actions_configured(main_window: MainWindow) -> None:
    assert main_window.act_new_project.text() == "Новый проект"
    assert main_window.act_generate_code.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+G"
    assert main_window.act_show_palette.isCheckable()
    assert main_window.act_theme_dark.isCheckable()
    assert main_window.act_theme_light.isCheckable()
    assert main_window.act_select_board.isEnabled()
    assert main_window.act_tools_simulator.text() == "Симулятор 2D"
