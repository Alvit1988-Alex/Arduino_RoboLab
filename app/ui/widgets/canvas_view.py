from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsView,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
)

from ..canvas.canvas_scene import CanvasScene


class CanvasView(QGraphicsView):
    _TEXT_INPUT_WIDGETS = (QLineEdit, QPlainTextEdit, QTextEdit)

    def __init__(self, scene: CanvasScene, parent=None) -> None:
        super().__init__(parent)
        self.setScene(scene)
        self.setRenderHints(self.renderHints())
        # Qt6: drag mode из вложенного enum-класса DragMode
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self._panning = False
        self._pan_start = QPoint()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_Delete:
            focus = QApplication.focusWidget()
            if isinstance(focus, self._TEXT_INPUT_WIDGETS):
                super().keyPressEvent(event)
                return

            scene = self.scene()
            deleter = getattr(scene, "delete_selected", None)
            if callable(deleter) and deleter():
                event.accept()
                return

        super().keyPressEvent(event)
