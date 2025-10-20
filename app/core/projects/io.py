from __future__ import annotations

import json
from pathlib import Path
from typing import Collection, Mapping, Optional, Tuple

from app.ui.canvas.model import BlockInstance, ConnectionModel, ProjectModel


def load_project_file(
    path: str | Path,
    *,
    aliases: Mapping[str, str] | None = None,
    known_blocks: Collection[str] | None = None,
) -> Tuple[ProjectModel, Optional[str], Optional[str]]:
    """Load project definition from .robojson file."""
    project_path = Path(path)
    data = json.loads(project_path.read_text(encoding="utf-8"))

    board = data.get("board")
    port = data.get("port")

    model = ProjectModel()
    alias_map = dict(aliases) if aliases is not None else {}
    known_ids = set(known_blocks) if known_blocks is not None else None
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        uid = str(node.get("uid", "")) or None
        type_id = str(node.get("type", ""))
        pos = node.get("pos", {}) if isinstance(node.get("pos", {}), dict) else {}
        params = node.get("params", {}) if isinstance(node.get("params", {}), dict) else {}
        if not type_id:
            continue
        canonical_type = type_id
        if alias_map:
            if type_id in alias_map:
                canonical_type = alias_map[type_id]
            elif known_ids is not None and type_id not in known_ids:
                canonical_type = alias_map.get(type_id, type_id)
        if canonical_type != type_id:
            print(f"[RoboLab] Блок {type_id} заменён на {canonical_type} (совместимость)")
        block = BlockInstance(
            uid=uid or type_id,
            type_id=canonical_type,
            x=float(pos.get("x", 0.0)),
            y=float(pos.get("y", 0.0)),
            params=dict(params),
        )
        model.add_block(block)

    for edge in data.get("edges", []):
        if not isinstance(edge, dict):
            continue
        src = edge.get("from", {}) if isinstance(edge.get("from", {}), dict) else {}
        dst = edge.get("to", {}) if isinstance(edge.get("to", {}), dict) else {}
        connection = ConnectionModel(
            from_block_uid=str(src.get("node", "")),
            from_port=str(src.get("port", "")),
            to_block_uid=str(dst.get("node", "")),
            to_port=str(dst.get("port", "")),
        )
        if connection.from_block_uid and connection.to_block_uid:
            model.add_connection(connection)

    return model, board, port


def save_project_file(
    path: str | Path,
    model: ProjectModel,
    *,
    board: Optional[str] = None,
    port: Optional[str] = None,
) -> None:
    """Serialize project model into .robojson file."""
    project_path = Path(path)
    project_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": 1,
        "board": board,
        "port": port,
        "nodes": [
            {
                "uid": block.uid,
                "type": block.type_id,
                "pos": {"x": block.x, "y": block.y},
                "params": dict(block.params),
            }
            for block in model.blocks
        ],
        "edges": [
            {
                "uid": connection.key(),
                "from": {"node": connection.from_block_uid, "port": connection.from_port},
                "to": {"node": connection.to_block_uid, "port": connection.to_port},
            }
            for connection in model.connections
        ],
    }

    project_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
