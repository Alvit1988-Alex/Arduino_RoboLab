from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class CodePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.editor = QTextEdit(self)
        self.editor.setPlaceholderText("Здесь будет показываться сгенерированный код...")
        layout.addWidget(self.editor)
