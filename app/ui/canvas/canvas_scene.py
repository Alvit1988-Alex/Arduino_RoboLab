"""Graphics scene implementing drag-and-drop and project synchronisation."""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsScene

from .items import BlockItem, GRID_SIZE
from .model import BlockInstance, ProjectModel

MIME_TYPE = "application/x-robolab-block-id"


class CanvasScene(QGraphicsScene):
    """Canvas with drag & drop support for RoboLab blocks."""

    blockAdded = Signal(BlockInstance)
    blocksRemoved = Signal(int)

    def __init__(self, *, parent=None) -> None:
        super().__init__(parent)
        self.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self._project_model = ProjectModel()
        self._block_items: Dict[str, BlockItem] = {}
        self._block_catalog: Dict[str, str] = {}
        self._grid_size = GRID_SIZE
        self._accept_drops_enabled = False
        self.setBackgroundBrush(QColor("#202020"))
        self.setAcceptDrops(True)

    # ------------------------------------------------------------ catalog/model
    def set_block_catalog(self, catalog: Dict[str, str]) -> None:
        self._block_catalog = dict(catalog)

    def load_model(self, model: ProjectModel) -> None:
        self.clear()
        self._block_items.clear()
        self._project_model = model.clone()
        for block in self._project_model.blocks:
            self._create_item_for_block(block)
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
        removed = 0
        for item in list(self.selectedItems()):
            if isinstance(item, BlockItem):
                uid = item.block.uid
                self._project_model.remove_block(uid)
                self._block_items.pop(uid, None)
                self.removeItem(item)
                removed += 1
        if removed:
            self.blocksRemoved.emit(removed)
        return removed

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

    # ---------------------------------------------------------------- helpers
    def _create_item_for_block(self, block: BlockInstance, title: Optional[str] = None) -> BlockItem:
        final_title = title or self._block_catalog.get(block.type_id, block.type_id)
        try:
            item = BlockItem(block, title=final_title, grid_size=self._grid_size)
        except TypeError:
            item = BlockItem(block)  # type: ignore[call-arg] - совместимость со старыми версиями
        self.addItem(item)
        item.setPos(block.x, block.y)
        self._block_items[block.uid] = item
        return item

    def _snap_to_grid(self, pos: QPointF) -> QPointF:
        if self._grid_size <= 1:
            return pos
        x = round(pos.x() / self._grid_size) * self._grid_size
        y = round(pos.y() / self._grid_size) * self._grid_size
        return QPointF(x, y)

    def _add_block(self, *, type_id: str, pos: QPointF) -> Optional[BlockItem]:
        """Create a new block instance and corresponding graphics item."""

        title = self._block_catalog.get(type_id, type_id)
        snapped = self._snap_to_grid(pos)
        block = self._project_model.create_block(type_id=type_id, x=snapped.x(), y=snapped.y())
        item = self._create_item_for_block(block, title=title)
        self.blockAdded.emit(block)
        return item

    # --------------------------------------------------------- drop toggling API
    def setAcceptDrops(self, accept: bool) -> None:  # type: ignore[override]
        """Store drop availability flag for the scene.

        Qt не предоставляет прямой реализации ``setAcceptDrops`` для
        :class:`QGraphicsScene`, поэтому сохраняем состояние самостоятельно.
        Метод присутствует для совместимости с ожидаемым API.
        """

        self._accept_drops_enabled = bool(accept)

    def acceptsDrops(self) -> bool:  # type: ignore[override]
        """Return whether the scene currently accepts drops."""

        return self._accept_drops_enabled
