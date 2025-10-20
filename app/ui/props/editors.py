from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
)
from PySide6.QtWidgets import QColorDialog


class BaseParamEditor(QWidget):
    """Base class for parameter editors in the properties dock."""

    valueChanged = Signal(object)

    def __init__(self, metadata: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._metadata = metadata

    @property
    def metadata(self) -> dict:
        return self._metadata

    def set_value(self, value: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def value(self) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    def focus_editor(self) -> None:
        focus_widget = self.focusProxy() or self
        focus_widget.setFocus(Qt.TabFocusReason)


class IntEditor(BaseParamEditor):
    def __init__(self, metadata: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(metadata, parent)
        self._spin = QSpinBox(self)
        self._spin.setAlignment(Qt.AlignRight)
        minimum = metadata.get("min")
        maximum = metadata.get("max")
        step = metadata.get("step")
        if isinstance(minimum, int):
            self._spin.setMinimum(minimum)
        else:
            self._spin.setMinimum(-1_000_000)
        if isinstance(maximum, int):
            self._spin.setMaximum(maximum)
        else:
            self._spin.setMaximum(1_000_000)
        if isinstance(step, int) and step > 0:
            self._spin.setSingleStep(step)
        self._spin.valueChanged.connect(self.valueChanged)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._spin)

    def set_value(self, value: Any) -> None:
        with SignalBlocker(self._spin):
            if isinstance(value, int):
                self._spin.setValue(value)
            elif isinstance(value, float):
                self._spin.setValue(int(value))
            else:
                default = self.metadata.get("default")
                if isinstance(default, int):
                    self._spin.setValue(default)

    def value(self) -> int:
        return int(self._spin.value())


class FloatEditor(BaseParamEditor):
    def __init__(self, metadata: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(metadata, parent)
        self._spin = QDoubleSpinBox(self)
        self._spin.setAlignment(Qt.AlignRight)
        minimum = metadata.get("min")
        maximum = metadata.get("max")
        step = metadata.get("step")
        if isinstance(minimum, (int, float)):
            self._spin.setMinimum(float(minimum))
        if isinstance(maximum, (int, float)):
            self._spin.setMaximum(float(maximum))
        if isinstance(step, (int, float)) and step > 0:
            self._spin.setSingleStep(float(step))
        else:
            self._spin.setSingleStep(0.1)
        self._spin.setDecimals(3)
        self._spin.valueChanged.connect(self.valueChanged)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._spin)

    def set_value(self, value: Any) -> None:
        with SignalBlocker(self._spin):
            if isinstance(value, (int, float)):
                self._spin.setValue(float(value))
            else:
                default = self.metadata.get("default")
                if isinstance(default, (int, float)):
                    self._spin.setValue(float(default))

    def value(self) -> float:
        return float(self._spin.value())


class EnumEditor(BaseParamEditor):
    def __init__(self, metadata: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(metadata, parent)
        self._combo = QComboBox(self)
        self._options: list[Any] = []
        for option in metadata.get("options", []) or []:
            if isinstance(option, dict):
                label = str(option.get("label", option.get("value")))
                value = option.get("value")
            else:
                label = str(option)
                value = option
            self._combo.addItem(label, userData=value)
            self._options.append(value)
        self._combo.currentIndexChanged.connect(self._emit_current_value)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo)

    def _emit_current_value(self, _index: int) -> None:
        self.valueChanged.emit(self.value())

    def set_value(self, value: Any) -> None:
        with SignalBlocker(self._combo):
            index = self._combo.findData(value)
            if index < 0:
                default = self.metadata.get("default")
                index = self._combo.findData(default)
            if index < 0:
                index = 0
            if index >= 0:
                self._combo.setCurrentIndex(index)

    def value(self) -> Any:
        return self._combo.currentData()


class StringEditor(BaseParamEditor):
    def __init__(self, metadata: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(metadata, parent)
        self._edit = QLineEdit(self)
        self._edit.textEdited.connect(self.valueChanged)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)

    def set_value(self, value: Any) -> None:
        with SignalBlocker(self._edit):
            if value is None:
                value = ""
            self._edit.setText(str(value))

    def value(self) -> str:
        return self._edit.text()

    def focus_editor(self) -> None:
        self._edit.setFocus(Qt.TabFocusReason)


class BoolEditor(BaseParamEditor):
    def __init__(self, metadata: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(metadata, parent)
        self._check = QCheckBox("", self)
        self._check.stateChanged.connect(self._emit_state)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._check)

    def _emit_state(self, _state: int) -> None:
        self.valueChanged.emit(self.value())

    def set_value(self, value: Any) -> None:
        with SignalBlocker(self._check):
            self._check.setChecked(bool(value))

    def value(self) -> bool:
        return bool(self._check.isChecked())

    def focus_editor(self) -> None:
        self._check.setFocus(Qt.TabFocusReason)


class ColorEditor(BaseParamEditor):
    def __init__(self, metadata: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(metadata, parent)
        self._line = QLineEdit(self)
        self._button = QPushButton("…", self)
        self._button.setFixedWidth(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._line, 1)
        layout.addWidget(self._button)
        self._line.textEdited.connect(self.valueChanged)
        self._button.clicked.connect(self._choose_color)

    def _choose_color(self) -> None:
        current = QColor(self._line.text())
        color = QColorDialog.getColor(current, self, "Выбор цвета")
        if color.isValid():
            with SignalBlocker(self._line):
                self._line.setText(color.name())
            self.valueChanged.emit(self.value())

    def set_value(self, value: Any) -> None:
        with SignalBlocker(self._line):
            if isinstance(value, str) and value:
                self._line.setText(value)
            else:
                default = self.metadata.get("default")
                self._line.setText(str(default or "#ffffff"))

    def value(self) -> str:
        return self._line.text()

    def focus_editor(self) -> None:
        self._line.setFocus(Qt.TabFocusReason)


class AnyEditor(StringEditor):
    """Fallback editor that uses line edit and string representation."""

    def value(self) -> Any:
        text = super().value()
        return text


def create_editor(metadata: dict) -> BaseParamEditor:
    """Create an editor widget suitable for the given parameter metadata."""

    param_type = str(metadata.get("type") or "string").lower()
    if param_type in {"int", "integer"}:
        return IntEditor(metadata)
    if param_type in {"float", "double"}:
        return FloatEditor(metadata)
    if param_type in {"number"}:
        return FloatEditor(metadata)
    if param_type == "enum":
        return EnumEditor(metadata)
    if param_type in {"bool", "boolean"}:
        return BoolEditor(metadata)
    if param_type == "color":
        return ColorEditor(metadata)
    if param_type in {"string"}:
        return StringEditor(metadata)
    return AnyEditor(metadata)


class SignalBlocker:
    """Context manager to temporarily block widget signals."""

    def __init__(self, widget: QWidget) -> None:
        self._widget = widget
        self._state: Optional[bool] = None

    def __enter__(self) -> None:
        self._state = self._widget.blockSignals(True)

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._state is not None:
            self._widget.blockSignals(self._state)
        self._state = None


__all__ = ["BaseParamEditor", "create_editor"]
