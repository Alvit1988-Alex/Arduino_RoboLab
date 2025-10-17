"""Упаковка portable-версии Arduino RoboLab."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_portable(portable_dir: Path, output_zip: Path) -> Path:
    portable_dir = portable_dir.resolve()
    output_zip = output_zip.resolve()
    if output_zip.exists():
        output_zip.unlink()
    archive_path = shutil.make_archive(output_zip.as_posix(), "zip", root_dir=portable_dir)
    checksum_path = output_zip.with_name("checksums.txt")
    checksum_path.write_text(f"{_checksum(Path(archive_path))}  {Path(archive_path).name}\n", encoding="utf-8")
    return Path(archive_path)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    portable_dir = root / "dist" / "portable"
    output_zip = root / "dist" / "ArduinoRoboLab_portable"
    archive = package_portable(portable_dir, output_zip)
    print(f"Portable archive создан: {archive}")
