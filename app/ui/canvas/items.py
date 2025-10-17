from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem

from .model import BlockInstance

GRID_SIZE = 20


@dataclass(frozen=True)
class PortSpec:
    name: str
    direction: str   # "in" | "out"
    dtype: Optional[str] = None


class BlockItem(QGraphicsItem):
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

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(1)

        self._port_specs_in = list(ports_in or [])
        self._port_specs_out = list(ports_out or [])
        self._ports_in: List[PortItem] = []
        self._ports_out: List[PortItem] = []
        self._port_lookup: Dict[Tuple[str, str], PortItem] = {}
        self._connections: Set["ConnectionItem"] = set()
        self._height = self._compute_height()
        self._create_ports()

        self.setPos(self.block.x, self.block.y)

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return QRectF(0, 0, self.WIDTH, self._height)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        rect = QRectF(0, 0, self.WIDTH, self._height)
        painter.setPen(QPen(QColor(96, 125, 139), 1.5))
        painter.setBrush(QColor(38, 50, 56))
        painter.drawRoundedRect(rect, 8, 8)

        header = QRectF(0, 0, self.WIDTH, self.HEADER_HEIGHT)
        painter.setBrush(QColor(55, 71, 79))
        painter.drawRoundedRect(header, 8, 8)
        painter.drawRect(0, self.HEADER_HEIGHT - 1, self.WIDTH, 1)

        painter.setPen(QColor(236, 239, 241))
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(header.adjusted(8, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, self.title)

        if self.isSelected():
            painter.setPen(QPen(QColor(255, 193, 7), 2.0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionHasChanged:
            pos = self.pos()
            gx = round(pos.x() / self.grid_size) * self.grid_size
            gy = round(pos.y() / self.grid_size) * self.grid_size
            self.block.x, self.block.y = gx, gy
            self.setPos(gx, gy)
            for connection in list(self._connections):
                connection.update_path()
        return super().itemChange(change, value)

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
            from PySide6.QtGui import QPainterPath
            self.setPath(QPainterPath())
            return
        if self.end_port is not None:
            end = self._anchor_for_port(self.end_port)
        elif self._temp_end is not None:
            end = self._temp_end
        else:
            end = start
        from PySide6.QtGui import QPainterPath
        path = QPainterPath(start)
        dx = (end.x() - start.x()) * 0.5
        path.cubicTo(start.x() + dx, start.y(), end.x() - dx, end.y(), end.x(), end.y())
        self.setPath(path)

    def _anchor_for_port(self, port: Optional[PortItem]) -> Optional[QPointF]:
        if port is None:
            return None
        return port.connection_anchor()

    def detach(self) -> None:
        if self.start_port is not None:
            self.start_port.remove_connection(self)
            self.start_port.block_item.unregister_connection(self)
        if self.end_port is not None:
            self.end_port.remove_connection(self)
            self.end_port.block_item.unregister_connection(self)
        self.start_port = None  # type: ignore[assignment]
        self.end_port = None    # type: ignore[assignment]
