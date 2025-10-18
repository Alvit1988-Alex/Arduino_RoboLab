"""Проверка структуры файла data/blocks/blocks.json."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.blocks_loader import load_blocks


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "blocks" / "blocks.json"
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_palette_entries() -> list[dict]:
    normalized = load_blocks(DATA_PATH)
    return [spec.to_palette_entry() for spec in normalized.blocks]


def test_blocks_collection_has_expected_size() -> None:
    blocks = load_palette_entries()
    assert len(blocks) >= 150, "Палитра должна содержать минимум 150 блоков"


@pytest.mark.parametrize("key", ["id", "category", "title", "section", "color"])
def test_blocks_have_required_fields(key: str) -> None:
    blocks = load_palette_entries()
    for block in blocks:
        assert isinstance(block, dict)
        value = block.get(key)
        assert isinstance(value, str) and value.strip(), f"Поле {key} должно быть строкой"


def test_block_colors_are_hex() -> None:
    blocks = load_palette_entries()
    for block in blocks:
        color = block.get("color", "")
        assert isinstance(color, str)
        assert HEX_COLOR_RE.match(color), f"Некорректный цвет: {color!r}"


def test_block_ids_unique() -> None:
    blocks = load_palette_entries()
    seen: set[str] = set()
    for block in blocks:
        block_id = block.get("id")
        assert isinstance(block_id, str)
        assert block_id not in seen, f"Дублирующийся id блока: {block_id}"
        seen.add(block_id)


def test_ports_and_params_shapes() -> None:
    blocks = load_palette_entries()
    for block in blocks:
        ports = block.get("ports", {})
        assert isinstance(ports, dict)
        for direction in ("inputs", "outputs"):
            port_list = ports.get(direction, [])
            assert isinstance(port_list, list)
            for port in port_list:
                assert isinstance(port, dict)
                name = port.get("name")
                assert isinstance(name, str) and name.strip()
        params = block.get("params", [])
        assert isinstance(params, list)
        for descriptor in params:
            assert isinstance(descriptor, dict)
            assert descriptor.get("name"), "Параметр должен содержать имя"
