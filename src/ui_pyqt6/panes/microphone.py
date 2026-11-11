"""Microphone: which device, with proof that it is hearing you.

Devices are rows with live level meters rather than a dropdown, because
"pick the one whose bars move when you talk" is something anyone can do,
and "Microphone Array (Realtek(R) Audio)" is not.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..theme import current_palette
from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, ChoiceRow, PaneHeader, pane_body

logger = logging.getLogger(__name__)

#: The row meaning "whatever Windows is set to".
SYSTEM_DEFAULT_ID = "__system_default__"

#: How often the meters are redrawn while the pane is on screen. The
#: recorder measures the level on every chunk it reads, so this only
#: decides how smooth the bars look.
LEVEL_POLL_MS = 60


def list_input_devices() -> list[dict]:
    """Input devices, as {"index", "name"}, newest list every call.

    Ported from the old settings window: the same host-API filtering the
    recorder uses, so the list the user picks from and the device actually
    opened cannot disagree.
    """
    import pyaudio

    from src.mic_recorder import find_preferred_host_api

    pa = pyaudio.PyAudio()
    try:
        wasapi_idx = find_preferred_host_api(pa)
        if wasapi_idx is not None:
            target_host = wasapi_idx
        else:
            target_host = pa.get_default_host_api_info().get("index", 0)

        devices: list[dict] = []
        seen: set[str] = set()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) <= 0:
                continue
            if info.get("hostApi", -1) != target_host:
                continue
            name = info.get("name", "Device %d" % i)
            if name in seen:
                continue
            seen.add(name)
            devices.append({"index": info.get("index", i), "name": name})
        return devices
    finally:
        try:
            pa.terminate()
        except Exception:
            pass


class _LevelMeter(QWidget):
    """Five bars that rise with the input level."""

    BARS = 5

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(QSize(46, 18))
        self._level = 0.0
        palette = current_palette()
        self._on = QColor(palette["accent"])
        self._off = QColor(palette["row_border"])

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, float(level)))
        self.update()

    def set_colours(self, on: str, off: str) -> None:
        self._on = QColor(on)
        self._off = QColor(off)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        lit = round(self._level * self.BARS)
        width, gap = 6, 4
        for i in range(self.BARS):
            height = 6 + i * 3
            x = i * (width + gap)
            y = self.height() - height
            painter.setBrush(self._on if i < lit else self._off)
            painter.drawRoundedRect(x, y, width, height, 2, 2)
        painter.end()


class _DeviceRow(QWidget):
    """A choice row with a level meter pinned to its right."""

    def __init__(self, row_id: str, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.row_id = row_id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.choice = ChoiceRow(row_id, title, subtitle)
        layout.addWidget(self.choice, 1)
        self.meter = _LevelMeter(self.choice)
        meter_slot = QHBoxLayout()
        meter_slot.setContentsMargins(0, 0, 14, 0)
        self.choice.layout().addWidget(self.meter, 0, Qt.AlignmentFlag.AlignVCenter)

    def restyle(self, p: dict) -> None:
        self.choice.restyle(p)
        self.meter.set_colours(p["accent"], p["row_border"])


class MicrophonePane(Pane):
    PANE_ID = "microphone"
    TITLE = "Microphone"
    SUBTITLE = "Pick the one whose bars move when you talk."
    OWNS = frozenset({"mic_device_name", "mic_device"})

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._rows: dict[str, _DeviceRow] = {}
        self._devices: list[dict] = []
        self._warning = ""

        _area, layout = pane_body(self)
        self._layout = layout

        self._header = PaneHeader(self.TITLE, self.SUBTITLE)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        self._warning_label = QLabel()
        self._warning_label.setObjectName("pane_warning")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(10)
        layout.addWidget(self._rows_host)

        layout.addStretch(1)

        # The recorder's capture loop measures the level on every chunk it
        # reads, recording or not - that is how the preroll buffer works -
        # so the bars only need something to pull that value across. The
        # timer runs while the pane is on screen and no longer.
        self._level_timer = QTimer(self)
        self._level_timer.setInterval(LEVEL_POLL_MS)
        self._level_timer.timeout.connect(self.poll_levels)

        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        self._level_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._level_timer.stop()
        super().hideEvent(event)

    # ------------------------------------------------------------------

    def device_names(self) -> list[str]:
        return [d["name"] for d in self._devices]

    def row_ids(self) -> list[str]:
        return list(self._rows)

    def warning_text(self) -> str:
        return self._warning

    def selected_id(self) -> str:
        saved = self.ctx.config.get("mic_device_name", None)
        return saved if saved else SYSTEM_DEFAULT_ID

    def level_for(self, row_id: str) -> float:
        row = self._rows.get(row_id)
        return row.meter._level if row is not None else 0.0

    # ------------------------------------------------------------------

    def choose(self, row_id: str) -> None:
        """Apply a device. A name no longer present is ignored."""
        if row_id == SYSTEM_DEFAULT_ID:
            self.ctx.apply("mic_device_name", None)
            self.ctx.apply("mic_device", None)
            self.refresh()
            return
        match = next((d for d in self._devices if d["name"] == row_id), None)
        if match is None:
            return
        self.ctx.apply("mic_device_name", match["name"])
        self.ctx.apply("mic_device", match["index"])
        self.refresh()

    def poll_levels(self) -> None:
        """Push the recorder's current level onto the chosen device's meter.

        Only the chosen one: a stream per device would mean opening every
        microphone on the machine at once.
        """
        level = 0.0
        recorder = getattr(self.ctx, "recorder", None)
        if recorder is not None:
            try:
                level = float(recorder.current_level())
            except Exception as e:
                logger.debug("Could not read the input level: %s", e)
                level = 0.0
        chosen = self.selected_id()
        for row_id, row in self._rows.items():
            row.meter.set_level(level if row_id == chosen else 0.0)

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        try:
            self._devices = list_input_devices()
            failed = False
        except Exception as e:
            logger.warning("Could not list microphones: %s", e)
            self._devices = []
            failed = True

        self._rebuild_rows()

        saved = self.ctx.config.get("mic_device_name", None)
        if failed:
            self._warning = (
                "Voxel could not read the list of microphones. "
                "It will use whatever Windows is set to."
            )
        elif not self._devices:
            self._warning = (
                "No microphone found. Plug one in, then come back to this page."
            )
        elif saved and saved not in self.device_names():
            self._warning = (
                '"%s" is not plugged in at the moment. '
                "Voxel is using the Windows default until it is back, "
                "and your choice is still saved." % saved
            )
        else:
            self._warning = ""

        self._warning_label.setText(self._warning)
        self._warning_label.setVisible(bool(self._warning))

        chosen = self.selected_id()
        for row_id, row in self._rows.items():
            row.choice.set_selected(row_id == chosen)

    def _rebuild_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = {}

        entries = [(SYSTEM_DEFAULT_ID, "System default", "Whatever Windows is set to")]
        entries += [(d["name"], d["name"], "") for d in self._devices]

        palette = getattr(self, "_palette", None) or self.ctx.palette()
        for row_id, title, subtitle in entries:
            row = _DeviceRow(row_id, title, subtitle)
            row.choice.clicked.connect(self.choose)
            row.restyle(palette)
            self._rows[row_id] = row
            self._rows_layout.addWidget(row)

    # ------------------------------------------------------------------

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        repaint_with(self, pane_surface_qss(self._palette))
        self._header.restyle(self._palette)
        self._warning_label.setStyleSheet(
            "color: {warning}; font-size: 13px; background: transparent;".format(
                **self._palette
            )
        )
        for row in self._rows.values():
            row.restyle(self._palette)
