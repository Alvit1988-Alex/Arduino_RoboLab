"""Модель AST визуальных блоков Arduino RoboLab."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional

import json


class Section(Enum):
    """Разделы итогового Arduino-скетча."""

    INCLUDES = "includes"
    GLOBALS = "globals"
    SETUP = "setup"
    LOOP = "loop"
    FUNCTIONS = "functions"

    @classmethod
    def from_string(cls, value: str) -> "Section":
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Неизвестный раздел секции: {value}") from exc


@dataclass(frozen=True)
class BlockParameter:
    """Описание параметра блока."""

    name: str
    type: str
    default: object | None = None


@dataclass(frozen=True)
class BlockContainerSpec:
    """Описание контейнера блока (для дочерних блоков)."""

    name: str
    section: Section
    placeholder: Optional[str] = None


@dataclass(frozen=True)
class BlockDefinition:
    """Метаданные блока, загружаемые из JSON."""

    block_id: str
    name: str
    category: str
    kind: str
    section: Optional[Section]
    template: Optional[str]
    returns: Optional[str]
    parameters: List[BlockParameter] = field(default_factory=list)
    setup_snippets: List[str] = field(default_factory=list)
    globals_snippets: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    functions_snippets: List[str] = field(default_factory=list)
    containers: List[BlockContainerSpec] = field(default_factory=list)

    @property
    def is_expression(self) -> bool:
        return self.kind == "expression"


@dataclass
class BlockInstance:
    """Конкретный блок на канве с параметрами и дочерними блоками."""

    instance_id: str
    definition_id: str
    values: MutableMapping[str, object] = field(default_factory=dict)
    children: MutableMapping[str, List["BlockInstance"]] = field(default_factory=dict)

    def iter_children(self) -> Iterable["BlockInstance"]:
        for blocks in self.children.values():
            for block in blocks:
                yield block


@dataclass
class ProgramNode:
    """AST всей программы (проект)."""

    board_id: str
    root: Optional[BlockInstance] = None
    metadata: MutableMapping[str, object] = field(default_factory=dict)

    def iter_blocks(self) -> Iterable[BlockInstance]:
        if not self.root:
            return []

        stack = [self.root]
        while stack:
            block = stack.pop()
            yield block
            stack.extend(reversed(list(block.iter_children())))


class BlockRegistry:
    """Загрузка и предоставление определений блоков из JSON."""

    def __init__(self, definitions: Mapping[str, BlockDefinition], categories: Mapping[str, Mapping[str, str]]):
        self._definitions = dict(definitions)
        self.categories = dict(categories)

    def get(self, block_id: str) -> BlockDefinition:
        try:
            return self._definitions[block_id]
        except KeyError as exc:
            raise KeyError(f"Неизвестный блок '{block_id}'") from exc

    @classmethod
    def load_from_file(cls, path: Path) -> "BlockRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        definitions: Dict[str, BlockDefinition] = {}
        categories = data.get("categories", {})
        for block_data in data.get("blocks", []):
            containers = [
                BlockContainerSpec(
                    name=item["name"],
                    section=Section.from_string(item["section"]),
                    placeholder=item.get("placeholder"),
                )
                for item in block_data.get("containers", [])
            ]
            parameters = [
                BlockParameter(name=p["name"], type=p["type"], default=p.get("default"))
                for p in block_data.get("parameters", [])
            ]
            section_value = block_data.get("section")
            section = Section.from_string(section_value) if section_value else None
            definitions[block_data["id"]] = BlockDefinition(
                block_id=block_data["id"],
                name=block_data["name"],
                category=block_data["category"],
                kind=block_data["kind"],
                section=section,
                template=block_data.get("template"),
                returns=block_data.get("returns"),
                parameters=parameters,
                setup_snippets=block_data.get("setup", []),
                globals_snippets=block_data.get("globals", []),
                includes=block_data.get("includes", []),
                functions_snippets=block_data.get("functions", []),
                containers=containers,
            )
        return cls(definitions, categories)

    def __contains__(self, block_id: str) -> bool:
        return block_id in self._definitions

    def values(self) -> Iterable[BlockDefinition]:
        return self._definitions.values()


@dataclass
class BoardPinCapabilities:
    """Описание возможностей платы."""

    digital: List[int]
    pwm: List[int]
    analog: List[str]


@dataclass
class BoardProfile:
    """Описание платы (идентификатор и команды прошивки)."""

    board_id: str
    name: str
    fqbn: str
    upload_command: str
    upload_tool: str
    upload_speed: int
    pins: BoardPinCapabilities


def load_board_profiles(path: Path) -> Dict[str, BoardProfile]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    profiles: Dict[str, BoardProfile] = {}
    for board in data.get("boards", []):
        pins = board.get("pins", {})
        profiles[board["id"]] = BoardProfile(
            board_id=board["id"],
            name=board.get("name", board["id"]),
            fqbn=board.get("fqbn", board["id"]),
            upload_command=board.get("upload", {}).get("command", ""),
            upload_tool=board.get("upload", {}).get("tool", ""),
            upload_speed=board.get("upload", {}).get("speed", 115200),
            pins=BoardPinCapabilities(
                digital=[int(p) for p in pins.get("digital", [])],
                pwm=[int(p) for p in pins.get("pwm", [])],
                analog=[str(p) for p in pins.get("analog", [])],
            ),
        )
    return profiles
