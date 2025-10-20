from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.canvas.items import BlockItem
from app.ui.canvas.canvas_scene import CanvasScene

from .editors import BaseParamEditor, create_editor


class PropsDock(QDockWidget):
    """Dock widget that exposes parameters of the selected block."""

    def __init__(self, scene: CanvasScene, parent: Optional[QWidget] = None) -> None:
        super().__init__("Свойства блока", parent)
        self.setObjectName("propsDock")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        self._scene = scene
        self._catalog: Dict[str, Dict[str, object]] = {}
        self._block_item: Optional[BlockItem] = None
        self._editors: Dict[str, BaseParamEditor] = {}

        container = QWidget(self)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(6)

        self._header_label = QLabel("Не выбран блок")
        self._header_label.setWordWrap(True)
        container_layout.addWidget(self._header_label)

        self._scroll = QScrollArea(container)
        self._scroll.setWidgetResizable(True)
        self._form_container = QWidget()
        self._form_layout = QFormLayout(self._form_container)
        self._form_layout.setLabelAlignment(Qt.AlignRight)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._form_container)
        container_layout.addWidget(self._scroll, 1)

        self._reset_button = QPushButton("Сбросить параметры по умолчанию", container)
        self._reset_button.clicked.connect(self._reset_parameters)
        container_layout.addWidget(self._reset_button)

        self.setWidget(container)
        self.clear()

    # ------------------------------------------------------------------ public
    def set_block_catalog(self, catalog: Dict[str, Dict[str, object]]) -> None:
        self._catalog = dict(catalog)

    def bind(self, block_item: BlockItem) -> None:
        self._block_item = block_item
        block = block_item.block
        metadata = self._catalog.get(block.type_id, {})
        params_meta = metadata.get("params", []) if isinstance(metadata.get("params"), list) else []
        default_params = metadata.get("default_params", {})
        if not isinstance(default_params, dict):
            default_params = {}

        self._header_label.setText(
            f"<b>{metadata.get('title', block.type_id)}</b><br/>UID: {block.uid}"
        )
        self.setWindowTitle(f"Свойства — {metadata.get('title', block.type_id)} ({block.uid})")

        # clear previous editors
        self._clear_form()
        self._editors.clear()

        if not params_meta:
            placeholder = QLabel("Этот блок не имеет настраиваемых параметров.")
            placeholder.setEnabled(False)
            self._form_layout.addRow(placeholder)
            self._reset_button.setEnabled(False)
            return

        self._reset_button.setEnabled(True)
        for descriptor in params_meta:
            if not isinstance(descriptor, dict):
                continue
            name = descriptor.get("name")
            if not isinstance(name, str) or not name:
                continue
            editor = create_editor(descriptor)
            editor.setParent(self._form_container)
            value = block.params.get(name)
            if value is None:
                if name in default_params:
                    value = default_params[name]
                elif "default" in descriptor:
                    value = descriptor.get("default")
            editor.set_value(value)
            editor.valueChanged.connect(lambda val, param=name: self._on_value_changed(param, val))

            label_text = descriptor.get("label") or descriptor.get("title") or name
            label = QLabel(str(label_text))
            self._form_layout.addRow(label, editor)
            self._editors[name] = editor

        # ensure block params include defaults for missing values
        for name, editor in self._editors.items():
            block.params[name] = editor.value()

    def clear(self) -> None:
        self._block_item = None
        self._clear_form()
        self._editors.clear()
        self._header_label.setText("Не выбран блок")
        self.setWindowTitle("Свойства блока")
        self._reset_button.setEnabled(False)

    def focus_first_editor(self) -> None:
        if self._editors:
            first = next(iter(self._editors.values()))
            first.focus_editor()

    # ----------------------------------------------------------------- callbacks
    def _clear_form(self) -> None:
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_value_changed(self, name: str, value) -> None:
        if self._block_item is None:
            return
        self._block_item.block.params[name] = value
        self._scene.notify_block_params_changed(self._block_item)

    def _reset_parameters(self) -> None:
        if self._block_item is None:
            return
        metadata = self._catalog.get(self._block_item.block.type_id, {})
        defaults = metadata.get("default_params", {})
        if not isinstance(defaults, dict) or not defaults:
            return
        for name, editor in self._editors.items():
            value = defaults.get(name)
            if value is None and isinstance(editor.metadata, dict):
                value = editor.metadata.get("default")
            editor.set_value(value)
            self._block_item.block.params[name] = editor.value()
        self._scene.notify_block_params_changed(self._block_item)


__all__ = ["PropsDock"]
