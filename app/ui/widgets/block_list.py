from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from ..canvas.canvas_scene import MIME_BLOCK


class BlockListWidget(QListWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionMode(self.SingleSelection)
        self.setDragEnabled(True)
        self._catalog: Dict[str, Dict[str, object]] = {}

    def set_catalog(self, catalog: Dict[str, Dict[str, object]]) -> None:
        self._catalog = dict(catalog)
        self.clear()
        for type_id, meta in sorted(self._catalog.items()):
            title = str(meta.get("title", type_id))
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, type_id)
            self.addItem(item)

    def startDrag(self, supportedActions) -> None:  # type: ignore[override]
        item = self.currentItem()
        if not item:
            return
        type_id = str(item.data(Qt.UserRole) or "")
        if not type_id:
            return
        mime = QMimeData()
        mime.setData(MIME_BLOCK, type_id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        self.startDrag(Qt.CopyAction)
        super().mouseDoubleClickEvent(event)
