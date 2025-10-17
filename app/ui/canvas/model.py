from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import copy


@dataclass
class BlockInstance:
    """Описание блока, размещённого на сцене."""
    uid: str
    type_id: str
    x: float = 0.0
    y: float = 0.0
    params: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "uid": self.uid,
            "type_id": self.type_id,
            "x": self.x,
            "y": self.y,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "BlockInstance":
        return cls(
            uid=str(payload.get("uid", "")),
            type_id=str(payload.get("type_id", "")),
            x=float(payload.get("x", 0.0)),
            y=float(payload.get("y", 0.0)),
            params=dict(payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}),
        )


@dataclass
class ConnectionModel:
    """Connection between two block ports."""
    from_block_uid: str
    from_port: str
    to_block_uid: str
    to_port: str

    def key(self) -> str:
        """Unique key of the connection (stable)."""
        return f"{self.from_block_uid}:{self.from_port}->{self.to_block_uid}:{self.to_port}"

    def to_dict(self) -> Dict[str, object]:
        # сохранение в «плоском» формате (из Codex-ветки)
        return {
            "from_uid": self.from_block_uid,
            "from_port": self.from_port,
            "to_uid": self.to_block_uid,
            "to_port": self.to_port,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ConnectionModel":
        # поддержка обоих форматов
        if not isinstance(payload, dict):
            payload = {}
        if "from_uid" in payload or "to_uid" in payload:
            return cls(
                from_block_uid=str(payload.get("from_uid", "")),
                from_port=str(payload.get("from_port", "")),
                to_block_uid=str(payload.get("to_uid", "")),
                to_port=str(payload.get("to_port", "")),
            )
        from_payload = payload.get("from", {}) if isinstance(payload.get("from", {}), dict) else {}
        to_payload = payload.get("to", {}) if isinstance(payload.get("to", {}), dict) else {}
        return cls(
            from_block_uid=str(from_payload.get("block_uid", "")),
            from_port=str(from_payload.get("port", "")),
            to_block_uid=str(to_payload.get("block_uid", "")),
            to_port=str(to_payload.get("port", "")),
        )

    def matches(self, other: "ConnectionModel") -> bool:
        return (
            self.from_block_uid == other.from_block_uid
            and self.from_port == other.from_port
            and self.to_block_uid == other.to_block_uid
            and self.to_port == other.to_port
        )


@dataclass
class ProjectModel:
    """Проект: набор блоков и соединений."""
    blocks: List[BlockInstance] = field(default_factory=list)
    connections: List[ConnectionModel] = field(default_factory=list)

    def clone(self) -> "ProjectModel":
        return copy.deepcopy(self)

    def add_block(self, block: BlockInstance) -> None:
        self.blocks.append(block)

    def remove_block(self, uid: str) -> None:
        self.blocks = [b for b in self.blocks if b.uid != uid]
        # связанные соединения тоже удалим — безопасность на уровне модели
        self.connections = [
            c for c in self.connections if (c.from_block_uid != uid and c.to_block_uid != uid)
        ]

    def add_connection(self, connection: ConnectionModel) -> None:
        self.connections.append(connection)

    def remove_connection(self, connection: ConnectionModel) -> None:
        self.connections = [c for c in self.connections if not c.matches(connection)]

    def find_connections_of(self, uid: str) -> List[ConnectionModel]:
        return [c for c in self.connections if c.from_block_uid == uid or c.to_block_uid == uid]

    def to_dict(self) -> Dict[str, object]:
        return {
            "blocks": [b.to_dict() for b in self.blocks],
            "connections": [c.to_dict() for c in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ProjectModel":
        blocks = []
        connections = []
        if isinstance(payload, dict):
            for b in payload.get("blocks", []):
                if isinstance(b, dict):
                    blocks.append(BlockInstance.from_dict(b))
            for c in payload.get("connections", []):
                if isinstance(c, dict):
                    connections.append(ConnectionModel.from_dict(c))
        return cls(blocks=blocks, connections=connections)
