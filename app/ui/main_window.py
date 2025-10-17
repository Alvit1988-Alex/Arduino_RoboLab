"""Главное окно предварительной версии Arduino RoboLab."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QAction, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTextEdit,
)

from app.ui.canvas import CanvasScene, CanvasView, ProjectModel
from app.ui.canvas.canvas_scene import MIME_TYPE


class BlockListWidget(QListWidget):
    """Список блоков, поддерживающий drag-and-drop на канву."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("blockList")
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def startDrag(self, supported_actions) -> None:  # type: ignore[override]
        del supported_actions
        item = self.currentItem()
        if item is None:
            return
        block_payload = item.data(Qt.UserRole) or {}
        block_id = block_payload.get("id") if isinstance(block_payload, dict) else None
        if not block_id:
            return
        mime_data = QMimeData()
        mime_data.setData(MIME_TYPE, str(block_id).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction)


class MainWindow(QMainWindow):
    """Минимальный GUI с палитрой блоков, канвой и генерацией кода."""

    WINDOW_TITLE = "Arduino RoboLab (Preview)"

    def __init__(self) -> None:
        super().__init__()
        self.blocks: List[dict] = []
        self.block_titles: Dict[str, str] = {}
        self.blocks_path = (
            Path(__file__).resolve().parents[2] / "data" / "blocks" / "blocks.json"
        )
        self.project_path: Optional[Path] = None
        self._create_ui()
        self._create_menu()
        self.statusBar()
        self._load_blocks()

    # ------------------------------------------------------------------ UI
    def _create_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal, self)

        self.block_list = BlockListWidget(splitter)

        self.canvas_scene = CanvasScene()
        self.canvas_scene.blockAdded.connect(self._on_block_added)
        self.canvas_scene.blocksRemoved.connect(self._on_blocks_removed)
        self.canvas_view = CanvasView(self.canvas_scene, splitter)
        self.canvas_view.setObjectName("canvasView")

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
        self.canvas_scene.reset()
        self.project_path = None
        self.code_view.clear()
        self.statusBar().showMessage("Создан новый проект", 4000)

    def _open_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект",
            str(Path.home()),
            "Arduino RoboLab (*.robojson)",
        )
        if not file_path:
            return
        path = Path(file_path)
        try:
            model = ProjectModel.load_from_file(path)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось открыть проект: {exc}",
            )
            self.statusBar().showMessage(f"Ошибка открытия проекта: {exc}", 8000)
            return
        self.canvas_scene.load_model(model)
        self.project_path = path
        self.statusBar().showMessage(f"Загружен проект: {path.name}", 5000)

    def _save_project(self) -> None:
        target_path = self.project_path
        if target_path is None:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить проект",
                str(Path.home()),
                "Arduino RoboLab (*.robojson)",
            )
            if not file_path:
                return
            target_path = Path(file_path)
        model = self.canvas_scene.export_model()
        try:
            model.save_to_file(target_path)
        except OSError as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить проект: {exc}")
            self.statusBar().showMessage(f"Ошибка сохранения: {exc}", 8000)
            return
        self.project_path = target_path
        self.statusBar().showMessage(f"Проект сохранён: {target_path.name}", 5000)

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

        self.block_titles = {}
        self.block_list.clear()
        for block in self.blocks:
            block_id = str(block.get("id", uuid.uuid4().hex))
            title = block.get("title") or block.get("name") or block_id
            item = QListWidgetItem(str(title))
            item.setData(Qt.UserRole, {"id": block_id, "title": str(title)})
            item.setToolTip(str(block.get("description", "")))
            self.block_list.addItem(item)
            self.block_titles[block_id] = str(title)
        self.canvas_scene.set_block_catalog(self.block_titles)
        self.statusBar().showMessage(
            f"Загружено блоков: {self.block_list.count()}", 5000
        )

    # ---------------------------------------------------------- code generate
    def _generate_code(self) -> None:
        project_model = self.canvas_scene.export_model()
        sketch = self._default_sketch(project_model)
        try:
            # TODO: integrate with app.core.generator.codegen
            from app.core.generator.codegen import generate_code  # type: ignore

            sketch = str(generate_code(project_model.to_dict()))
            self.statusBar().showMessage("Скетч сгенерирован", 4000)
        except ImportError as exc:
            self.statusBar().showMessage(
                f"Генератор недоступен, используется шаблон: {exc}", 8000
            )
        except Exception as exc:  # noqa: BLE001 - показать ошибку генерации
            self.statusBar().showMessage(
                f"Ошибка генерации, использован шаблон: {exc}", 8000
            )
            sketch = self._default_sketch(project_model)
        self.code_view.setPlainText(sketch)

    def _default_sketch(self, model: ProjectModel) -> str:
        block_types = [block.type_id for block in model.blocks]
        comment = (
            "// Блоки в проекте: " + ", ".join(block_types)
            if block_types
            else "// Блоков в проекте нет"
        )
        return (
            "#include <Arduino.h>\n\n"
            "void setup() {\n"
            "  // TODO: добавить блоки и инициализацию\n"
            "}\n\n"
            "void loop() {\n"
            f"  {comment}\n"
            "}\n"
        )

    # --------------------------------------------------------------- callbacks
    def _on_block_added(self, block) -> None:
        title = self.block_titles.get(block.type_id, block.type_id)
        self.statusBar().showMessage(f"Добавлен блок: {title}", 4000)

    def _on_blocks_removed(self, count: int) -> None:
        self.statusBar().showMessage(f"Удалено блоков: {count}", 4000)
