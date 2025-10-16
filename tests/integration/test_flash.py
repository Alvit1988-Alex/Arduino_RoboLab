"""Интеграционные тесты модуля прошивки."""
from pathlib import Path

from app.core.ast.ast_nodes import load_board_profiles
from app.core.firmware.flasher import CommandResult, FirmwareFlasher, parse_compile_errors

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class StubRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> CommandResult:
        self.commands.append(command)
        return CommandResult(command=command, returncode=0, stdout="OK", stderr="")


def test_compile_command_generation(tmp_path: Path) -> None:
    profiles = load_board_profiles(DATA_DIR / "boards.json")
    board = profiles["uno"]
    runner = StubRunner()
    flasher = FirmwareFlasher(Path("portable"), runner=runner)
    sketch_dir = tmp_path / "sketch"
    sketch_dir.mkdir()

    result = flasher.compile(sketch_dir, board)

    assert result.success
    assert runner.commands[0][0].endswith("arduino-cli")
    assert "--fqbn" in runner.commands[0]
    assert str(sketch_dir) in runner.commands[0]


def test_flash_command_and_error_parsing(tmp_path: Path) -> None:
    profiles = load_board_profiles(DATA_DIR / "boards.json")
    board = profiles["uno"]
    runner = StubRunner()
    flasher = FirmwareFlasher(Path("portable"), runner=runner)
    hex_path = tmp_path / "build" / "project.ino.hex"
    hex_path.parent.mkdir()
    hex_path.write_text("dummy", encoding="utf-8")

    result = flasher.flash(hex_path, board, "COM5")

    assert result.success
    command = runner.commands[-1]
    assert str(hex_path) in command[-1]
    assert any("COM5" in part for part in command)

    errors = parse_compile_errors(
        "sketch.ino:12:5: error: 'foo' was not declared in this scope\n" "sketch.ino:20:1: warning: unused variable"
    )
    assert len(errors) == 1
    assert errors[0].line == 12
    assert "foo" in errors[0].message
