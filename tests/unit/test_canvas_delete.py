# tests/unit/test_canvas_delete.py
import pytest

try:  # pragma: no cover - skip when Qt bindings are unavailable
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication
except ImportError as exc:  # pragma: no cover - import guard
    pytest.skip(f"PySide6 runtime is not available: {exc}", allow_module_level=True)

from app.ui.canvas.canvas_scene import CanvasScene


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def scene(qt_app: QApplication) -> CanvasScene:
    scene = CanvasScene()
    scene.set_block_catalog(
        {
            "io": {
                "title": "IO",
                "inputs": [{"name": "in", "type": "flow"}],
                "outputs": [{"name": "out", "type": "flow"}],
                "default_params": {},
            }
        }
    )
    yield scene
    scene.clear()


def _prepare_blocks_with_connection(scene: CanvasScene):
    block_a = scene.add_block_at("io", QPointF(0, 0))
    block_b = scene.add_block_at("io", QPointF(200, 0))
    out_port = block_a.get_port("out", "out")
    in_port = block_b.get_port("in", "in")
    assert out_port is not None and in_port is not None
    scene.begin_connection(out_port)
    scene.complete_connection(in_port)
    connection_item = next(iter(scene._connection_items.values()))  # type: ignore[attr-defined]
    return block_a, block_b, connection_item


def test_delete_selected_connection(scene: CanvasScene) -> None:
    block_a, block_b, connection_item = _prepare_blocks_with_connection(scene)

    scene.clearSelection()
    connection_item.setSelected(True)

    removed = scene.delete_selected()
    assert removed is True

    model = scene.model()
    assert len(model.connections) == 0
    assert len(model.blocks) == 2
    assert scene._connection_items == {}
    assert block_a.block.uid in scene._block_items and block_b.block.uid in scene._block_items


def test_delete_selected_block_removes_connections(scene: CanvasScene) -> None:
    block_a, block_b, _ = _prepare_blocks_with_connection(scene)

    scene.clearSelection()
    block_a.setSelected(True)

    removed = scene.delete_selected()
    assert removed is True

    model = scene.model()
    assert all(block.uid != block_a.block.uid for block in model.blocks)
    assert all(
        conn.from_block_uid != block_a.block.uid and conn.to_block_uid != block_a.block.uid
        for conn in model.connections
    )
    assert block_a.block.uid not in scene._block_items
    assert scene._connection_items == {}


class _DummyProject:
    def __init__(self) -> None:
        self.removed_blocks = []
        self.removed_connections = []

    def remove_block(self, payload) -> None:
        self.removed_blocks.append(payload)

    def remove_connection(self, payload) -> None:
        self.removed_connections.append(payload)


def test_delete_selected_updates_attached_project(scene: CanvasScene) -> None:
    block_a, block_b, _ = _prepare_blocks_with_connection(scene)

    dummy = _DummyProject()
    scene._project = dummy  # type: ignore[attr-defined]

    scene.clearSelection()
    block_a.setSelected(True)

    removed = scene.delete_selected()
    assert removed is True

    assert len(dummy.removed_blocks) == 1
    removed_block_payload = dummy.removed_blocks[0]
    uid_value = getattr(removed_block_payload, "uid", removed_block_payload)
    assert uid_value == block_a.block.uid

    assert len(dummy.removed_connections) >= 1
    connection_payload = dummy.removed_connections[0]
    if hasattr(connection_payload, "from_block_uid"):
        assert (
            connection_payload.from_block_uid == block_a.block.uid
            or connection_payload.to_block_uid == block_a.block.uid
        )
    else:
        assert block_a.block.uid in str(connection_payload)

    assert block_a.block.uid not in scene._block_items
    assert scene._connection_items == {}
