"""Graphics items used on the RoboLab canvas."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem

from .model import BlockInstance

GRID_SIZE = 16


class BlockItem(QGraphicsItem):
    """Visual representation of a block on the canvas."""

    WIDTH = 160
    HEIGHT = 80
    HEADER_HEIGHT = 26

    def __init__(self, block: BlockInstance, *, title: str, grid_size: int = GRID_SIZE) -> None:
        super().__init__()
        self.block = block
        self.title = title
        self.grid_size = grid_size
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(1)

    # --------------------------------------------------------------- QGraphics
    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return QRectF(0, 0, self.WIDTH, self.HEIGHT)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        rect = self.boundingRect()
        background = QColor(55, 71, 79) if self.isSelected() else QColor(38, 50, 56)
        border_color = QColor(0, 188, 212) if self.isSelected() else QColor(96, 125, 139)
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 8, 8)

        header_rect = QRectF(rect.left(), rect.top(), rect.width(), self.HEADER_HEIGHT)
        header_color = QColor(120, 144, 156)
        painter.setPen(Qt.NoPen)
        painter.setBrush(header_color)
        painter.drawRoundedRect(header_rect, 8, 8)
        painter.drawRect(
            QRectF(
                header_rect.left(),
                header_rect.top() + self.HEADER_HEIGHT / 2,
                header_rect.width(),
                self.HEADER_HEIGHT / 2,
            )
        )

        painter.setPen(Qt.white)
        font = QFont()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(header_rect.adjusted(8, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, self.title)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionChange:
            pos: QPointF = value
            snapped = self._snap_to_grid(pos)
            return snapped
        if change == QGraphicsItem.ItemPositionHasChanged:
            new_pos = self.pos()
            self.block.set_position(new_pos.x(), new_pos.y())
        return super().itemChange(change, value)

    # ------------------------------------------------------------- helpers
    def _snap_to_grid(self, pos: QPointF) -> QPointF:
        if self.grid_size <= 1:
            return pos
        x = round(pos.x() / self.grid_size) * self.grid_size
        y = round(pos.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)


class PortItem(QGraphicsEllipseItem):
    """Placeholder for block ports (future work)."""

    def __init__(self, center: QPointF, radius: float = 4.0) -> None:
        diameter = radius * 2
        rect = QRectF(center.x() - radius, center.y() - radius, diameter, diameter)
        super().__init__(rect)
        self.setBrush(QColor(236, 239, 241))
        self.setPen(QPen(QColor(84, 110, 122)))
        self.setZValue(2)


class ConnectionItem(QGraphicsPathItem):
    """Placeholder for block connections (future work)."""

    def __init__(self) -> None:
        super().__init__()
        self.setPen(QPen(QColor(120, 144, 156), 2))
        self.setZValue(0)
