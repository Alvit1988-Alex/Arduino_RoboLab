from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QPlainTextEdit


class SerialMonitorDock(QDockWidget):
    """Простая заглушка док-панели монитора порта."""

    def __init__(self, parent=None) -> None:
        super().__init__("Монитор порта", parent)
        self.setObjectName("serialMonitorDock")
        self.setAllowedAreas(
            Qt.TopDockWidgetArea
            | Qt.BottomDockWidgetArea
            | Qt.LeftDockWidgetArea
            | Qt.RightDockWidgetArea
        )
        self._output = QPlainTextEdit(self)
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("Монитор порта будет доступен в будущих версиях")
        self.setWidget(self._output)

    def append_line(self, text: str) -> None:
        self._output.appendPlainText(text)
