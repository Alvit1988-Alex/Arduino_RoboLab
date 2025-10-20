# app/ui/main_window.py
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QTextEdit,
)

from app.core.blocks_loader import BlocksLoaderError, load_blocks
from app.core.projects.io import load_project_file, save_project_file

from .canvas.canvas_scene import CanvasScene
from .canvas.items import BlockItem
from .canvas.model import BlockInstance, ProjectModel
from .code_panel.code_panel import CodeDock
from .palette.palette import PaletteDock
from .props.props_dock import PropsDock
from .widgets.canvas_view import CanvasView
from .widgets.serial_monitor import SerialMonitorDock


class MainWindow(QMainWindow):
    _TEXT_INPUT_WIDGETS = (QLineEdit, QPlainTextEdit, QTextEdit)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arduino RoboLab (Preview)")
        self.resize(1280, 800)

        # Сцена и вью
        self.canvas_scene = CanvasScene()
        self.canvas_scene.blockAdded.connect(self._on_block_added)
        self.canvas_scene.blocksRemoved.connect(self._on_blocks_removed)
        self.canvas_scene.connectionsRemoved.connect(self._on_connections_removed)
        self.canvas_scene.connectionAdded.connect(self._on_connection_added)
        self.canvas_scene.statusMessage.connect(self._show_status_message)
        self.canvas_scene.selectionChanged.connect(self._update_delete_action)
        self.canvas_scene.projectModelChanged.connect(self._on_project_model_changed)
        self.canvas_scene.selectionChanged.connect(self._on_selection_changed)
        self.canvas_scene.blockPropertiesRequested.connect(self._focus_properties)

        self.canvas_view = CanvasView(self.canvas_scene, self)
        self.setCentralWidget(self.canvas_view)

        # Слева — палитра блоков
        self.palette_dock = PaletteDock(self)
        self.palette_dock.blockActivated.connect(self._add_block_from_palette)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)

        # Справа — панель кода
        self.code_dock = CodeDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.code_dock)

        # Справа — свойства блока
        self.props_dock = PropsDock(self.canvas_scene, self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.props_dock)
        self.props_dock.hide()

        # Снизу — монитор порта (по умолчанию скрыт)
        self.serial_dock = SerialMonitorDock(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.serial_dock)
        self.serial_dock.hide()

        # Синхронизация меню Вид с реальной видимостью доков
        self.palette_dock.visibilityChanged.connect(self._sync_palette_action)
        self.code_dock.visibilityChanged.connect(self._sync_code_action)
        self.props_dock.visibilityChanged.connect(self._sync_props_action)
        self.serial_dock.visibilityChanged.connect(self._sync_monitor_action)

        self.block_library: List[dict] = []
        self.block_catalog: Dict[str, Dict[str, object]] = {}
        self.block_aliases: Dict[str, str] = {}
        self._blocks_path: Optional[Path] = None

        self._current_project_path: Optional[Path] = None
        self._current_board: str = "—"
        self._current_port: str = "—"
        self._project_dir: Path = Path.cwd()

        # Статусбар
        self.status_label = QLabel()
        self.statusBar().addPermanentWidget(self.status_label)

        # Меню и хоткеи
        self._shortcuts: List[QShortcut] = []
        self._setup_menu_bar()
        self._install_shortcuts()

        # Загрузка каталога блоков
        self._load_block_library()
        self.palette_dock.set_blocks(self.block_library)
        self.canvas_scene.set_block_catalog(self.block_catalog)
        self.props_dock.set_block_catalog(self.block_catalog)

        # Показатели состояния
        self._sync_palette_action(self.palette_dock.isVisible())
        self._sync_code_action(self.code_dock.isVisible())
        self._sync_props_action(self.props_dock.isVisible())
        self._sync_monitor_action(self.serial_dock.isVisible())
        self._update_status_counts()
        self.statusBar().showMessage("Готово", 2000)

    # ------------------------------------------------------------------ menu
    def _setup_menu_bar(self) -> None:
        menu_bar: QMenuBar = self.menuBar()
        menu_bar.clear()

        # Файл --------------------------------------------------------------
        file_menu = menu_bar.addMenu("Файл")

        self.act_new_project = QAction("Новый проект", self)
        self.act_new_project.setObjectName("actionNewProject")
        self.act_new_project.setShortcut(QKeySequence("Ctrl+N"))
        self.act_new_project.setStatusTip("Создать новый проект")
        self.act_new_project.triggered.connect(self.action_new_project)
        file_menu.addAction(self.act_new_project)

        self.act_open = QAction("Открыть…", self)
        self.act_open.setObjectName("actionOpenProject")
        self.act_open.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open.setStatusTip("Открыть проект .robojson")
        self.act_open.triggered.connect(self.action_open)
        file_menu.addAction(self.act_open)

        self.act_save = QAction("Сохранить", self)
        self.act_save.setObjectName("actionSaveProject")
        self.act_save.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save.setStatusTip("Сохранить текущий проект")
        self.act_save.triggered.connect(self.action_save)
        file_menu.addAction(self.act_save)

        self.act_save_as = QAction("Сохранить как…", self)
        self.act_save_as.setObjectName("actionSaveProjectAs")
        self.act_save_as.setShortcut(QKeySequence(QKeySequence.StandardKey.SaveAs))
        self.act_save_as.setStatusTip("Сохранить проект под новым именем")
        self.act_save_as.triggered.connect(self.action_save_as)
        file_menu.addAction(self.act_save_as)

        file_menu.addSeparator()

        self.act_exit = QAction("Выход", self)
        self.act_exit.setObjectName("actionExit")
        self.act_exit.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit))
        self.act_exit.setStatusTip("Закрыть приложение")
        self.act_exit.triggered.connect(self.action_exit)
        file_menu.addAction(self.act_exit)

        # Правка ------------------------------------------------------------
        edit_menu = menu_bar.addMenu("Правка")
        self.act_delete = QAction("Удалить выделенное", self)
        self.act_delete.setObjectName("actionDeleteSelection")
        self.act_delete.setStatusTip("Удалить выделенные блоки или соединения")
        self.act_delete.triggered.connect(self._delete_selection)
        self.act_delete.setEnabled(False)
        edit_menu.addAction(self.act_delete)

        # Устройство --------------------------------------------------------
        device_menu = menu_bar.addMenu("Устройство")
        self.act_select_board = QAction("Выбрать плату…", self)
        self.act_select_board.setObjectName("actionSelectBoard")
        self.act_select_board.triggered.connect(self.action_select_board)
        device_menu.addAction(self.act_select_board)

        self.act_select_port = QAction("Выбрать порт…", self)
        self.act_select_port.setObjectName("actionSelectPort")
        self.act_select_port.triggered.connect(self.action_select_port)
        device_menu.addAction(self.act_select_port)

        self.act_scan_devices = QAction("Сканировать", self)
        self.act_scan_devices.setObjectName("actionScanDevices")
        self.act_scan_devices.triggered.connect(self.action_scan_devices)
        device_menu.addAction(self.act_scan_devices)

        # Прошивка ---------------------------------------------------------
        firmware_menu = menu_bar.addMenu("Прошивка")

        self.act_generate_code = QAction("Сгенерировать код", self)
        self.act_generate_code.setObjectName("actionGenerateCode")
        self.act_generate_code.setShortcut(QKeySequence("Ctrl+G"))
        self.act_generate_code.setStatusTip("Сформировать предварительный Arduino-скетч")
        self.act_generate_code.triggered.connect(self.action_generate)
        firmware_menu.addAction(self.act_generate_code)

        self.act_compile_firmware = QAction("Скомпилировать", self)
        self.act_compile_firmware.setObjectName("actionCompileFirmware")
        self.act_compile_firmware.triggered.connect(lambda: self._show_stub_dialog(
            "Компиляция", "Компиляция прошивки будет добавлена в следующих версиях."
        ))
        firmware_menu.addAction(self.act_compile_firmware)

        self.act_upload_firmware = QAction("Залить", self)
        self.act_upload_firmware.setObjectName("actionUploadFirmware")
        self.act_upload_firmware.triggered.connect(lambda: self._show_stub_dialog(
            "Загрузка прошивки", "Загрузка прошивки пока недоступна."
        ))
        firmware_menu.addAction(self.act_upload_firmware)

        # Вид --------------------------------------------------------------
        view_menu = menu_bar.addMenu("Вид")

        theme_menu = QMenu("Тема", self)
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        self.act_theme_dark = QAction("Тёмная тема", self, checkable=True)
        self.act_theme_dark.setObjectName("actionThemeDark")
        self.act_theme_dark.setChecked(True)
        self.act_theme_dark.triggered.connect(lambda checked: checked and self._apply_theme("dark"))
        theme_group.addAction(self.act_theme_dark)
        theme_menu.addAction(self.act_theme_dark)

        self.act_theme_light = QAction("Светлая тема", self, checkable=True)
        self.act_theme_light.setObjectName("actionThemeLight")
        self.act_theme_light.triggered.connect(lambda checked: checked and self._apply_theme("light"))
        theme_group.addAction(self.act_theme_light)
        theme_menu.addAction(self.act_theme_light)

        view_menu.addMenu(theme_menu)

        panels_menu = QMenu("Панели", self)
        self.act_show_palette = QAction("Палитра блоков", self, checkable=True, checked=True)
        self.act_show_palette.setObjectName("actionTogglePalette")
        self.act_show_palette.setStatusTip("Показать или скрыть палитру блоков")
        self.act_show_palette.triggered.connect(self.action_toggle_palette)
        panels_menu.addAction(self.act_show_palette)

        self.act_show_code = QAction("Панель кода", self, checkable=True, checked=True)
        self.act_show_code.setObjectName("actionToggleCode")
        self.act_show_code.setStatusTip("Показать или скрыть панель кода")
        self.act_show_code.triggered.connect(self.action_toggle_code)
        panels_menu.addAction(self.act_show_code)

        self.act_show_props = QAction("Свойства блока", self, checkable=True, checked=False)
        self.act_show_props.setObjectName("actionToggleProps")
        self.act_show_props.setStatusTip("Показать или скрыть свойства выбранного блока")
        self.act_show_props.triggered.connect(self.action_toggle_props)
        panels_menu.addAction(self.act_show_props)

        self.act_show_monitor = QAction("Сериал-монитор", self, checkable=True, checked=False)
        self.act_show_monitor.setObjectName("actionToggleSerialMonitor")
        self.act_show_monitor.setStatusTip("Показать или скрыть монитор последовательного порта")
        self.act_show_monitor.triggered.connect(self.action_toggle_monitor)
        panels_menu.addAction(self.act_show_monitor)

        view_menu.addMenu(panels_menu)

        # Инструменты ------------------------------------------------------
        tools_menu = menu_bar.addMenu("Инструменты")

        self.act_tools_monitor = QAction("Сериал-монитор", self)
        self.act_tools_monitor.setObjectName("actionToolsSerialMonitor")
        self.act_tools_monitor.triggered.connect(self._open_serial_monitor)
        tools_menu.addAction(self.act_tools_monitor)

        self.act_tools_telemetry = QAction("Телеметрия", self)
        self.act_tools_telemetry.setObjectName("actionToolsTelemetry")
        self.act_tools_telemetry.triggered.connect(lambda: self._show_stub_dialog(
            "Телеметрия", "Модуль телеметрии находится в разработке."
        ))
        tools_menu.addAction(self.act_tools_telemetry)

        self.act_tools_simulator = QAction("Симулятор 2D", self)
        self.act_tools_simulator.setObjectName("actionToolsSimulator")
        self.act_tools_simulator.triggered.connect(lambda: self._show_stub_dialog(
            "Симулятор", "2D-симулятор будет доступен в будущих релизах."
        ))
        tools_menu.addAction(self.act_tools_simulator)

        # Справка ----------------------------------------------------------
        help_menu = menu_bar.addMenu("Справка")
        self.act_about = QAction("О программе", self)
        self.act_about.setObjectName("actionAbout")
        self.act_about.setStatusTip("Информация о приложении")
        self.act_about.triggered.connect(self.action_about)
        help_menu.addAction(self.act_about)

        self._update_delete_action()

    def _install_shortcuts(self) -> None:
        self._shortcuts.clear()

        self._register_shortcut("Ctrl+N", self.action_new_project)
        self._register_shortcut("Ctrl+O", self.action_open)
        self._register_shortcut("Ctrl+S", self.action_save)
        self._register_shortcut("Backspace", self._delete_selection)
        self._register_shortcut(QKeySequence.StandardKey.ZoomIn, self._zoom_in)
        self._register_shortcut(QKeySequence.StandardKey.ZoomOut, self._zoom_out)
        self._register_shortcut("Ctrl+0", self._reset_zoom)

        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        delete_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        delete_shortcut.activated.connect(self._delete_selection)
        self._shortcuts.append(delete_shortcut)

    def _register_shortcut(
        self,
        sequence: Union[QKeySequence, str, QKeySequence.StandardKey],
        callback: Callable[[], None],
    ) -> None:
        key_sequence = sequence if isinstance(sequence, QKeySequence) else QKeySequence(sequence)
        shortcut = QShortcut(key_sequence, self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    # ----------------------------------------------------------------- palette
    def _load_block_library(self) -> None:
        blocks_path = Path(__file__).resolve().parents[2] / "data" / "blocks" / "blocks.json"
        self._blocks_path = blocks_path
        print(f"[RoboLab] Loading block palette from {blocks_path}")
        try:
            normalized = load_blocks(blocks_path)
        except BlocksLoaderError as exc:  # pragma: no cover - UI feedback path
            print(f"[RoboLab] Failed to load blocks: {exc}")
            QMessageBox.critical(
                self,
                "Ошибка чтения палитры",
                f"Не удалось загрузить data/blocks/blocks.json\n{exc}",
            )
            self.block_library = []
            self.block_catalog = {}
            self.block_aliases = {}
            self.props_dock.set_block_catalog({})
            self.props_dock.clear()
            return

        palette = [spec.to_palette_entry() for spec in normalized.blocks]
        self.block_library = palette
        self.block_catalog = self._build_block_catalog(palette)
        self.block_aliases = dict(normalized.aliases_map)
        self.props_dock.set_block_catalog(self.block_catalog)

    def _build_block_catalog(self, blocks: List[dict]) -> Dict[str, Dict[str, object]]:
        catalog: Dict[str, Dict[str, object]] = {}
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_id = str(block.get("id", "")).strip()
            if not block_id:
                continue
            ports = block.get("ports", {}) if isinstance(block.get("ports", {}), dict) else {}
            inputs = self._normalize_ports(ports.get("inputs"), prefix="in")
            outputs = self._normalize_ports(ports.get("outputs"), prefix="out")
            if not outputs:
                outputs = [{"name": "out", "type": "flow"}]
            params = block.get("params", []) if isinstance(block.get("params", []), list) else []
            default_params: Dict[str, object] = {}
            catalog_defaults = block.get("default_params")
            if isinstance(catalog_defaults, dict):
                default_params.update({str(k): v for k, v in catalog_defaults.items()})
            for param in params:
                if isinstance(param, dict) and param.get("name") and param.get("name") not in default_params:
                    default_params[str(param.get("name"))] = param.get("default")
            catalog[block_id] = {
                "title": block.get("title", block_id),
                "category": block.get("category"),
                "color": block.get("color"),
                "section": block.get("section"),
                "inputs": inputs,
                "outputs": outputs,
                "params": params,
                "default_params": default_params,
            }
        return catalog

    def _normalize_ports(self, payload, *, prefix: str) -> List[Dict[str, Optional[str]]]:
        result: List[Dict[str, Optional[str]]] = []
        if isinstance(payload, list):
            for index, item in enumerate(payload):
                if isinstance(item, dict):
                    name = str(item.get("name", f"{prefix}{index+1}"))
                    dtype = item.get("type")
                else:
                    name = f"{prefix}{index+1}"
                    dtype = None
                dtype_value = str(dtype).strip() if isinstance(dtype, str) else None
                result.append({"name": name, "type": dtype_value})
        return result

    # ----------------------------------------------------------------- actions
    def action_new_project(self) -> None:
        self.canvas_scene.load_model(ProjectModel())
        self._current_project_path = None
        self.statusBar().showMessage("Создан новый проект", 3000)
        self._update_status_counts()
        self.props_dock.clear()

    def action_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект",
            str(self._project_dir),
            "RoboLab Project (*.robojson)",
        )
        if not path:
            return
        try:
            model, board, port = load_project_file(
                path,
                aliases=self.block_aliases,
                known_blocks=self.block_catalog.keys(),
            )
        except Exception as exc:  # pragma: no cover - UI feedback path
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть проект\n{exc}")
            return
        self.canvas_scene.load_model(model)
        self._current_project_path = Path(path)
        self._project_dir = self._current_project_path.parent
        self._current_board = board or "—"
        self._current_port = port or "—"
        self._update_status_counts()
        self._on_selection_changed()
        self.statusBar().showMessage(f"Проект загружен: {self._current_project_path.name}", 4000)

    def action_save(self) -> None:
        if not self._current_project_path:
            self.action_save_as()
            return
        self._save_project(self._current_project_path)

    def action_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект",
            str(self._project_dir),
            "RoboLab Project (*.robojson)",
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != ".robojson":
            target = target.with_suffix(".robojson")
        self._project_dir = target.parent
        self._save_project(target)
        self._current_project_path = target

    def _save_project(self, path: Path) -> None:
        model = self.canvas_scene.model().clone()
        board = None if self._current_board in {None, "—"} else self._current_board
        port = None if self._current_port in {None, "—"} else self._current_port
        try:
            save_project_file(path, model, board=board, port=port)
        except Exception as exc:  # pragma: no cover - UI feedback path
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить проект\n{exc}")
            return
        self.statusBar().showMessage(f"Проект сохранён: {path.name}", 4000)

    def action_exit(self) -> None:
        self.close()

    def action_select_board(self) -> None:
        current = self._current_board if self._current_board not in {None, "—"} else ""
        board, accepted = QInputDialog.getText(
            self,
            "Выбор платы",
            "Введите идентификатор платы:",
            text=current,
        )
        if accepted and board.strip():
            self._current_board = board.strip()
            self._update_status_counts()
            self.statusBar().showMessage(f"Выбрана плата: {self._current_board}", 3000)
        elif accepted:
            self._show_stub_dialog("Выбор платы", "Укажите название платы для продолжения.")

    def action_select_port(self) -> None:
        current = self._current_port if self._current_port not in {None, "—"} else ""
        port, accepted = QInputDialog.getText(
            self,
            "Выбор порта",
            "Введите имя порта (например, COM3):",
            text=current,
        )
        if accepted and port.strip():
            self._current_port = port.strip()
            self._update_status_counts()
            self.statusBar().showMessage(f"Выбран порт: {self._current_port}", 3000)
        elif accepted:
            self._show_stub_dialog("Выбор порта", "Имя порта не может быть пустым.")

    def action_scan_devices(self) -> None:
        self._show_stub_dialog(
            "Сканирование устройств",
            "Поиск плат и портов будет добавлен позже.",
        )

    def action_generate(self) -> None:
        sketch = self._generate_sketch_text()
        self.code_dock.set_code(sketch)
        self.statusBar().showMessage("Скетч обновлён", 3000)

    def action_toggle_palette(self, checked: bool) -> None:
        self.palette_dock.setVisible(checked)

    def action_toggle_code(self, checked: bool) -> None:
        self.code_dock.setVisible(checked)

    def action_toggle_props(self, checked: bool) -> None:
        self.props_dock.setVisible(checked)
        if checked and self.props_dock.isHidden():
            self.props_dock.show()

    def action_toggle_monitor(self, checked: bool) -> None:
        self.serial_dock.setVisible(checked)
        if checked and self.serial_dock.isHidden():
            self.serial_dock.show()

    def action_about(self) -> None:
        QMessageBox.about(
            self,
            "Arduino RoboLab",
            "Arduino RoboLab (Preview)\nВерсия: 0.1.0",
        )

    def _open_serial_monitor(self) -> None:
        if not self.act_show_monitor.isChecked():
            self.act_show_monitor.setChecked(True)
        self.action_toggle_monitor(True)
        self.serial_dock.raise_()
        self.serial_dock.activateWindow()
        self.statusBar().showMessage("Сериал-монитор открыт", 2000)

    # ----------------------------------------------------------- scene hooks
    def _on_block_added(self, block: BlockInstance) -> None:
        title = self.block_catalog.get(block.type_id, {}).get("title", block.type_id)
        self.statusBar().showMessage(f"Добавлен блок: {title}", 3000)
        self._update_status_counts()
        self._on_selection_changed()

    def _on_blocks_removed(self, count: int) -> None:
        if count:
            self.statusBar().showMessage(f"Удалено блоков: {count}", 3000)
            self._update_status_counts()

    def _on_connection_added(self, connection) -> None:
        self.statusBar().showMessage("Создано соединение", 2000)

    def _on_connections_removed(self, count: int) -> None:
        if count:
            self.statusBar().showMessage(f"Удалено соединений: {count}", 2000)

    def _show_status_message(self, text: str, timeout: int = 4000) -> None:
        self.statusBar().showMessage(text, timeout)

    def _add_block_from_palette(self, block_info: dict) -> None:
        block_id = block_info.get("id")
        if not block_id:
            return
        scene_pos = self.canvas_view.mapToScene(self.canvas_view.viewport().rect().center())
        self.canvas_scene.add_block_at(block_id, scene_pos)
        self._update_status_counts()

    # ------------------------------------------------------------ shortcuts
    def _delete_selection(self) -> None:
        focus = QApplication.focusWidget()
        if isinstance(focus, self._TEXT_INPUT_WIDGETS):
            return
        removed = self.canvas_scene.delete_selected()
        if removed:
            self._update_status_counts()
        self._update_delete_action()
        self._on_selection_changed()

    def _on_project_model_changed(self, _model: ProjectModel) -> None:
        # Пока просто обновляем статус; в будущем можно добавить отметку «есть несохранённые изменения».
        self._update_status_counts()

    def _zoom_in(self) -> None:
        self.canvas_view.scale(1.15, 1.15)

    def _zoom_out(self) -> None:
        self.canvas_view.scale(1 / 1.15, 1 / 1.15)

    def _reset_zoom(self) -> None:
        self.canvas_view.resetTransform()

    def _apply_theme(self, theme: str) -> None:
        theme_name = "Тёмная" if theme == "dark" else "Светлая"
        self._show_stub_dialog(
            "Настройка темы",
            f"{theme_name} тема интерфейса будет доступна в следующих обновлениях.",
        )

    # ------------------------------------------------------------ utilities
    def _on_selection_changed(self) -> None:
        if not hasattr(self, "props_dock"):
            return
        items = [item for item in self.canvas_scene.selectedItems() if isinstance(item, BlockItem)]
        if len(items) == 1:
            block_item = items[0]
            self.props_dock.bind(block_item)
            if self.act_show_props.isChecked() and not self.props_dock.isVisible():
                self.props_dock.show()
        else:
            self.props_dock.clear()

    def _focus_properties(self, block_item: BlockItem) -> None:
        if not block_item.isSelected():
            self.canvas_scene.clearSelection()
            block_item.setSelected(True)
        self.props_dock.bind(block_item)
        if not self.act_show_props.isChecked():
            self.act_show_props.setChecked(True)
        self.props_dock.show()
        self.props_dock.raise_()
        self.props_dock.activateWindow()
        self.props_dock.focus_first_editor()

    def _generate_sketch_text(self) -> str:
        model = self.canvas_scene.model().clone()
        lines = [
            "// Arduino RoboLab preview sketch",
            "#include <Arduino.h>",
            "",
            "void setup() {",
            "  // TODO: заполнить настройку по данным блоков",
            "}",
            "",
            "void loop() {",
            "  // TODO: автоматическая генерация логики",
            "}",
            "",
            "// --- blocks on canvas ---",
        ]
        for block in model.blocks:
            params = ", ".join(f"{key}={value}" for key, value in block.params.items())
            if not params:
                params = "<без параметров>"
            lines.append(f"// {block.type_id}: {params}")
        if not model.blocks:
            lines.append("// канва пуста")
        lines.append("")
        lines.append("// --- connections ---")
        for connection in model.connections:
            lines.append(
                f"// {connection.from_block_uid}:{connection.from_port} -> "
                f"{connection.to_block_uid}:{connection.to_port}"
            )
        if not model.connections:
            lines.append("// соединений нет")
        lines.append("")
        lines.append("// Конец предварительного скетча")
        return "\n".join(lines)

    def _update_status_counts(self) -> None:
        model = self.canvas_scene.model()
        count = len(model.blocks)
        board = self._current_board or "—"
        port = self._current_port or "—"
        self.status_label.setText(f"Блоков на сцене: {count} | Плата: {board} | Порт: {port}")

    def _update_delete_action(self) -> None:
        action = getattr(self, "act_delete", None)
        if action is None:
            return
        has_selection = bool(self.canvas_scene.selectedItems())
        action.setEnabled(has_selection)

    # ---------------------------------------------------------- visibility
    def _sync_palette_action(self, visible: bool) -> None:
        if self.act_show_palette.isChecked() != visible:
            self.act_show_palette.setChecked(visible)

    def _sync_code_action(self, visible: bool) -> None:
        if self.act_show_code.isChecked() != visible:
            self.act_show_code.setChecked(visible)

    def _sync_props_action(self, visible: bool) -> None:
        if self.act_show_props.isChecked() != visible:
            self.act_show_props.setChecked(visible)

    def _sync_monitor_action(self, visible: bool) -> None:
        if self.act_show_monitor.isChecked() != visible:
            self.act_show_monitor.setChecked(visible)

    def _show_stub_dialog(self, title: str, message: str) -> None:
        print(f"[RoboLab] {title}: {message}")
        QMessageBox.information(self, title, message)
