from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QShortcut,
)

from app.core.projects.io import load_project_file, save_project_file

from .canvas.canvas_scene import CanvasScene
from .canvas.model import BlockInstance
from .code_panel.code_panel import CodeDock
from .palette.palette import PaletteDock
from .widgets.canvas_view import CanvasView
from .widgets.serial_monitor import SerialMonitorDock


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arduino RoboLab (Preview)")
        self.resize(1280, 800)

        self.canvas_scene = CanvasScene()
        self.canvas_scene.blockAdded.connect(self._on_block_added)
        self.canvas_scene.blocksRemoved.connect(self._on_blocks_removed)
        self.canvas_scene.connectionsRemoved.connect(self._on_connections_removed)
        self.canvas_scene.connectionAdded.connect(self._on_connection_added)
        self.canvas_scene.statusMessage.connect(self._show_status_message)

        self.canvas_view = CanvasView(self.canvas_scene, self)
        self.setCentralWidget(self.canvas_view)

        self.palette_dock = PaletteDock(self)
        self.palette_dock.blockActivated.connect(self._add_block_from_palette)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)

        self.code_dock = CodeDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.code_dock)

        self.serial_dock = SerialMonitorDock(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.serial_dock)
        self.serial_dock.hide()

        self.palette_dock.visibilityChanged.connect(self._sync_palette_action)
        self.code_dock.visibilityChanged.connect(self._sync_code_action)
        self.serial_dock.visibilityChanged.connect(self._sync_monitor_action)
        self._sync_palette_action(self.palette_dock.isVisible())
        self._sync_code_action(self.code_dock.isVisible())
        self._sync_monitor_action(self.serial_dock.isVisible())

        self.block_library: List[dict] = []
        self.block_catalog: Dict[str, Dict[str, object]] = {}

        self._current_project_path: Optional[Path] = None
        self._current_board: str = "—"
        self._current_port: str = "—"
        self._project_dir: Path = Path.cwd()

        self.status_label = QLabel()
        self.statusBar().addPermanentWidget(self.status_label)

        self._setup_menu_bar()
        self._install_shortcuts()

        self._load_block_library()
        self.palette_dock.set_blocks(self.block_library)
        self.canvas_scene.set_block_catalog(self.block_catalog)

        self._update_status_counts()
        self.statusBar().showMessage("Готово", 2000)

    # ------------------------------------------------------------------ menu
    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Файл")
        act_open = QAction("Открыть…", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.setStatusTip("Открыть проект .robojson")
        act_open.triggered.connect(self.action_open)
        file_menu.addAction(act_open)

        self.act_save = QAction("Сохранить", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.setStatusTip("Сохранить текущий проект")
        self.act_save.triggered.connect(self.action_save)
        file_menu.addAction(self.act_save)

        act_save_as = QAction("Сохранить как…", self)
        act_save_as.setStatusTip("Сохранить проект под новым именем")
        act_save_as.triggered.connect(self.action_save_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_exit = QAction("Выход", self)
        act_exit.setStatusTip("Закрыть приложение")
        act_exit.triggered.connect(self.action_exit)
        file_menu.addAction(act_exit)

        device_menu = menu_bar.addMenu("Устройство")
        device_menu.addAction(QAction("Настройки устройства (скоро)", self, enabled=False))

        firmware_menu = menu_bar.addMenu("Прошивка")
        firmware_menu.addAction(QAction("Инструменты прошивки (скоро)", self, enabled=False))

        view_menu = menu_bar.addMenu("Вид")
        self.act_show_palette = QAction(
            "Показать палитру", self, checkable=True, checked=True
        )
        self.act_show_palette.setStatusTip("Показать или скрыть палитру блоков")
        self.act_show_palette.triggered.connect(self.action_toggle_palette)
        view_menu.addAction(self.act_show_palette)

        self.act_show_code = QAction(
            "Показать панель кода", self, checkable=True, checked=True
        )
        self.act_show_code.setStatusTip("Показать или скрыть панель кода")
        self.act_show_code.triggered.connect(self.action_toggle_code)
        view_menu.addAction(self.act_show_code)

        self.act_show_monitor = QAction(
            "Показать монитор порта", self, checkable=True, checked=False
        )
        self.act_show_monitor.setStatusTip("Показать или скрыть монитор последовательного порта")
        self.act_show_monitor.triggered.connect(self.action_toggle_monitor)
        view_menu.addAction(self.act_show_monitor)

        tools_menu = menu_bar.addMenu("Инструменты")
        act_generate = QAction("Сгенерировать скетч", self)
        act_generate.setShortcut("Ctrl+G")
        act_generate.setStatusTip("Сформировать предварительный Arduino-скетч")
        act_generate.triggered.connect(self.action_generate)
        tools_menu.addAction(act_generate)

        help_menu = menu_bar.addMenu("Справка")
        act_about = QAction("О программе", self)
        act_about.setStatusTip("Информация о приложении")
        act_about.triggered.connect(self.action_about)
        help_menu.addAction(act_about)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence.Delete, self, activated=self._delete_selection)
        QShortcut(QKeySequence.ZoomIn, self, activated=self._zoom_in)
        QShortcut(QKeySequence.ZoomOut, self, activated=self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self._reset_zoom)

    # ----------------------------------------------------------------- palette
    def _load_block_library(self) -> None:
        blocks_path = Path(__file__).resolve().parents[2] / "data" / "blocks" / "blocks.json"
        try:
            raw = json.loads(blocks_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("Неверный формат blocks.json")
        except Exception as exc:  # pragma: no cover - UI feedback path
            QMessageBox.critical(
                self,
                "Ошибка чтения палитры",
                f"Не удалось загрузить data/blocks/blocks.json\n{exc}",
            )
            self.block_library = []
            self.block_catalog = {}
            return

        self.block_library = raw
        self.block_catalog = self._build_block_catalog(raw)

    def _build_block_catalog(self, blocks: List[dict]) -> Dict[str, Dict[str, object]]:
        catalog: Dict[str, Dict[str, object]] = {}
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_id = str(block.get("id", "")).strip()
            if not block_id:
                continue
            ports = block.get("ports", {}) if isinstance(block.get("ports", {}), dict) else {}
            inputs = self._normalize_ports(ports.get("inputs"), prefix="in")
            outputs = self._normalize_ports(ports.get("outputs"), prefix="out")
            if not outputs:
                outputs = [{"name": "out", "type": "flow"}]
            params = block.get("params", []) if isinstance(block.get("params", []), list) else []
            default_params = {
                str(param.get("name")): param.get("default")
                for param in params
                if isinstance(param, dict) and param.get("name")
            }
            catalog[block_id] = {
                "title": block.get("title", block_id),
                "category": block.get("category"),
                "color": block.get("color"),
                "section": block.get("section"),
                "inputs": inputs,
                "outputs": outputs,
                "params": params,
                "default_params": default_params,
            }
        return catalog

    def _normalize_ports(self, payload, *, prefix: str) -> List[Dict[str, Optional[str]]]:
        result: List[Dict[str, Optional[str]]] = []
        if isinstance(payload, list):
            for index, item in enumerate(payload):
                if isinstance(item, dict):
                    name = str(item.get("name", f"{prefix}{index+1}"))
                    dtype = item.get("type")
                else:
                    name = f"{prefix}{index+1}"
                    dtype = None
                dtype_value = str(dtype).strip() if isinstance(dtype, str) else None
                result.append({"name": name, "type": dtype_value})
        return result

    # ----------------------------------------------------------------- actions
    def action_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект",
            str(self._project_dir),
            "RoboLab Project (*.robojson)",
        )
        if not path:
            return
        try:
            model, board, port = load_project_file(path)
        except Exception as exc:  # pragma: no cover - UI feedback path
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть проект\n{exc}")
            return
        self.canvas_scene.load_model(model)
        self._current_project_path = Path(path)
        self._project_dir = self._current_project_path.parent
        self._current_board = board or "—"
        self._current_port = port or "—"
        self._update_status_counts()
        self.statusBar().showMessage(f"Проект загружен: {self._current_project_path.name}", 4000)

    def action_save(self) -> None:
        if not self._current_project_path:
            self.action_save_as()
            return
        self._save_project(self._current_project_path)

    def action_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект",
            str(self._project_dir),
            "RoboLab Project (*.robojson)",
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != ".robojson":
            target = target.with_suffix(".robojson")
        self._project_dir = target.parent
        self._save_project(target)
        self._current_project_path = target

    def _save_project(self, path: Path) -> None:
        model = self.canvas_scene.model().clone()
        board = None if self._current_board in {None, "—"} else self._current_board
        port = None if self._current_port in {None, "—"} else self._current_port
        try:
            save_project_file(path, model, board=board, port=port)
        except Exception as exc:  # pragma: no cover - UI feedback path
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить проект\n{exc}")
            return
        self.statusBar().showMessage(f"Проект сохранён: {path.name}", 4000)

    def action_exit(self) -> None:
        self.close()

    def action_generate(self) -> None:
        sketch = self._generate_sketch_text()
        self.code_dock.set_code(sketch)
        self.statusBar().showMessage("Скетч обновлён", 3000)

    def action_toggle_palette(self, checked: bool) -> None:
        self.palette_dock.setVisible(checked)

    def action_toggle_code(self, checked: bool) -> None:
        self.code_dock.setVisible(checked)

    def action_toggle_monitor(self, checked: bool) -> None:
        self.serial_dock.setVisible(checked)
        if checked and self.serial_dock.isHidden():
            self.serial_dock.show()

    def action_about(self) -> None:
        QMessageBox.about(
            self,
            "Arduino RoboLab",
            "Arduino RoboLab (Preview)\nВерсия: 0.1.0",
        )

    # ----------------------------------------------------------- scene hooks
    def _on_block_added(self, block: BlockInstance) -> None:
        title = self.block_catalog.get(block.type_id, {}).get("title", block.type_id)
        self.statusBar().showMessage(f"Добавлен блок: {title}", 3000)
        self._update_status_counts()

    def _on_blocks_removed(self, count: int) -> None:
        if count:
            self.statusBar().showMessage(f"Удалено блоков: {count}", 3000)
            self._update_status_counts()

    def _on_connection_added(self, connection) -> None:
        self.statusBar().showMessage("Создано соединение", 2000)

    def _on_connections_removed(self, count: int) -> None:
        if count:
            self.statusBar().showMessage(f"Удалено соединений: {count}", 2000)

    def _show_status_message(self, text: str, timeout: int = 4000) -> None:
        self.statusBar().showMessage(text, timeout)

    def _add_block_from_palette(self, block_info: dict) -> None:
        block_id = block_info.get("id")
        if not block_id:
            return
        scene_pos = self.canvas_view.mapToScene(self.canvas_view.viewport().rect().center())
        self.canvas_scene.add_block_at(block_id, scene_pos)
        self._update_status_counts()

    # ------------------------------------------------------------ shortcuts
    def _delete_selection(self) -> None:
        removed = self.canvas_scene.remove_selected()
        if removed:
            self._update_status_counts()

    def _zoom_in(self) -> None:
        self.canvas_view.scale(1.15, 1.15)

    def _zoom_out(self) -> None:
        self.canvas_view.scale(1 / 1.15, 1 / 1.15)

    def _reset_zoom(self) -> None:
        self.canvas_view.resetTransform()

    # ------------------------------------------------------------ utilities
    def _generate_sketch_text(self) -> str:
        model = self.canvas_scene.model().clone()
        lines = [
            "// Arduino RoboLab preview sketch",
            "#include <Arduino.h>",
            "",
            "void setup() {",
            "  // TODO: заполнить настройку по данным блоков",
            "}",
            "",
            "void loop() {",
            "  // TODO: автоматическая генерация логики",
            "}",
            "",
            "// --- blocks on canvas ---",
        ]
        for block in model.blocks:
            params = ", ".join(f"{key}={value!r}" for key, value in block.params.items())
            if not params:
                params = "<без параметров>"
            lines.append(f"// {block.uid}: {block.type_id} ({params})")
        if not model.blocks:
            lines.append("// канва пуста")
        lines.append("")
        lines.append("// --- connections ---")
        for connection in model.connections:
            lines.append(
                f"// {connection.from_block_uid}:{connection.from_port} -> "
                f"{connection.to_block_uid}:{connection.to_port}"
            )
        if not model.connections:
            lines.append("// соединений нет")
        lines.append("")
        lines.append("// Конец предварительного скетча")
        return "\n".join(lines)

    def _update_status_counts(self) -> None:
        model = self.canvas_scene.model()
        count = len(model.blocks)
        board = self._current_board or "—"
        port = self._current_port or "—"
        self.status_label.setText(f"Блоков на сцене: {count} | Плата: {board} | Порт: {port}")

    # ---------------------------------------------------------- visibility
    def _sync_palette_action(self, visible: bool) -> None:
        if self.act_show_palette.isChecked() != visible:
            self.act_show_palette.setChecked(visible)

    def _sync_code_action(self, visible: bool) -> None:
        if self.act_show_code.isChecked() != visible:
            self.act_show_code.setChecked(visible)

    def _sync_monitor_action(self, visible: bool) -> None:
        if self.act_show_monitor.isChecked() != visible:
            self.act_show_monitor.setChecked(visible)

