"""Главное окно предварительной версии Arduino RoboLab."""
from __future__ import annotations
from pathlib import Path
import json
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction  # <-- Важно: QAction из QtGui
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QMenuBar, QStatusBar,
    QListWidget, QListWidgetItem, QTextEdit, QSplitter, QMessageBox, QFileDialog,
    QToolBar, QPushButton
)


class MainWindow(QMainWindow):
    """Минимальный GUI с палитрой блоков и генерацией кода."""

    WINDOW_TITLE = "Arduino RoboLab (Preview)"

    def __init__(self) -> None:
        super().__init__()
        self.blocks: List[dict] = []
        self.blocks_path = (
            Path(__file__).resolve().parents[2] / "data" / "blocks" / "blocks.json"
        )
        self._create_ui()
        self._create_menu()
        self.statusBar()
        self._load_blocks()

    # ------------------------------------------------------------------ UI
    def _create_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal, self)

        self.block_list = QListWidget(splitter)
        self.block_list.setObjectName("blockList")

        self.canvas_placeholder = QLabel("Канва (в разработке)", splitter)
        self.canvas_placeholder.setAlignment(Qt.AlignCenter)
        self.canvas_placeholder.setObjectName("canvasPlaceholder")

        self.code_view = QTextEdit(splitter)
        self.code_view.setReadOnly(True)
        self.code_view.setObjectName("codeView")

        splitter.setSizes([200, 400, 400])
        self.setCentralWidget(splitter)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(1200, 700)

    def _create_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Файл")
        new_action = QAction("Новый", self)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("Открыть…", self)
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        save_action = QAction("Сохранить", self)
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        build_menu = menu_bar.addMenu("Сборка")
        generate_action = QAction("Сгенерировать код", self)
        generate_action.triggered.connect(self._generate_code)
        build_menu.addAction(generate_action)

        help_menu = menu_bar.addMenu("Справка")
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------- menu slots
    def _new_project(self) -> None:
        self.statusBar().showMessage("Создан новый проект (заглушка)", 3000)
        self.code_view.clear()

    def _open_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект",
            str(Path.home()),
            "Arduino RoboLab (*.robojson)",
        )
        if not file_path:
            return
        self.statusBar().showMessage(f"Загружен проект: {Path(file_path).name}", 5000)

    def _save_project(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект",
            str(Path.home()),
            "Arduino RoboLab (*.robojson)",
        )
        if not file_path:
            return
        self.statusBar().showMessage(f"Проект сохранён: {Path(file_path).name}", 5000)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "О программе",
            "Arduino RoboLab — предварительная версия визуального редактора.",
        )

    # -------------------------------------------------------------- data load
    def _load_blocks(self) -> None:
        if not self.blocks_path.exists():
            self.statusBar().showMessage(
                "Не найден файл blocks.json — отображается пустая палитра.", 8000
            )
            return
        try:
            raw_text = self.blocks_path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
            self.blocks = list(payload.get("blocks", []))
        except (OSError, json.JSONDecodeError) as exc:
            self.statusBar().showMessage(
                f"Ошибка загрузки blocks.json: {exc}", 8000
            )
            return

        self.block_list.clear()
        for block in self.blocks:
            title = block.get("title") or block.get("name") or block.get("id")
            item = QListWidgetItem(str(title))
            item.setData(Qt.UserRole, block)
            self.block_list.addItem(item)
        self.statusBar().showMessage(
            f"Загружено блоков: {self.block_list.count()}", 5000
        )

    # ---------------------------------------------------------- code generate
    def _generate_code(self) -> None:
        sketch = self._default_sketch()
        try:
            # TODO: integrate with app.core.generator.codegen
            from app.core.generator import codegen as _codegen_module

            generate_code = getattr(_codegen_module, "generate_code", None)
            if callable(generate_code):
                sketch = str(generate_code(None))  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 - демонстрация статуса ошибки
            self.statusBar().showMessage(
                f"Используется базовый шаблон скетча: {exc}", 8000
            )
        finally:
            self.code_view.setPlainText(sketch)

    @staticmethod
    def _default_sketch() -> str:
        return (
            "#include <Arduino.h>\n\n"
            "void setup() {\n"
            "  // TODO: добавить блоки и инициализацию\n"
            "}\n\n"
            "void loop() {\n"
            "  // TODO: добавить основную логику\n"
            "}\n"
        )
