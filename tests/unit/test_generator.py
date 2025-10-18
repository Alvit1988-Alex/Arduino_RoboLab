"""Юнит-тесты генерации Arduino-кода."""
from pathlib import Path

import pytest

from app.core.ast.ast_nodes import BlockInstance, BlockRegistry, ProgramNode, load_board_profiles
from app.core.generator.codegen import build_sketch
from app.core.validator.validator import ProgramValidator
from app.core.blocks_loader import BlocksLoaderError, load_blocks

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load_registry() -> BlockRegistry:
    normalized = load_blocks(DATA_DIR / "blocks" / "blocks.json")
    try:
        payload = normalized.require_registry_payload()
    except BlocksLoaderError as exc:
        pytest.skip(f"Пропуск тестов генератора: {exc}")
    return BlockRegistry.from_mapping(payload)


def _load_board() -> tuple:
    profiles = load_board_profiles(DATA_DIR / "boards.json")
    return profiles["uno"]


def test_basic_led_program_generation() -> None:
    registry = _load_registry()
    board = _load_board()
    start = BlockInstance(
        instance_id="start",
        definition_id="EV_START",
        children={
            "setup": [],
            "loop": [
                BlockInstance("led_on", "LS_LED_ON", values={"pin": 13}),
                BlockInstance("delay", "TM_DELAY", values={"ms": 500}),
            ],
        },
    )
    program = ProgramNode(board_id="uno", root=start)

    validator = ProgramValidator(registry, board)
    errors = validator.validate(program)
    assert not errors, f"Ожидались отсутствие ошибок, получено: {[str(e) for e in errors]}"

    bundle = build_sketch(program, registry, board)
    code = bundle.code

    assert "#include <Arduino.h>" in code
    assert "pinMode(13, OUTPUT);" in code
    assert "digitalWrite(13, HIGH);" in code
    assert "delay(500);" in code
    assert bundle.mapping["led_on"], "Для блока led_on должен формироваться маппинг строк"


def test_if_block_renders_children() -> None:
    registry = _load_registry()
    board = _load_board()
    start = BlockInstance(
        instance_id="start",
        definition_id="EV_START",
        children={
            "setup": [],
            "loop": [
                BlockInstance(
                    "if1",
                    "CTL_IF",
                    values={"condition": "digitalRead(2) == LOW"},
                    children={
                        "then": [
                            BlockInstance("led", "LS_LED_ON", values={"pin": 12}),
                        ]
                    },
                )
            ],
        },
    )
    program = ProgramNode(board_id="uno", root=start)
    bundle = build_sketch(program, registry, board)

    assert "if (digitalRead(2) == LOW)" in bundle.code
    assert "digitalWrite(12, HIGH);" in bundle.code
