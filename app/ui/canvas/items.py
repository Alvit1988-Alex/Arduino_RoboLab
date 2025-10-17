"""Graphics items used on the RoboLab canvas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem

from .model import BlockInstance

GRID_SIZE = 16


@dataclass(frozen=True)
class PortSpec:
    """Specification of a block port."""

    name: str
    direction: str
    dtype: Optional[str] = None


class BlockItem(QGraphicsItem):
    """Visual representation of a block on the canvas."""

    WIDTH = 180
    HEADER_HEIGHT = 28
    MIN_HEIGHT = 96
    PORT_SPACING = 24
    PORT_MARGIN_TOP = 36

    def __init__(
        self,
        block: BlockInstance,
        *,
        title: str,
        ports_in: Sequence[PortSpec] | None = None,
        ports_out: Sequence[PortSpec] | None = None,
        grid_size: int = GRID_SIZE,
    ) -> None:
        super().__init__()
        self.block = block
        self.title = title
        self.grid_size = grid_size
        self._port_specs_in = list(ports_in or [])
        self._port_specs_out = list(ports_out or [])
        self._ports_in: List[PortItem] = []
        self._ports_out: List[PortItem] = []
        self._port_lookup: Dict[Tuple[str, str], PortItem] = {}
        self._connections: Set["ConnectionItem"] = set()
        self._height = self._compute_height()
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(1)
        self._create_ports()

    # --------------------------------------------------------------- QGraphics
    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return QRectF(0, 0, self.WIDTH, self._height)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        rect = QRectF(0, 0, self.WIDTH, self._height)
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
            for connection in list(self._connections):
                connection.update_path()
        return super().itemChange(change, value)

    # -------------------------------------------------------------- port utils
    def ports_in(self) -> Iterable["PortItem"]:
        return tuple(self._ports_in)

    def ports_out(self) -> Iterable["PortItem"]:
        return tuple(self._ports_out)

    def get_port(self, name: str, direction: Optional[str] = None) -> Optional["PortItem"]:
        if direction:
            return self._port_lookup.get((direction, name))
        return self._port_lookup.get(("in", name)) or self._port_lookup.get(("out", name))

    def register_connection(self, connection: "ConnectionItem") -> None:
        self._connections.add(connection)

    def unregister_connection(self, connection: "ConnectionItem") -> None:
        self._connections.discard(connection)

    # ------------------------------------------------------------- helpers
    def _snap_to_grid(self, pos: QPointF) -> QPointF:
        if self.grid_size <= 1:
            return pos
        x = round(pos.x() / self.grid_size) * self.grid_size
        y = round(pos.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)

    def _compute_height(self) -> float:
        rows = max(len(self._port_specs_in), len(self._port_specs_out), 1)
        return max(self.MIN_HEIGHT, self.HEADER_HEIGHT + self.PORT_MARGIN_TOP + rows * self.PORT_SPACING)

    def _create_ports(self) -> None:
        base_y = self.HEADER_HEIGHT + self.PORT_MARGIN_TOP
        for index, spec in enumerate(self._port_specs_in):
            port = PortItem(self, spec)
            port.setPos(0, base_y + index * self.PORT_SPACING)
            self._ports_in.append(port)
            self._port_lookup[(spec.direction, spec.name)] = port
        for index, spec in enumerate(self._port_specs_out):
            port = PortItem(self, spec)
            port.setPos(self.WIDTH, base_y + index * self.PORT_SPACING)
            self._ports_out.append(port)
            self._port_lookup[(spec.direction, spec.name)] = port


class PortItem(QGraphicsEllipseItem):
    """Interactive port item used for connections."""

    RADIUS = 6.0
    COLOR_DEFAULT = QColor(236, 239, 241)
    COLOR_HOVER = QColor(255, 241, 118)

    def __init__(self, block_item: BlockItem, spec: PortSpec) -> None:
        rect = QRectF(-self.RADIUS, -self.RADIUS, self.RADIUS * 2, self.RADIUS * 2)
        super().__init__(rect, block_item)
        self.block_item = block_item
        self.spec = spec
        self.direction = spec.direction
        self.dtype = spec.dtype.lower() if isinstance(spec.dtype, str) else None
        self.setBrush(self.COLOR_DEFAULT)
        self.setPen(QPen(QColor(84, 110, 122), 1.5))
        self.setZValue(2)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self._connections: Set["ConnectionItem"] = set()
        self.setToolTip(f"{self.direction}: {self.spec.name}")

    # --------------------------------------------------------------- helpers
    @property
    def name(self) -> str:
        return self.spec.name

    def add_connection(self, connection: "ConnectionItem") -> None:
        self._connections.add(connection)

    def remove_connection(self, connection: "ConnectionItem") -> None:
        self._connections.discard(connection)

    def has_connections(self) -> bool:
        return bool(self._connections)

    def iter_connections(self) -> Iterable["ConnectionItem"]:
        return tuple(self._connections)

    def connection_anchor(self) -> QPointF:
        return self.mapToScene(self.boundingRect().center())

    # ---------------------------------------------------------------- events
    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        self.setBrush(self.COLOR_HOVER)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.setBrush(self.COLOR_DEFAULT)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            scene = self.scene()
            handler = getattr(scene, "begin_connection", None)
            if callable(handler):
                handler(self)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            scene = self.scene()
            handler = getattr(scene, "complete_connection", None)
            if callable(handler):
                handler(self)
                event.accept()
                return
        super().mouseReleaseEvent(event)


class ConnectionItem(QGraphicsPathItem):
    """Visual connection between two ports."""

    COLOR_DEFAULT = QColor(120, 144, 156)
    COLOR_SELECTED = QColor(255, 193, 7)

    def __init__(
        self,
        start_port: PortItem,
        end_port: Optional[PortItem] = None,
        *,
        model=None,
        preview: bool = False,
    ) -> None:
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.model = model
        self._temp_end: Optional[QPointF] = None
        self._is_preview = preview
        pen = self._make_pen(preview)
        self.setPen(pen)
        self.setBrush(Qt.NoBrush)
        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable, not preview)
        self.setAcceptHoverEvents(True)
        self.update_path()

    # --------------------------------------------------------------- helpers
    def _make_pen(self, preview: bool) -> QPen:
        style = Qt.DashLine if preview else Qt.SolidLine
        return QPen(self.COLOR_DEFAULT, 2.0 if not preview else 1.5, style, Qt.RoundCap, Qt.RoundJoin)

    def set_temp_end(self, pos: QPointF) -> None:
        self._temp_end = QPointF(pos)
        self.update_path()

    def set_end_port(self, port: PortItem) -> None:
        self.end_port = port
        self._temp_end = None
        self._is_preview = False
        self.setPen(self._make_pen(False))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.update_path()

    def update_path(self) -> None:
        start = self._anchor_for_port(self.start_port)
        if start is None:
            self.setPath(QPainterPath())
            return
        if self.end_port is not None:
            end = self._anchor_for_port(self.end_port)
        elif self._temp_end is not None:
            end = self._temp_end
        else:
            end = start
        path = QPainterPath(start)
        dx = (end.x() - start.x()) * 0.5
        path.cubicTo(start.x() + dx, start.y(), end.x() - dx, end.y(), end.x(), end.y())
        self.setPath(path)

    def _anchor_for_port(self, port: Optional[PortItem]) -> Optional[QPointF]:
        if port is None:
            return None
        return port.connection_anchor()

    def detach(self) -> None:
        """Detach the connection from its ports."""

        if self.start_port is not None:
            self.start_port.remove_connection(self)
            self.start_port.block_item.unregister_connection(self)
        if self.end_port is not None:
            self.end_port.remove_connection(self)
            self.end_port.block_item.unregister_connection(self)
        self.start_port = None  # type: ignore[assignment]
        self.end_port = None  # type: ignore[assignment]

    # ---------------------------------------------------------------- events
    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        pen = self.pen()
        pen.setColor(self.COLOR_SELECTED)
        self.setPen(pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        pen = self.pen()
        pen.setColor(self.COLOR_DEFAULT)
        self.setPen(pen)
        super().hoverLeaveEvent(event)
