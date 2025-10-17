from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QDrag  # QAction и QDrag в QtGui
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter

from .canvas.canvas_scene import CanvasScene
from .canvas.items import PortSpec
from .canvas.model import BlockInstance, ProjectModel
from .widgets.block_list import BlockListWidget  # предположительно есть
from .widgets.canvas_view import CanvasView      # предположительно есть
from .widgets.code_panel import CodePanel        # предположительно есть


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arduino RoboLab (Preview)")
        self.resize(1280, 800)

        # Центральный сплиттер: палитра | канва | код
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal, central)
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        # Левая палитра
        self.block_list = BlockListWidget(splitter)

        # Центр: канва (Scene + View)
        self.canvas_scene = CanvasScene()
        self.canvas_scene.blockAdded.connect(self._on_block_added)
        self.canvas_scene.blocksRemoved.connect(self._on_blocks_removed)
        self.canvas_scene.connectionsRemoved.connect(self._on_connections_removed)
        self.canvas_scene.connectionAdded.connect(self._on_connection_added)
        self.canvas_scene.statusMessage.connect(self._show_status_message)
        self.canvas_view = CanvasView(self.canvas_scene, splitter)
        self.canvas_view.setObjectName("canvasView")

        # Правая панель: код
        self.code_panel = CodePanel(splitter)

        splitter.setSizes([200, 400, 400])  # как в Codex-ветке

        # Каталог блоков (title + схема портов)
        self.block_catalog: Dict[str, Dict[str, object]] = {}
        self._load_block_catalog()

        # Привязать каталог к сцене
        self.canvas_scene.set_block_catalog(self.block_catalog)

        # Статус-бар
        self.statusBar().showMessage("Готово")

    # -------------------------------------------------------- catalog loading
    def _load_block_catalog(self) -> None:
        """
        Собираем каталог из данных (в MVP может быть упрощённым).
        Ожидаемый формат для сцен: {type_id: {"title": str, "inputs": [...], "outputs": [...]}}
        """
        # Пример минимального набора:
        blocks = [
            {"id": "EV_START", "title": "При старте", "ports": {"inputs": [], "outputs": [{"name": "out", "type": None}]}},
            {"id": "LS_LED_ON", "title": "LED ON", "ports": {"inputs": [{"name": "in", "type": "pulse"}], "outputs": []}},
            {"id": "CTL_IF", "title": "Если", "ports": {"inputs": [{"name": "in", "type": "flow"}], "outputs": [{"name": "then", "type": "flow"}, {"name": "else", "type": "flow"}]}},
        ]
        self.block_catalog = {}
        for block in blocks:
            block_id = str(block.get("id"))
            title = block.get("title", block_id)
            ports = block.get("ports", {}) if isinstance(block, dict) else {}
            inputs = self._normalize_ports(ports.get("inputs"), prefix="in") if isinstance(ports, dict) else []
            outputs = self._normalize_ports(ports.get("outputs"), prefix="out") if isinstance(ports, dict) else []
            if not outputs:
                outputs = [{"name": "out", "type": None}]
            self.block_catalog[block_id] = {
                "title": str(title),
                "inputs": inputs,
                "outputs": outputs,
            }

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

    # ------------------------------------------------------------ callbacks
    def _on_block_added(self, block: BlockInstance) -> None:
        title = self.block_catalog.get(block.type_id, {}).get("title", block.type_id)
        self.statusBar().showMessage(f"Добавлен блок: {title}", 4000)

    def _on_blocks_removed(self, count: int) -> None:
        self.statusBar().showMessage(f"Удалено блоков: {count}", 4000)

    def _on_connection_added(self, connection) -> None:
        # можно подсветить код или обновить панель свойств — пока заглушка
        pass

    def _on_connections_removed(self, count: int) -> None:
        self.statusBar().showMessage(f"Удалено соединений: {count}", 4000)

    def _show_status_message(self, text: str, timeout: int = 4000) -> None:
        self.statusBar().showMessage(text, timeout)
