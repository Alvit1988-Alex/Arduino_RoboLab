# app/smoke_ci.py
from __future__ import annotations
import sys, os, ast, io, traceback
from typing import List, Tuple

# Абсолютный путь к корню пакета app/
APP_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))

FILES_AST_CHECK = [
    "app/ui/main_window.py",
    "app/ui/canvas/model.py",
    "app/ui/canvas/items.py",
    "app/ui/canvas/canvas_scene.py",
    "app/ui/widgets/block_list.py",
    "app/ui/widgets/canvas_view.py",
    "app/ui/widgets/code_panel.py",
]

def read_text(path: str) -> str:
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()

def ast_parse_ok(path: str) -> Tuple[bool, str]:
    try:
        src = read_text(path)
        ast.parse(src, filename=path)
        return True, ""
    except SyntaxError as e:
        return False, f"{path}: SyntaxError: {e}"
    except Exception as e:
        return False, f"{path}: Unexpected error: {e}"

def must_contain(text: str, needle: str, label: str) -> Tuple[bool, str]:
    if needle in text:
        return True, ""
    return False, f"{label} not found"

def main() -> int:
    errors: List[str] = []

    # 1) Проверка наличия файлов
    for rel in FILES_AST_CHECK:
        abspath = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(abspath):
            errors.append(f"Missing file: {rel}")

    # 2) AST-парсинг (не требует PySide6)
    for rel in FILES_AST_CHECK:
        abspath = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(abspath):
            continue
        ok, msg = ast_parse_ok(abspath)
        if not ok:
            errors.append(msg)

    # 3) Инварианты по содержимому
    try:
        mime_src = read_text(os.path.join(REPO_ROOT, "app/ui/common/mime.py"))
        ok, msg = must_contain(
            mime_src,
            'BLOCK_MIME = "application/x-robolab-block"',
            "BLOCK_MIME constant",
        )
        if not ok:
            errors.append(f"mime.py: {msg}")
    except Exception as e:
        errors.append(f"mime.py read failed: {e}")

    try:
        scene_src = read_text(os.path.join(REPO_ROOT, "app/ui/canvas/canvas_scene.py"))
        ok, msg = must_contain(
            scene_src,
            "from ..common.mime import BLOCK_MIME",
            "canvas_scene imports BLOCK_MIME",
        )
        if not ok:
            errors.append(f"canvas_scene.py: {msg}")
        if "MIME_BLOCK" in scene_src:
            errors.append("canvas_scene.py: legacy MIME_BLOCK symbol detected")
        if "<<<<<<<" in scene_src or "=======" in scene_src or ">>>>>>>" in scene_src:
            errors.append("canvas_scene.py: merge markers detected")
    except Exception as e:
        errors.append(f"canvas_scene.py read failed: {e}")

    try:
        block_list_src = read_text(os.path.join(REPO_ROOT, "app/ui/widgets/block_list.py"))
        ok, msg = must_contain(
            block_list_src,
            "mime.setData(BLOCK_MIME",
            "block_list uses shared BLOCK_MIME",
        )
        if not ok:
            errors.append(f"block_list.py: {msg}")
        if "from ..common.mime import BLOCK_MIME" not in block_list_src:
            errors.append("block_list.py: BLOCK_MIME import missing")
    except Exception as e:
        errors.append(f"block_list.py read failed: {e}")

    try:
        items_src = read_text(os.path.join(REPO_ROOT, "app/ui/canvas/items.py"))
        for cls in ["class BlockItem", "class PortItem", "class ConnectionItem"]:
            ok, msg = must_contain(items_src, cls, f"{cls} declaration")
            if not ok:
                errors.append(f"items.py: {msg}")
        if "<<<<<<<" in items_src or "=======" in items_src or ">>>>>>>" in items_src:
            errors.append("items.py: merge markers detected")
    except Exception as e:
        errors.append(f"items.py read failed: {e}")

    # 4) Безопасный импорт только модели (без PySide6)
    try:
        import importlib
        model = importlib.import_module("app.ui.canvas.model")
        assert hasattr(model, "BlockInstance"), "BlockInstance not found"
        assert hasattr(model, "ConnectionModel"), "ConnectionModel not found"
        assert hasattr(model, "ProjectModel"), "ProjectModel not found"
    except Exception:
        errors.append("Import error in app.ui.canvas.model:\n" + traceback.format_exc())

    if errors:
        print("SMOKE CI: FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("SMOKE CI: OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
