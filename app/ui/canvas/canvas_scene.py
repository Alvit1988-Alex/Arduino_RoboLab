"""Graphics scene implementing drag-and-drop and project synchronisation."""
from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsScene

from .items import BlockItem, ConnectionItem, PortItem, PortSpec, GRID_SIZE
from .model import BlockInstance, ConnectionModel, ProjectModel

MIME_TYPE = "application/x-robolab-block-id"


class CanvasScene(QGraphicsScene):
    """Canvas with drag & drop support for RoboLab blocks."""

    blockAdded = Signal(BlockInstance)
    blocksRemoved = Signal(int)
    connectionsRemoved = Signal(int)
    connectionAdded = Signal(ConnectionModel)
    statusMessage = Signal(str, int)

    def __init__(self, *, parent=None) -> None:
        super().__init__(parent)
        self.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self._project_model = ProjectModel()
        self._block_items: Dict[str, BlockItem] = {}
        self._connection_items: Dict[str, ConnectionItem] = {}
        self._block_catalog: Dict[str, Dict[str, object]] = {}
        self._grid_size = GRID_SIZE
        self._accept_drops_enabled = False
        self._connection_preview: Optional[ConnectionItem] = None
        self._connection_start_port: Optional[PortItem] = None
        self.setBackgroundBrush(QColor("#202020"))
        self.setAcceptDrops(True)

    # ------------------------------------------------------------ catalog/model
    def set_block_catalog(self, catalog: Dict[str, Dict[str, object]]) -> None:
        self._block_catalog = dict(catalog)

    def load_model(self, model: ProjectModel) -> None:
        self._cancel_connection_preview()
        self.clear()
        self._block_items.clear()
        self._connection_items.clear()
        self._project_model = model.clone()
        for block in self._project_model.blocks:
            self._create_item_for_block(block)
        for connection in list(self._project_model.connections):
            if self._create_connection_item(connection) is None:
                self._project_model.remove_connection(connection)
        self.update()

    def reset(self) -> None:
        self.load_model(ProjectModel())

    def export_model(self) -> ProjectModel:
        return self._project_model.clone()

    # ----------------------------------------------------------------- actions
    def add_block_from_palette(self, type_id: str, pos: QPointF) -> Optional[BlockItem]:
        if not type_id:
            return None
        return self._add_block(type_id=type_id, pos=pos)

    def remove_selected_blocks(self) -> int:
        removed_blocks = 0
        removed_connections = 0
        for item in list(self.selectedItems()):
            if isinstance(item, BlockItem):
                uid = item.block.uid
                removed_connections += self._remove_connections_for_block(uid)
                self._project_model.remove_block(uid)
                self._block_items.pop(uid, None)
                self.removeItem(item)
                removed_blocks += 1
            elif isinstance(item, ConnectionItem):
                if self._remove_connection_item(item):
                    removed_connections += 1
        if removed_blocks:
            self.blocksRemoved.emit(removed_blocks)
            self._emit_status(f"Удалено блоков: {removed_blocks}")
        if removed_connections:
            self.connectionsRemoved.emit(removed_connections)
            self._emit_status(f"Удалено соединений: {removed_connections}")
        return removed_blocks + removed_connections

    # ------------------------------------------------------------------ Qt DnD
    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self.acceptsDrops() and event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.acceptsDrops() and event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        if not self.acceptsDrops():
            super().dropEvent(event)
            return
        mime = event.mimeData()
        if not mime.hasFormat(MIME_TYPE):
            super().dropEvent(event)
            return
        try:
            raw_bytes = bytes(mime.data(MIME_TYPE))
            block_id = raw_bytes.decode("utf-8")
        except Exception:  # noqa: BLE001 - защитный fallback
            block_id = ""
        self.add_block_from_palette(block_id, event.scenePos())
        event.acceptProposedAction()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._connection_preview is not None:
            self._connection_preview.set_temp_end(event.scenePos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if (
            self._connection_preview is not None
            and event.button() == Qt.LeftButton
            and not event.isAccepted()
        ):
            self._emit_status("Соединение отменено")
            self._cancel_connection_preview()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ---------------------------------------------------------------- helpers
    def _create_item_for_block(self, block: BlockInstance, title: Optional[str] = None) -> BlockItem:
        metadata = self._block_catalog.get(block.type_id, {})
        final_title = title or str(metadata.get("title", block.type_id))
        ports_in = self._make_port_specs(metadata.get("inputs", []), direction="in")
        ports_out = self._make_port_specs(metadata.get("outputs", []), direction="out")
        if not ports_out:
            ports_out = [PortSpec(name="out", direction="out", dtype=None)]
        try:
            item = BlockItem(
                block,
                title=final_title,
                ports_in=ports_in,
                ports_out=ports_out,
                grid_size=self._grid_size,
            )
        except TypeError:
            item = BlockItem(block)  # type: ignore[call-arg] - совместимость со старыми версиями
        self.addItem(item)
        item.setPos(block.x, block.y)
        self._block_items[block.uid] = item
        return item

    def _make_port_specs(
        self, payload: Iterable[Dict[str, object]], *, direction: str
    ) -> List[PortSpec]:
        result: List[PortSpec] = []
        for index, raw in enumerate(payload or []):
            if isinstance(raw, dict):
                name = str(raw.get("name", f"{direction}{index+1}"))
                dtype = raw.get("type")
            else:
                name = f"{direction}{index+1}"
                dtype = None
            dtype_value = str(dtype).strip() if isinstance(dtype, str) else None
            result.append(PortSpec(name=name, direction=direction, dtype=dtype_value))
        return result

    def _snap_to_grid(self, pos: QPointF) -> QPointF:
        if self._grid_size <= 1:
            return pos
        x = round(pos.x() / self._grid_size) * self._grid_size
        y = round(pos.y() / self._grid_size) * self._grid_size
        return QPointF(x, y)

    def _add_block(self, *, type_id: str, pos: QPointF) -> Optional[BlockItem]:
        """Create a new block instance and corresponding graphics item."""

        metadata = self._block_catalog.get(type_id, {})
        title = str(metadata.get("title", type_id))
        snapped = self._snap_to_grid(pos)
        block = self._project_model.create_block(type_id=type_id, x=snapped.x(), y=snapped.y())
        item = self._create_item_for_block(block, title=title)
        self.blockAdded.emit(block)
        self._emit_status(f"Добавлен блок: {title}")
        return item

    # ----------------------------------------------------------- connection API
    def begin_connection(self, port: PortItem) -> None:
        if port.direction != "out":
            if port.direction == "in" and port.has_connections():
                self._emit_status("Вход уже соединён. Удалите связь для замены.")
            else:
                self._emit_status("Соединение начинается с выходного порта.")
            return
        self._cancel_connection_preview()
        self._connection_start_port = port
        preview = ConnectionItem(port, preview=True)
        preview.set_temp_end(port.connection_anchor())
        self._connection_preview = preview
        self.addItem(preview)
        self._emit_status("Перетащите соединение к целевому входу")

    def complete_connection(self, port: PortItem) -> None:
        if self._connection_preview is None or self._connection_start_port is None:
            return
        if port is self._connection_start_port:
            self._emit_status("Соединение отменено")
            self._cancel_connection_preview()
            return
        if port.direction != "in":
            self._emit_status("Целевой порт должен быть входом")
            return
        start_port = self._connection_start_port
        if start_port.direction != "out":
            self._emit_status("Соединение начинается с выходного порта")
            self._cancel_connection_preview()
            return
        if port.has_connections():
            self._emit_status("Вход уже использован")
            self._cancel_connection_preview()
            return
        if not self._are_types_compatible(start_port, port):
            self._emit_status("Несовместимые типы портов")
            self._cancel_connection_preview()
            return
        from_uid = start_port.block_item.block.uid
        to_uid = port.block_item.block.uid
        key = self._connection_key(from_uid, start_port.name, to_uid, port.name)
        if key in self._connection_items:
            self._emit_status("Такое соединение уже существует")
            self._cancel_connection_preview()
            return
        if self._creates_cycle(from_uid, to_uid):
            self._emit_status("Соединение создает цикл — запрещено")
            self._cancel_connection_preview()
            return
        self._cancel_connection_preview()
        connection_model = ConnectionModel(
            from_block_uid=from_uid,
            from_port=start_port.name,
            to_block_uid=to_uid,
            to_port=port.name,
        )
        self._project_model.add_connection(connection_model)
        item = ConnectionItem(start_port, port, model=connection_model, preview=False)
        self._register_connection_item(connection_model, item)
        title_from = self._block_catalog.get(
            start_port.block_item.block.type_id, {}
        ).get("title", start_port.block_item.block.type_id)
        title_to = self._block_catalog.get(port.block_item.block.type_id, {}).get(
            "title", port.block_item.block.type_id
        )
        self.connectionAdded.emit(connection_model)
        self._emit_status(f"Создано соединение: {title_from} → {title_to}")

    def _register_connection_item(
        self, connection: ConnectionModel, item: ConnectionItem
    ) -> None:
        key = connection.key()
        self._connection_items[key] = item
        self.addItem(item)
        item.update_path()
        item.start_port.add_connection(item)
        item.start_port.block_item.register_connection(item)
        if item.end_port is not None:
            item.end_port.add_connection(item)
            item.end_port.block_item.register_connection(item)

    def _remove_connections_for_block(self, uid: str) -> int:
        removed = 0
        for key, item in list(self._connection_items.items()):
            model = item.model
            if model and (model.from_block_uid == uid or model.to_block_uid == uid):
                if self._remove_connection_item(item):
                    removed += 1
        return removed

    def _remove_connection_item(self, item: ConnectionItem) -> bool:
        model = item.model
        if model is None:
            return False
        key = model.key()
        if key in self._connection_items:
            self._connection_items.pop(key, None)
        item.detach()
        self._project_model.remove_connection(model)
        self.removeItem(item)
        return True

    def _find_port(self, block_uid: str, name: str, direction: Optional[str] = None) -> Optional[PortItem]:
        block_item = self._block_items.get(block_uid)
        if block_item is None:
            return None
        return block_item.get_port(name, direction)

    def _create_connection_item(self, connection: ConnectionModel) -> Optional[ConnectionItem]:
        start = self._find_port(connection.from_block_uid, connection.from_port, "out")
        end = self._find_port(connection.to_block_uid, connection.to_port, "in")
        if start is None or end is None:
            self._emit_status(
                "Не удалось восстановить соединение при загрузке проекта",
                6000,
            )
            return None
        item = ConnectionItem(start, end, model=connection, preview=False)
        self._register_connection_item(connection, item)
        return item

    def _creates_cycle(self, from_uid: str, to_uid: str) -> bool:
        if from_uid == to_uid:
            return True
        adjacency: Dict[str, List[str]] = {}
        for connection in self._project_model.connections:
            adjacency.setdefault(connection.from_block_uid, []).append(connection.to_block_uid)
        adjacency.setdefault(from_uid, []).append(to_uid)
        visited = set()
        queue: deque[str] = deque([to_uid])
        while queue:
            current = queue.popleft()
            if current == from_uid:
                return True
            for neighbour in adjacency.get(current, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(neighbour)
        return False

    def _are_types_compatible(self, source: PortItem, target: PortItem) -> bool:
        src = source.dtype or ""
        dst = target.dtype or ""
        if not src or src.lower() in {"any", "*"}:
            return True
        if not dst or dst.lower() in {"any", "*"}:
            return True
        return src == dst

    def _connection_key(self, from_uid: str, from_port: str, to_uid: str, to_port: str) -> str:
        return f"{from_uid}:{from_port}->{to_uid}:{to_port}"

    def _cancel_connection_preview(self) -> None:
        if self._connection_preview is not None:
            self.removeItem(self._connection_preview)
        self._connection_preview = None
        self._connection_start_port = None

    def _emit_status(self, text: str, timeout: int = 4000) -> None:
        self.statusMessage.emit(text, timeout)

    # --------------------------------------------------------- drop toggling API
    def setAcceptDrops(self, accept: bool) -> None:  # type: ignore[override]
        """Store drop availability flag for the scene.

        Qt не предоставляет прямой реализации ``setAcceptDrops`` для
        :class:`QGraphicsScene`, поэтому сохраняем состояние самостоятельно.
        Метод присутствует для совместимости с ожидаемым API.
        """

        self._accept_drops_enabled = bool(accept)
        super().setAcceptDrops(accept)

    def acceptsDrops(self) -> bool:  # type: ignore[override]
        """Return whether the scene currently accepts drops."""

        return self._accept_drops_enabled
