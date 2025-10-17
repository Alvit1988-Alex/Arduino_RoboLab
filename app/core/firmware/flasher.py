"""Инструменты компиляции и прошивки."""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from app.core.ast.ast_nodes import BoardProfile


@dataclass
class CommandResult:
    """Результат выполнения внешней команды."""

    command: List[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


@dataclass
class CompileError:
    """Описание ошибки компиляции."""

    file: str
    line: int
    column: Optional[int]
    message: str


class FirmwareFlasher:
    """Обёртка над arduino-cli и инструментами загрузки."""

    def __init__(self, tools_root: Path, runner: Optional[Callable[[List[str]], CommandResult]] = None):
        self.tools_root = Path(tools_root)
        self._runner = runner or self._default_runner

    def compile(self, sketch_dir: Path, board: BoardProfile) -> CommandResult:
        """Сборка скетча через arduino-cli."""

        cli_path = self.tools_root / "ArduinoCLI" / "arduino-cli"
        command = [str(cli_path), "compile", "--fqbn", board.fqbn, str(sketch_dir)]
        return self._run(command)

    def flash(self, hex_path: Path, board: BoardProfile, port: str) -> CommandResult:
        """Прошивка платы согласно профилю."""

        tool_path = self._resolve_tool(board.upload_tool)
        context = {
            "avrdude": str(tool_path),
            "port": port,
            "hex_path": str(hex_path),
            "speed": board.upload_speed,
        }
        command_str = board.upload_command.format(**context)
        command = shlex.split(command_str)
        return self._run(command)

    def _resolve_tool(self, tool: str) -> Path:
        mapping = {
            "avrdude": self.tools_root / "Tools" / "avrdude" / "avrdude.exe",
            "esptool": self.tools_root / "Tools" / "esptool.py",
            "picotool": self.tools_root / "Tools" / "picotool.exe",
        }
        path = mapping.get(tool, self.tools_root / tool)
        return path

    @staticmethod
    def _default_runner(command: List[str]) -> CommandResult:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return CommandResult(command=list(command), returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)

    def _run(self, command: List[str]) -> CommandResult:
        return self._runner(command)


def parse_compile_errors(output: str) -> List[CompileError]:
    """Разбор вывода компилятора для выделения ошибок."""

    errors: List[CompileError] = []
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        filename, line_no, column, message_part = parts[0], parts[1], parts[2], ":".join(parts[3:])
        try:
            line_int = int(line_no)
            column_int = int(column)
        except ValueError:
            continue
        message = message_part.strip()
        if "error" in message.lower():
            errors.append(CompileError(filename, line_int, column_int, message))
    return errors
