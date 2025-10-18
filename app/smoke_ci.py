# app/smoke_ci.py
from __future__ import annotations
import sys, os, ast, io, json, traceback
from typing import Dict, List, Tuple

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

def _simulate_default_merge() -> Dict[str, object]:
    """Reproduce the add_block_at default merge snippet for verification."""

    namespace: Dict[str, object] = {}
    exec(
        "def merge(metadata, params):\n"
        "    defaults = {}\n"
        "    catalog_defaults = metadata.get('default_params')\n"
        "    if isinstance(catalog_defaults, dict):\n"
        "        defaults.update({str(k): v for k, v in catalog_defaults.items()})\n"
        "    else:\n"
        "        params_meta = metadata.get('params')\n"
        "        if isinstance(params_meta, list):\n"
        "            for descriptor in params_meta:\n"
        "                if not isinstance(descriptor, dict):\n"
        "                    continue\n"
        "                name = descriptor.get('name')\n"
        "                if name is not None:\n"
        "                    defaults[str(name)] = descriptor.get('default')\n"
        "    if isinstance(params, dict):\n"
        "        for k, v in params.items():\n"
        "            defaults[str(k)] = v\n"
        "    return defaults\n",
        namespace,
    )

    metadata = {
        "default_params": {"threshold": 0.5, 7: "lucky"},
        "params": [
            {"name": "mode", "default": "auto"},
            "garbage",
            {"name": "threshold", "default": 0.25},
        ],
    }
    overrides = {"mode": "manual", 11: 42}
    merged = namespace["merge"](metadata, overrides)
    return merged


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
        if "catalog_defaults = metadata.get(\"default_params\")" not in scene_src:
            errors.append("canvas_scene.py: default_params merge block missing")
        if "MIME_BLOCK" in scene_src:
            errors.append("canvas_scene.py: legacy MIME_BLOCK symbol detected")
        if "<<<<<<<" in scene_src or "=======" in scene_src or ">>>>>>>" in scene_src:
            errors.append("canvas_scene.py: merge markers detected")
        if "QApplication.focusWidget" not in scene_src:
            errors.append("canvas_scene.py: focus guard for Delete missing")
        if "def delete_selection" not in scene_src:
            errors.append("canvas_scene.py: delete_selection helper missing")
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

    try:
        main_src = read_text(os.path.join(REPO_ROOT, "app/ui/main_window.py"))
        if "Удалить выделенное" not in main_src:
            errors.append("main_window.py: Delete action missing")
        if "QApplication.focusWidget" not in main_src:
            errors.append("main_window.py: focus guard missing")
        if "self._TEXT_INPUT_WIDGETS" not in main_src:
            errors.append("main_window.py: text input guard tuple missing")
    except Exception as e:
        errors.append(f"main_window.py read failed: {e}")

    # 4) Безопасный импорт только модели (без PySide6)
    try:
        import importlib

        model = importlib.import_module("app.ui.canvas.model")
        assert hasattr(model, "BlockInstance"), "BlockInstance not found"
        assert hasattr(model, "ConnectionModel"), "ConnectionModel not found"
        assert hasattr(model, "ProjectModel"), "ProjectModel not found"
        BlockInstance = model.BlockInstance
        ConnectionModel = model.ConnectionModel
        ProjectModel = model.ProjectModel

        scenario_model = ProjectModel()
        blocks = [
            BlockInstance(uid="A", type_id="logic/start"),
            BlockInstance(uid="B", type_id="logic/step"),
            BlockInstance(uid="C", type_id="logic/end"),
        ]
        for block in blocks:
            scenario_model.add_block(block)

        connection_ab = ConnectionModel("A", "out", "B", "in")
        connection_bc = ConnectionModel("B", "out", "C", "in")
        scenario_model.add_connection(connection_ab)
        scenario_model.add_connection(connection_bc)

        scenario_model.remove_connection(connection_ab)
        if len(scenario_model.connections) != 1:
            errors.append("ProjectModel: connection removal inconsistent")
        if any(conn.matches(connection_ab) for conn in scenario_model.connections):
            errors.append("ProjectModel: dangling reference to removed connection")

        scenario_model.remove_block("B")
        if any(block.uid == "B" for block in scenario_model.blocks):
            errors.append("ProjectModel: block removal failed")
        if any(
            conn.from_block_uid == "B" or conn.to_block_uid == "B"
            for conn in scenario_model.connections
        ):
            errors.append("ProjectModel: edges referencing removed block remain")

        serialised = scenario_model.to_dict()
        roundtrip = json.loads(json.dumps(serialised))
        restored = ProjectModel.from_dict(roundtrip)
        if any(
            conn.from_block_uid not in {block.uid for block in restored.blocks}
            or conn.to_block_uid not in {block.uid for block in restored.blocks}
            for conn in restored.connections
        ):
            errors.append("ProjectModel: roundtrip produced dangling connections")
    except Exception:
        errors.append("Import error in app.ui.canvas.model:\n" + traceback.format_exc())

    try:
        merged = _simulate_default_merge()
        expected = {"threshold": 0.5, "7": "lucky", "mode": "manual", "11": 42}
        if merged != expected:
            errors.append(
                "Default merge simulation mismatch: expected"
                f" {expected!r}, got {merged!r}"
            )
        if not all(isinstance(key, str) for key in merged.keys()):
            errors.append("Default merge simulation produced non-str keys")
    except Exception:
        errors.append("Default merge simulation failed:\n" + traceback.format_exc())

    if errors:
        print("SMOKE CI: FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("SMOKE CI: OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
