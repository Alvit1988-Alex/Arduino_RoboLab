"""Модель AST визуальных блоков Arduino RoboLab."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

import json

from app.core.blocks_loader import BlocksLoaderError, load_blocks


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
        normalized = load_blocks(path)
        try:
            payload = normalized.require_registry_payload()
        except BlocksLoaderError as exc:
            raise BlocksLoaderError(
                f"Не удалось получить определения блоков из {path}: {exc}"
            ) from exc
        return cls.from_mapping(payload)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BlockRegistry":
        definitions: Dict[str, BlockDefinition] = {}
        categories = payload.get("categories", {})
        blocks_data = payload.get("blocks", [])
        if not isinstance(blocks_data, Iterable):
            raise BlocksLoaderError("Секция 'blocks' должна быть списком")

        def _string_list(value: Any) -> List[str]:
            if isinstance(value, str):
                return [value]
            if isinstance(value, Iterable):
                return [str(item) for item in value if isinstance(item, str)]
            return []

        for block_data in blocks_data:
            if not isinstance(block_data, Mapping):
                continue
            try:
                block_id = str(block_data["id"])
                name = str(block_data["name"])
                category = str(block_data["category"])
                kind = str(block_data["kind"])
            except KeyError as exc:
                raise BlocksLoaderError(
                    "Определение блока отсутствует или содержит неполные данные"
                ) from exc

            containers = []
            for item in block_data.get("containers", []):
                if not isinstance(item, Mapping):
                    continue
                try:
                    container_name = str(item["name"])
                    section = Section.from_string(str(item["section"]))
                except (KeyError, ValueError) as exc:
                    raise BlocksLoaderError(
                        f"Некорректное описание контейнера блока {block_id}"
                    ) from exc
                placeholder = item.get("placeholder")
                containers.append(
                    BlockContainerSpec(
                        name=container_name,
                        section=section,
                        placeholder=placeholder if isinstance(placeholder, str) else None,
                    )
                )

            parameters: List[BlockParameter] = []
            for param in block_data.get("parameters", []):
                if not isinstance(param, Mapping):
                    continue
                try:
                    param_name = str(param["name"])
                    param_type = str(param["type"])
                except KeyError as exc:
                    raise BlocksLoaderError(
                        f"Некорректное описание параметра блока {block_id}"
                    ) from exc
                parameters.append(
                    BlockParameter(
                        name=param_name,
                        type=param_type,
                        default=param.get("default"),
                    )
                )

            section_value = block_data.get("section")
            if isinstance(section_value, str) and section_value:
                section = Section.from_string(section_value)
            else:
                section = None

            definitions[block_id] = BlockDefinition(
                block_id=block_id,
                name=name,
                category=category,
                kind=kind,
                section=section,
                template=block_data.get("template"),
                returns=block_data.get("returns"),
                parameters=parameters,
                setup_snippets=_string_list(block_data.get("setup", [])),
                globals_snippets=_string_list(block_data.get("globals", [])),
                includes=_string_list(block_data.get("includes", [])),
                functions_snippets=_string_list(block_data.get("functions", [])),
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
