# app/ui/canvas/canvas_view.py
"""Graphics view with panning, zoom and grid drawing."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
)


class CanvasView(QGraphicsView):
    """Customized graphics view for the RoboLab canvas."""

    MIN_ZOOM = 0.25
    MAX_ZOOM = 3.0
    GRID_SIZE = 16
    _TEXT_INPUT_WIDGETS = (QLineEdit, QPlainTextEdit, QTextEdit)

    def __init__(self, scene: Optional[QGraphicsScene] = None, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self._zoom = 1.0
        self._is_panning = False
        self._last_pan_point: Optional[QPoint] = None

    # ----------------------------------------------------------------- commands
    def reset_zoom(self) -> None:
        self.resetTransform()
        self._zoom = 1.0

    # ------------------------------------------------------------------ events
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if event.modifiers() & Qt.ControlModifier:
            zoom_out = event.angleDelta().y() < 0
            factor = 0.9 if zoom_out else 1.1
            new_zoom = self._zoom * factor
            new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, new_zoom))
            factor = new_zoom / self._zoom
            self._zoom = new_zoom
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and event.modifiers() & Qt.ShiftModifier
        ):
            self._is_panning = True
            self._last_pan_point = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._is_panning and self._last_pan_point is not None:
            delta = event.position().toPoint() - self._last_pan_point
            self._last_pan_point = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._is_panning and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        # Централизованная обработка удаления:
        # - если фокус в текстовом поле — пропускаем
        # - иначе вызываем единый контракт сцены delete_selected() -> bool
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            focus = QApplication.focusWidget()
            if isinstance(focus, self._TEXT_INPUT_WIDGETS):
                super().keyPressEvent(event)
                return

            scene = self.scene()
            deleter = getattr(scene, "delete_selected", None)
            if callable(deleter) and deleter():
                event.accept()
                return

        # Ctrl+0 — сброс масштаба к 100%
        if event.key() == Qt.Key_0 and event.modifiers() & Qt.ControlModifier:
            self.reset_zoom()
            event.accept()
            return

        super().keyPressEvent(event)

    def drawBackground(self, painter: QPainter, rect) -> None:  # type: ignore[override]
        super().drawBackground(painter, rect)
        left = int(math.floor(rect.left() / self.GRID_SIZE)) - 1
        right = int(math.ceil(rect.right() / self.GRID_SIZE)) + 1
        top = int(math.floor(rect.top() / self.GRID_SIZE)) - 1
        bottom = int(math.ceil(rect.bottom() / self.GRID_SIZE)) + 1
        painter.save()
        color = self.palette().mid().color()
        color.setAlpha(60)
        painter.setPen(color)
        for x in range(left, right + 1):
            painter.drawLine(x * self.GRID_SIZE, rect.top(), x * self.GRID_SIZE, rect.bottom())
        for y in range(top, bottom + 1):
            painter.drawLine(rect.left(), y * self.GRID_SIZE, rect.right(), y * self.GRID_SIZE)
        painter.restore()
