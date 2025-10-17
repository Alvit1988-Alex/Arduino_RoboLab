"""Генерация Arduino-кода из AST."""
from __future__ import annotations

from collections import defaultdict, OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Mapping, MutableMapping, Optional

from app.core.ast.ast_nodes import (
    BlockDefinition,
    BlockInstance,
    BlockRegistry,
    BoardProfile,
    ProgramNode,
    Section,
)


INDENT = "  "


@dataclass
class SketchBundle:
    """Результат генерации: код и маппинг строк."""

    code: str
    mapping: Dict[str, List[int]]
    sections: Dict[Section, List[str]]


class CodeGenerationError(RuntimeError):
    """Ошибки генерации."""


class CodeGenerator:
    """Преобразует AST в текст скетча Arduino."""

    def __init__(self, registry: BlockRegistry, board: BoardProfile):
        self.registry = registry
        self.board = board
        self.section_lines: Dict[Section, List[tuple[str, Optional[str]]]] = {
            Section.INCLUDES: [],
            Section.GLOBALS: [],
            Section.SETUP: [],
            Section.LOOP: [],
            Section.FUNCTIONS: [],
        }
        self._include_cache: OrderedDict[str, Optional[str]] = OrderedDict()
        self._line_mapping: Dict[str, List[int]] = defaultdict(list)

    def build(self, program: ProgramNode) -> SketchBundle:
        if program.root is None:
            raise CodeGenerationError("Нет корневого блока EV_START")

        self._add_include("#include <Arduino.h>", None)
        self._process_block(program.root, target_section=None, indent_level=0)
        code = self._assemble_code()
        return SketchBundle(code=code, mapping=dict(self._line_mapping), sections=self._sections_as_text())

    def _process_block(
        self, block: BlockInstance, target_section: Optional[Section], indent_level: int
    ) -> Optional[str]:
        definition = self._get_definition(block.definition_id)
        context = self._build_context(block, definition)

        for include in definition.includes:
            self._add_include(include.format(**context), block.instance_id)
        for snippet in definition.globals_snippets:
            self._add_line(Section.GLOBALS, self._format(snippet, context, indent=0), block.instance_id)
        for snippet in definition.functions_snippets:
            self._add_line(Section.FUNCTIONS, snippet.format(**context), block.instance_id)
        for snippet in definition.setup_snippets:
            formatted = self._format(snippet, context, indent=1)
            self._add_line(Section.SETUP, formatted, block.instance_id)

        if definition.template:
            section = definition.section or target_section
            if section is None:
                raise CodeGenerationError(
                    f"Блок {definition.block_id} не привязан к секции и не передан target_section"
                )
            rendered = self._render_template(definition, block, context, indent_level)
            if rendered:
                for line in rendered.splitlines():
                    self._add_line(section, line, block.instance_id)
            return rendered

        # Если блок не имеет собственного шаблона, просто обработать дочерние контейнеры
        for container in definition.containers:
            for child in block.children.get(container.name, []):
                child_indent = 1 if container.section in {Section.SETUP, Section.LOOP} else 0
                self._process_block(child, container.section, child_indent)
        return None

    def _render_template(
        self, definition: BlockDefinition, block: BlockInstance, context: Mapping[str, object], indent_level: int
    ) -> str:
        template = definition.template or ""
        rendered_children: Dict[str, str] = {}
        for container in definition.containers:
            if container.placeholder is None:
                # Контейнер уже обработан в _process_block (например, EV_START)
                for child in block.children.get(container.name, []):
                    child_indent = 1 if container.section in {Section.SETUP, Section.LOOP} else 0
                    self._process_block(child, container.section, child_indent)
                rendered_children[container.name] = ""
                continue
            child_texts: List[str] = []
            for child in block.children.get(container.name, []):
                child_render = self._process_block(child, definition.section, indent_level + 1)
                if child_render:
                    child_texts.append(child_render)
            joined = "\n".join(filter(None, child_texts))
            if joined:
                joined = _indent_lines(joined, indent_level + 1)
            rendered_children[container.placeholder] = joined
        filled = template
        for placeholder, value in rendered_children.items():
            filled = filled.replace(f"{{{placeholder}}}", value)
        filled = self._format(filled, context, indent=indent_level)
        return filled

    def _assemble_code(self) -> str:
        lines: List[str] = []
        current_line_no = 0

        def emit(section: Section, header: Optional[str] = None) -> None:
            nonlocal current_line_no
            if header:
                lines.append(header)
                current_line_no += 1
            for text, block_id in self.section_lines[section]:
                lines.append(text)
                current_line_no += 1
                if block_id:
                    self._line_mapping.setdefault(block_id, []).append(current_line_no)
            if section in {Section.GLOBALS, Section.SETUP, Section.LOOP} and self.section_lines[section]:
                lines.append("")
                current_line_no += 1

        if self._include_cache:
            for include, block_id in self._include_cache.items():
                self.section_lines[Section.INCLUDES].append((include, block_id))
            self._include_cache.clear()
        emit(Section.INCLUDES)
        emit(Section.GLOBALS, "\n// ===== Globals =====")
        lines.append("void setup() {")
        current_line_no += 1
        if self.section_lines[Section.SETUP]:
            for text, block_id in self.section_lines[Section.SETUP]:
                lines.append(text)
                current_line_no += 1
                if block_id:
                    self._line_mapping.setdefault(block_id, []).append(current_line_no)
        lines.append("}")
        current_line_no += 1
        lines.append("")
        current_line_no += 1
        lines.append("void loop() {")
        current_line_no += 1
        if self.section_lines[Section.LOOP]:
            for text, block_id in self.section_lines[Section.LOOP]:
                lines.append(text)
                current_line_no += 1
                if block_id:
                    self._line_mapping.setdefault(block_id, []).append(current_line_no)
        lines.append("}")
        current_line_no += 1

        if self.section_lines[Section.FUNCTIONS]:
            lines.append("")
            current_line_no += 1
            for text, block_id in self.section_lines[Section.FUNCTIONS]:
                lines.append(text)
                current_line_no += 1
                if block_id:
                    self._line_mapping.setdefault(block_id, []).append(current_line_no)

        return "\n".join(lines).strip() + "\n"

    def _sections_as_text(self) -> Dict[Section, List[str]]:
        return {section: [line for line, _ in lines] for section, lines in self.section_lines.items()}

    def _add_include(self, include: str, block_id: Optional[str]) -> None:
        include = include.strip()
        if include not in self._include_cache:
            self._include_cache[include] = block_id

    def _add_line(self, section: Section, text: str, block_id: Optional[str]) -> None:
        if not text:
            return
        self.section_lines[section].append((text, block_id))

    def _build_context(self, block: BlockInstance, definition: BlockDefinition) -> MutableMapping[str, object]:
        context: Dict[str, object] = {param.name: block.values.get(param.name, param.default) for param in definition.parameters}
        context.setdefault("id", block.instance_id)
        return context

    def _get_definition(self, block_id: str) -> BlockDefinition:
        try:
            return self.registry.get(block_id)
        except KeyError as exc:
            raise CodeGenerationError(str(exc)) from exc

    @staticmethod
    def _format(template: str, context: Mapping[str, object], indent: int) -> str:
        if not template:
            return ""
        formatted = template
        for key, value in context.items():
            formatted = formatted.replace(f"{{{key}}}", str(value))
        return _indent_lines(formatted, indent)


def _indent_lines(text: str, indent_level: int) -> str:
    indent = INDENT * indent_level
    return "\n".join(f"{indent}{line}" if line else "" for line in text.splitlines())


def build_sketch(program: ProgramNode, registry: BlockRegistry, board: BoardProfile) -> SketchBundle:
    """Высокоуровневая функция генерации."""

    generator = CodeGenerator(registry, board)
    return generator.build(program)
