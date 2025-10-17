"""Сборка portable-версии Arduino RoboLab."""
from __future__ import annotations

import shutil
from pathlib import Path


ASSETS = [
    ("data", "data"),
    ("app", "app"),
    ("portable/Tools", "portable/Tools"),
]


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def build_portable(root: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    portable_root = output_dir / "ArduinoRoboLab"
    if portable_root.exists():
        shutil.rmtree(portable_root)
    portable_root.mkdir()
    for src_rel, dst_rel in ASSETS:
        src_path = root / src_rel
        dst_path = portable_root / dst_rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            copy_tree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "dist" / "portable"
    build_portable(repo_root, dist_dir)
    print(f"Portable сборка создана в {dist_dir}")
