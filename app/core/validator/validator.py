"""Валидатор AST программ Arduino RoboLab."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.core.ast.ast_nodes import BlockInstance, BlockRegistry, BoardProfile, ProgramNode, Section


@dataclass
class ValidationError:
    """Описание ошибки валидации."""

    message: str
    block_id: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - для удобного вывода
        if self.block_id:
            return f"[{self.block_id}] {self.message}"
        return self.message


class ProgramValidator:
    """Проверяет AST на совместимость с выбранной платой и определениями блоков."""

    def __init__(self, registry: BlockRegistry, board: BoardProfile):
        self.registry = registry
        self.board = board

    def validate(self, program: ProgramNode) -> List[ValidationError]:
        errors: List[ValidationError] = []
        if program.root is None:
            errors.append(ValidationError("Проект не содержит корневого блока EV_START"))
            return errors

        encountered_sections = {Section.INCLUDES, Section.GLOBALS, Section.SETUP, Section.LOOP, Section.FUNCTIONS}
        used_sections = set()

        def walk(block: BlockInstance) -> None:
            try:
                definition = self.registry.get(block.definition_id)
            except KeyError:
                errors.append(ValidationError("Неизвестный тип блока", block.instance_id))
                return

            if definition.section:
                used_sections.add(definition.section)
            if definition.setup_snippets:
                used_sections.add(Section.SETUP)
            if definition.globals_snippets:
                used_sections.add(Section.GLOBALS)

            for param in definition.parameters:
                value = block.values.get(param.name, param.default)
                if value is None:
                    errors.append(
                        ValidationError(f"Не задан параметр '{param.name}'", block.instance_id)
                    )
                    continue
                if param.type == "digital_pin":
                    self._validate_digital_pin(value, block, errors)
                elif param.type == "int":
                    self._ensure_int(value, param.name, block, errors)

            for container in definition.containers:
                for child in block.children.get(container.name, []):
                    walk(child)

        walk(program.root)

        if Section.LOOP not in used_sections:
            errors.append(ValidationError("В цикле loop() отсутствуют исполняемые блоки"))

        missing_sections = encountered_sections - used_sections - {Section.INCLUDES, Section.GLOBALS, Section.FUNCTIONS}
        for section in sorted(missing_sections, key=lambda s: s.value):
            if section in {Section.SETUP, Section.LOOP}:
                errors.append(ValidationError(f"Секция '{section.value}' пуста"))

        return errors

    def _validate_digital_pin(
        self, value: object, block: BlockInstance, errors: List[ValidationError]
    ) -> None:
        try:
            pin = int(str(value).replace("A", "")) if str(value).startswith("A") else int(value)
        except (TypeError, ValueError):
            errors.append(ValidationError("Неверный формат пина", block.instance_id))
            return
        if pin not in self.board.pins.digital:
            errors.append(ValidationError(f"Пин D{pin} недоступен для платы {self.board.name}", block.instance_id))

    @staticmethod
    def _ensure_int(value: object, name: str, block: BlockInstance, errors: List[ValidationError]) -> None:
        try:
            int(value)
        except (TypeError, ValueError):
            errors.append(ValidationError(f"Параметр '{name}' должен быть числом", block.instance_id))


def validate_program(program: ProgramNode, registry: BlockRegistry, board: BoardProfile) -> List[ValidationError]:
    """Удобная функция-обёртка."""

    return ProgramValidator(registry, board).validate(program)
