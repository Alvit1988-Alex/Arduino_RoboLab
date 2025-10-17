"""Data models for the canvas scene."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class BlockInstance:
    """Single block placed on the canvas."""

    uid: str
    type_id: str
    x: float
    y: float
    params: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "uid": self.uid,
            "type_id": self.type_id,
            "pos": {"x": float(self.x), "y": float(self.y)},
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "BlockInstance":
        uid_value = payload.get("uid", "") if isinstance(payload, dict) else ""
        uid = str(uid_value) if uid_value else uuid.uuid4().hex
        type_id_value = payload.get("type_id", "") if isinstance(payload, dict) else ""
        type_id = str(type_id_value)
        pos = payload.get("pos", {}) if isinstance(payload, dict) else {}
        if isinstance(pos, dict):
            x = float(pos.get("x", 0.0))
            y = float(pos.get("y", 0.0))
        else:
            x = 0.0
            y = 0.0
        params_payload = payload.get("params", {}) if isinstance(payload, dict) else {}
        params = dict(params_payload) if isinstance(params_payload, dict) else {}
        return cls(uid=uid, type_id=type_id, x=x, y=y, params=params)

    def set_position(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)


@dataclass
class ConnectionModel:
    """Connection between two block ports."""

    from_block_uid: str
    from_port: str
    to_block_uid: str
    to_port: str

    def key(self) -> str:
        """Return a unique key identifying the connection."""

        return f"{self.from_block_uid}:{self.from_port}->{self.to_block_uid}:{self.to_port}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "from_uid": self.from_block_uid,
            "from_port": self.from_port,
            "to_uid": self.to_block_uid,
            "to_port": self.to_port,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ConnectionModel":
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            from_block_uid=str(payload.get("from_uid", "")),
            from_port=str(payload.get("from_port", "")),
            to_block_uid=str(payload.get("to_uid", "")),
            to_port=str(payload.get("to_port", "")),
        )

    def matches(self, other: "ConnectionModel") -> bool:
        """Return True when ``other`` describes the same connection."""

        return (
            self.from_block_uid == other.from_block_uid
            and self.from_port == other.from_port
            and self.to_block_uid == other.to_block_uid
            and self.to_port == other.to_port
        )


class ProjectModel:
    """Model describing the entire canvas project."""

    VERSION = 1

    def __init__(
        self,
        *,
        blocks: Optional[Iterable[BlockInstance]] = None,
        connections: Optional[Iterable[ConnectionModel]] = None,
        version: Optional[int] = None,
    ) -> None:
        self.version = int(version or self.VERSION)
        self.blocks: List[BlockInstance] = list(blocks) if blocks else []
        self.connections: List[ConnectionModel] = list(connections) if connections else []

    def to_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "blocks": [block.to_dict() for block in self.blocks],
            "connections": [conn.to_dict() for conn in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ProjectModel":
        version_value = payload.get("version", cls.VERSION) if isinstance(payload, dict) else cls.VERSION
        version = int(version_value or cls.VERSION)
        blocks_payload = payload.get("blocks", []) if isinstance(payload, dict) else []
        connections_payload = payload.get("connections", []) if isinstance(payload, dict) else []
        blocks = [BlockInstance.from_dict(item) for item in blocks_payload]
        connections = [ConnectionModel.from_dict(item) for item in connections_payload]
        return cls(blocks=blocks, connections=connections, version=version)

    def create_block(
        self,
        *,
        type_id: str,
        x: float,
        y: float,
        params: Optional[Dict[str, object]] = None,
        uid: Optional[str] = None,
    ) -> BlockInstance:
        block = BlockInstance(
            uid=uid or uuid.uuid4().hex,
            type_id=type_id,
            x=float(x),
            y=float(y),
            params=params or {},
        )
        self.blocks.append(block)
        return block

    def remove_block(self, uid: str) -> None:
        self.blocks = [block for block in self.blocks if block.uid != uid]
        self.connections = [
            conn
            for conn in self.connections
            if conn.from_block_uid != uid and conn.to_block_uid != uid
        ]

    def find_block(self, uid: str) -> Optional[BlockInstance]:
        for block in self.blocks:
            if block.uid == uid:
                return block
        return None

    def add_connection(self, connection: ConnectionModel) -> None:
        """Append a new connection to the project model."""

        self.connections.append(connection)

    def remove_connection(self, connection: ConnectionModel) -> None:
        """Remove an existing connection from the project model."""

        self.connections = [
            existing for existing in self.connections if not existing.matches(connection)
        ]

    def find_connections_of(self, uid: str) -> List[ConnectionModel]:
        """Return all connections that originate from or end in ``uid``."""

        return [
            conn
            for conn in self.connections
            if conn.from_block_uid == uid or conn.to_block_uid == uid
        ]

    def clone(self) -> "ProjectModel":
        return ProjectModel.from_dict(self.to_dict())

    # ------------------------------------------------------- persistence utils
    def save_to_file(self, path: Path) -> None:
        serialized = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        path.write_text(serialized, encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> "ProjectModel":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)
