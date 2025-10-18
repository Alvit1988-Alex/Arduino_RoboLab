from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class CodePanel(QWidget):
    """Виджет отображения сгенерированного Arduino-кода."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.copy_button = QPushButton("Копировать")
        controls.addStretch(1)
        controls.addWidget(self.copy_button)

        layout.addLayout(controls)

        self.editor = QTextEdit(self)
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("Нажмите ‘Сгенерировать скетч’, чтобы увидеть результат…")
        layout.addWidget(self.editor, 1)

        self.copy_button.clicked.connect(self._copy_to_clipboard)

    def _copy_to_clipboard(self) -> None:
        text = self.editor.toPlainText()
        if not text:
            return
        self.editor.selectAll()
        self.editor.copy()
        self.editor.moveCursor(QTextCursor.End)

    # API -------------------------------------------------------------
    def set_code(self, text: str) -> None:
        self.editor.setPlainText(text)

    def text(self) -> str:
        return self.editor.toPlainText()


class CodeDock(QDockWidget):
    """Док-панель с кодом."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Сгенерированный код", parent)
        self.setObjectName("codeDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._panel = CodePanel(self)
        self.setWidget(self._panel)

    def set_code(self, text: str) -> None:
        self._panel.set_code(text)

    def text(self) -> str:
        return self._panel.text()
