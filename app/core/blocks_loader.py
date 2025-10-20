"""Utilities for loading block metadata in different formats."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


class BlocksLoaderError(RuntimeError):
    """Raised when block metadata cannot be loaded or normalised."""


@dataclass(frozen=True)
class BlockParamSpec:
    """Description of a block parameter."""

    name: str
    type: Optional[str] = None
    default: Any = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = dict(self.raw) if self.raw else {"name": self.name}
        payload.setdefault("name", self.name)
        if self.type is not None:
            payload.setdefault("type", self.type)
        if self.default is not None and "default" not in payload:
            payload["default"] = self.default
        return payload


@dataclass(frozen=True)
class BlockPortSpec:
    """Description of a port that can be rendered in the palette."""

    name: str
    direction: str
    type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": self.name}
        if self.type is not None:
            payload["type"] = self.type
        return payload


@dataclass
class BlockSpec:
    """Normalised representation of a block definition."""

    identifier: str
    category: str
    title: str
    section: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    params: List[BlockParamSpec] = field(default_factory=list)
    ports: Dict[str, List[BlockPortSpec]] = field(default_factory=dict)
    default_params: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_palette_entry(self) -> Dict[str, Any]:
        """Return a dictionary compatible with the canvas palette."""

        payload: Dict[str, Any] = dict(self.raw) if self.raw else {}
        payload.setdefault("id", self.identifier)
        payload.setdefault("category", self.category)
        payload.setdefault("title", self.title)
        if self.section is not None:
            payload.setdefault("section", self.section)
        if self.description is not None:
            payload.setdefault("description", self.description)
        if self.color is not None:
            payload.setdefault("color", self.color)
        if "params" not in payload:
            payload["params"] = [param.to_dict() for param in self.params]
        if "ports" not in payload:
            payload["ports"] = {
                direction: [port.to_dict() for port in ports]
                for direction, ports in self.ports.items()
            }
        else:
            # Ensure ports dictionary has both keys even if source omitted them.
            ports_dict = payload.get("ports", {})
            if not isinstance(ports_dict, dict):
                ports_dict = {}
            for direction, ports in self.ports.items():
                ports_dict.setdefault(direction, [port.to_dict() for port in ports])
            ports_dict.setdefault("inputs", ports_dict.get("inputs", []))
            ports_dict.setdefault("outputs", ports_dict.get("outputs", []))
            payload["ports"] = ports_dict
        if self.default_params and "default_params" not in payload:
            payload["default_params"] = dict(self.default_params)
        if self.aliases and "aliases" not in payload:
            payload["aliases"] = list(self.aliases)
        return payload


@dataclass
class NormalizedBlocks:
    """Container with block specifications and registry payload."""

    blocks: List[BlockSpec]
    by_category: Dict[str, List[BlockSpec]]
    registry_payload: Optional[Dict[str, Any]]
    source_format: str
    path: Path
    aliases_map: Dict[str, str]

    def palette_entries(self) -> List[Dict[str, Any]]:
        return [spec.to_palette_entry() for spec in self.blocks]

    def require_registry_payload(self) -> Dict[str, Any]:
        if self.registry_payload is None:
            raise BlocksLoaderError(
                "Файл blocks.json не содержит сведений, необходимых для генератора кода"
            )
        return copy.deepcopy(self.registry_payload)


def load_blocks(path: str | Path) -> NormalizedBlocks:
    """Load blocks metadata supporting both legacy (dict) and palette (list) formats."""

    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - configuration issue
        raise BlocksLoaderError(f"Не найден файл {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise BlocksLoaderError(f"Некорректный JSON в {file_path}: {exc}") from exc

    if isinstance(payload, list):
        return _load_from_list(file_path, payload)
    if isinstance(payload, Mapping):
        return _load_from_mapping(file_path, payload)
    raise BlocksLoaderError("Ожидался список или объект с блоками")


def _load_from_list(path: Path, payload: List[Any]) -> NormalizedBlocks:
    blocks: List[BlockSpec] = []
    alias_map: Dict[str, str] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        identifier = str(entry.get("id", "")).strip()
        category = str(entry.get("category", "")).strip()
        if not identifier or not category:
            continue
        title = str(entry.get("title") or identifier)
        section_value = entry.get("section")
        section = str(section_value) if isinstance(section_value, str) else None
        description = entry.get("description")
        description = str(description) if isinstance(description, str) else None
        color_value = entry.get("color")
        color = str(color_value) if isinstance(color_value, str) else None
        params = _parse_params(entry.get("params", []))
        ports = _parse_ports(entry.get("ports", {}))
        default_params = entry.get("default_params") if isinstance(entry.get("default_params"), dict) else {}
        aliases = _parse_aliases(entry.get("aliases"))
        for alias in aliases:
            alias_map.setdefault(alias, identifier)
        blocks.append(
            BlockSpec(
                identifier=identifier,
                category=category,
                title=title,
                section=section,
                description=description,
                color=color,
                params=params,
                ports=ports,
                default_params=dict(default_params),
                aliases=aliases,
                raw=dict(entry),
            )
        )

    by_category = _group_by_category(blocks)
    registry_payload = _fallback_registry_payload()
    return NormalizedBlocks(
        blocks=blocks,
        by_category=by_category,
        registry_payload=registry_payload,
        source_format="list",
        path=path,
        aliases_map=alias_map,
    )


def _load_from_mapping(path: Path, payload: Mapping[str, Any]) -> NormalizedBlocks:
    blocks_data = payload.get("blocks")
    if not isinstance(blocks_data, list):
        raise BlocksLoaderError("В объекте blocks.json отсутствует массив blocks")
    categories_meta = payload.get("categories", {})
    blocks: List[BlockSpec] = []
    alias_map: Dict[str, str] = {}
    for entry in blocks_data:
        if not isinstance(entry, Mapping):
            continue
        identifier = str(entry.get("id", "")).strip()
        category = str(entry.get("category", "")).strip()
        if not identifier or not category:
            continue
        title_source = entry.get("title") or entry.get("name") or identifier
        title = str(title_source)
        section_value = entry.get("section")
        section = str(section_value) if isinstance(section_value, str) else None
        description = entry.get("description")
        description = str(description) if isinstance(description, str) else None
        color = None
        if "color" in entry and isinstance(entry["color"], str):
            color = entry["color"]
        elif category in categories_meta:
            color_meta = categories_meta.get(category, {})
            color_value = color_meta.get("color") if isinstance(color_meta, Mapping) else None
            if isinstance(color_value, str):
                color = color_value
        params = _parse_params(entry.get("parameters", []))
        ports = _parse_ports(entry.get("ports", {}))
        default_params = entry.get("default_params") if isinstance(entry.get("default_params"), dict) else {}
        aliases = _parse_aliases(entry.get("aliases"))
        for alias in aliases:
            alias_map.setdefault(alias, identifier)
        blocks.append(
            BlockSpec(
                identifier=identifier,
                category=category,
                title=title,
                section=section,
                description=description,
                color=color,
                params=params,
                ports=ports,
                default_params=dict(default_params),
                aliases=aliases,
                raw=dict(entry),
            )
        )

    by_category = _group_by_category(blocks)
    registry_payload = copy.deepcopy(dict(payload))
    return NormalizedBlocks(
        blocks=blocks,
        by_category=by_category,
        registry_payload=registry_payload,
        source_format="mapping",
        path=path,
        aliases_map=alias_map,
    )


def _parse_params(data: Any) -> List[BlockParamSpec]:
    params: List[BlockParamSpec] = []
    if not isinstance(data, Iterable):
        return params
    for descriptor in data:
        if not isinstance(descriptor, Mapping):
            continue
        name = str(descriptor.get("name", "")).strip()
        if not name:
            continue
        type_value = descriptor.get("type")
        param_type = str(type_value) if isinstance(type_value, str) else None
        params.append(
            BlockParamSpec(
                name=name,
                type=param_type,
                default=descriptor.get("default"),
                raw=dict(descriptor),
            )
        )
    return params


def _parse_aliases(data: Any) -> List[str]:
    aliases: List[str] = []
    if not isinstance(data, Iterable):
        return aliases
    for alias in data:
        if isinstance(alias, str):
            value = alias.strip()
            if value:
                aliases.append(value)
    return aliases


def _parse_ports(data: Any) -> Dict[str, List[BlockPortSpec]]:
    ports: Dict[str, List[BlockPortSpec]] = {"inputs": [], "outputs": []}
    if not isinstance(data, Mapping):
        return ports
    for direction in ("inputs", "outputs"):
        items = data.get(direction, [])
        if not isinstance(items, Iterable):
            continue
        result: List[BlockPortSpec] = []
        for descriptor in items:
            if not isinstance(descriptor, Mapping):
                continue
            name = str(descriptor.get("name", "")).strip()
            if not name:
                continue
            type_value = descriptor.get("type")
            dtype = str(type_value) if isinstance(type_value, str) else None
            result.append(BlockPortSpec(name=name, direction=direction, type=dtype))
        ports[direction] = result
    return ports


def _group_by_category(blocks: Iterable[BlockSpec]) -> Dict[str, List[BlockSpec]]:
    grouped: Dict[str, List[BlockSpec]] = {}
    for block in blocks:
        grouped.setdefault(block.category, []).append(block)
    return grouped


def _fallback_registry_payload() -> Dict[str, Any]:
    """Provide minimal generator definitions for environments with palette-only data."""

    fallback = {
        "version": 1,
        "categories": {
            "events": {"title": "События", "color": "#607D8B"},
            "logic": {"title": "Логика", "color": "#4CAF50"},
            "timing": {"title": "Таймер", "color": "#FFC107"},
        },
        "blocks": [
            {
                "id": "EV_START",
                "name": "Старт",
                "category": "events",
                "kind": "event",
                "containers": [
                    {"name": "setup", "section": "setup"},
                    {"name": "loop", "section": "loop"},
                ],
            },
            {
                "id": "LS_LED_ON",
                "name": "Включить светодиод",
                "category": "logic",
                "kind": "statement",
                "section": "loop",
                "template": "digitalWrite({pin}, HIGH);",
                "parameters": [
                    {"name": "pin", "type": "int", "default": 13},
                ],
                "setup": ["pinMode({pin}, OUTPUT);"]
            },
            {
                "id": "TM_DELAY",
                "name": "Задержка",
                "category": "timing",
                "kind": "statement",
                "section": "loop",
                "template": "delay({ms});",
                "parameters": [
                    {"name": "ms", "type": "int", "default": 1000},
                ],
            },
            {
                "id": "CTL_IF",
                "name": "Если",
                "category": "logic",
                "kind": "statement",
                "section": "loop",
                "template": "if ({condition}) {\n{then}\n}",
                "parameters": [
                    {"name": "condition", "type": "string", "default": "true"},
                ],
                "containers": [
                    {"name": "then", "section": "loop", "placeholder": "then"},
                ],
            },
        ],
    }
    return fallback
