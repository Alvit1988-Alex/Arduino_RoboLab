from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..common.mime import BLOCK_MIME


class PaletteTreeWidget(QTreeWidget):
    """Категории блоков с поддержкой drag-and-drop."""

    blockActivated = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setUniformRowHeights(True)
        self.setAnimated(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setExpandsOnDoubleClick(False)

    def startDrag(self, supportedActions: Qt.DropActions) -> None:  # type: ignore[override]
        item = self.currentItem()
        if item is None or item.parent() is None:
            return
        payload = item.data(0, Qt.UserRole)
        if not isinstance(payload, dict):
            return
        block_id = payload.get("id")
        if not block_id:
            return
        mime = QMimeData()
        mime.setData(BLOCK_MIME, str(block_id).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        item = self.itemAt(event.pos())
        if item and item.parent() is not None:
            payload = item.data(0, Qt.UserRole)
            if isinstance(payload, dict):
                self.blockActivated.emit(payload)
        super().mouseDoubleClickEvent(event)


class PaletteDock(QDockWidget):
    """Док-панель с палитрой блоков и поиском."""

    blockActivated = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Палитра блоков", parent)
        self.setObjectName("paletteDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_label = QLabel("Палитра")
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        self._count_label = QLabel()
        header_layout.addWidget(self._count_label)

        layout.addLayout(header_layout)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию или ID…")
        layout.addWidget(self.search_edit)

        self.tree = PaletteTreeWidget()
        layout.addWidget(self.tree, 1)

        container.setLayout(layout)
        self.setWidget(container)

        self._category_items: Dict[str, QTreeWidgetItem] = {}
        self._all_blocks: List[dict] = []

        self.search_edit.textChanged.connect(self._apply_filter)
        self.tree.blockActivated.connect(self.blockActivated)

    def set_blocks(self, blocks: Iterable[dict]) -> None:
        """Populate tree with provided block metadata."""
        self._all_blocks = list(blocks)
        self.tree.clear()
        self._category_items.clear()

        grouped: Dict[str, List[dict]] = {}
        for block in self._all_blocks:
            category = str(block.get("category", "Прочее"))
            grouped.setdefault(category, []).append(block)

        for category in sorted(grouped.keys()):
            cat_item = QTreeWidgetItem([category])
            cat_item.setFlags(Qt.ItemIsEnabled)
            self.tree.addTopLevelItem(cat_item)
            self._category_items[category] = cat_item

            for block in sorted(grouped[category], key=lambda b: str(b.get("title", b.get("id", "")))):
                child = QTreeWidgetItem([str(block.get("title", block.get("id", "")))])
                child.setData(0, Qt.UserRole, block)
                tooltip = block.get("description")
                if tooltip:
                    child.setToolTip(0, str(tooltip))
                cat_item.addChild(child)

        self.tree.expandAll()
        self._count_label.setText(f"{len(self._all_blocks)} блоков")
        self._apply_filter(self.search_edit.text())

    def _apply_filter(self, text: str) -> None:
        pattern = text.strip().lower()
        for category, cat_item in self._category_items.items():
            any_visible = False
            for index in range(cat_item.childCount()):
                child = cat_item.child(index)
                block = child.data(0, Qt.UserRole)
                if not isinstance(block, dict):
                    child.setHidden(False)
                    any_visible = True
                    continue
                title = str(block.get("title", "")).lower()
                block_id = str(block.get("id", "")).lower()
                matches = not pattern or pattern in title or pattern in block_id
                child.setHidden(not matches)
                any_visible = any_visible or matches
            cat_item.setHidden(not any_visible)

    # Convenience API -------------------------------------------------
    def first_block(self) -> Optional[dict]:
        return self._all_blocks[0] if self._all_blocks else None

