from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsScene

MIME_TYPE = "application/x-robolab-block-id"


class CanvasScene(QGraphicsScene):
    """
    QGraphicsScene с поддержкой палитры блоков (DnD), сетки и простого API
    для экспорта/импорта модели проекта. Логика соединений реализуется позже.
    """
    blockAdded = Signal(object)
    blocksRemoved = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # производительность и вид
        self.setItemIndexMethod(QGraphicsScene.NoIndex)
        # Границы сцены — вариант Codex (больше поле)
        self.setSceneRect(-5000, -5000, 10000, 10000)
        # Фон — тёмный (вариант Codex)
        self.setBackgroundBrush(QColor("#202020"))

        # Совместимость: храним флаг приёма drop вручную
        self._accept_drops_enabled: bool = True

        # Каталог доступных блоков {type_id: title}
        self._catalog: Dict[str, str] = {}

    # -------- публичное API, вызываемое из MainWindow --------
    def set_block_catalog(self, catalog: Dict[str, str]) -> None:
        self._catalog = dict(catalog)

    def reset(self) -> None:
        cnt = len(self.items())
        self.clear()
        if cnt:
            self.blocksRemoved.emit(cnt)

    # NOTE: export_model/load_model реализованы в твоём проекте в этом модуле
    # или в соседнем (items/model). Мы их не трогаем здесь — остаётся реализация Codex.

    # -------- совместимое API для включения/выключения drop --------
    def setAcceptDrops(self, accept: bool) -> None:  # type: ignore[override]
        """
        Qt не даёт прямого setAcceptDrops у QGraphicsScene; храним флаг сами.
        Метод оставлен для совместимости с ожидаемым API.
        """
        self._accept_drops_enabled = bool(accept)

    def acceptsDrops(self) -> bool:  # type: ignore[override]
        """Текущее состояние приёма drop."""
        return self._accept_drops_enabled

    # -------- DnD события --------
    def dragEnterEvent(self, event) -> None:
        if self.acceptsDrops() and event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self.acceptsDrops() and event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        # Если drop выключен — передаём наверх и выходим
        if not self.acceptsDrops():
            super().dropEvent(event)
            return
        if not event.mimeData().hasFormat(MIME_TYPE):
            event.ignore()
            return

        block_id = bytes(event.mimeData().data(MIME_TYPE)).decode("utf-8")
        self._add_block(block_id, event.scenePos())
        event.acceptProposedAction()

    # -------- внутренняя логика добавления блоков --------
    def _add_block(self, block_id: str, pos: QPointF) -> None:
        # локальный импорт, чтобы не словить циклические зависимости
        from .items import BlockItem
        item = BlockItem(block_id)
        item.setPos(pos)
        self.addItem(item)
        self.blockAdded.emit(item)
