"""Settings panes: one topic per pane, all built against one context.

A pane never touches the running app directly. It reads from `ctx.config`
and writes through `ctx.apply(key, value)`, which is the single route that
decides what - if anything - has to restart. That is what lets this window
have no Save button.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Callable

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


@dataclass
class PaneContext:
    """Everything a pane is allowed to reach."""

    config: object
    profiles: object
    history: object
    apply: Callable[[str, object], None]
    palette: Callable[[], dict]
    #: Panes that need to talk to live audio (the microphone meters) get
    #: the recorder here; it is None outside the running app.
    recorder: object | None = None
    #: Set by test fixtures to record what `apply` was asked to change.
    applied: list = field(default_factory=list)


class Pane(QWidget):
    """Base class for a settings pane.

    Subclasses set `PANE_ID`, `TITLE`, `SUBTITLE` and `OWNS`, build their
    controls in `__init__`, re-read the config in `refresh()`, and repaint
    themselves from a palette in `restyle()`.
    """

    PANE_ID: str = ""
    TITLE: str = ""
    SUBTITLE: str = ""
    #: The config keys this pane edits. Checked for gaps and overlaps, so
    #: that no setting ends up with two homes or none.
    OWNS: frozenset[str] = frozenset()

    def __init__(self, ctx: PaneContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("pane_" + self.PANE_ID)

    def refresh(self) -> None:
        """Re-read the config. Called every time the pane is shown."""

    def restyle(self, palette: dict) -> None:
        """Repaint from a palette. Called when the theme changes."""


class PlaceholderPane(Pane):
    """Stands in for a pane whose task has not landed yet.

    It exists so the rail never leads nowhere while the rebuild is in
    progress. Every one of these is gone by the end of the plan - the
    registry below is the list of what is left.
    """

    def __init__(self, ctx: PaneContext, parent: QWidget | None = None) -> None:
        super().__init__(ctx, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        self._label = QLabel(self.TITLE or self.PANE_ID)
        layout.addWidget(self._label)
        layout.addStretch(1)


#: pane id -> "module:ClassName", or None while that pane is still a
#: placeholder. Each pane task fills in its own line.
_REGISTRY: dict[str, str | None] = {
    "writing_style": "writing_style:WritingStylePane",
    "voice_commands": "voice_commands:VoiceCommandsPane",
    "language": "language:LanguagePane",
    "microphone": "microphone:MicrophonePane",
    "shortcuts": "shortcuts:ShortcutsPane",
    "appearance": "appearance:AppearancePane",
    "history": None,
    "stats": None,
    "general": "general:GeneralPane",
    "about": "about:AboutPane",
}

#: Titles for the placeholders, so a half-built window still reads.
_PLACEHOLDER_TITLES: dict[str, str] = {
    "writing_style": "Writing style",
    "voice_commands": "Voice commands",
    "language": "Language",
    "microphone": "Microphone",
    "shortcuts": "Shortcuts",
    "appearance": "Appearance",
    "history": "History",
    "stats": "Stats",
    "general": "General",
    "about": "About",
}


def _placeholder_for(pane_id: str) -> type[Pane]:
    return type(
        "Placeholder" + pane_id.title().replace("_", "") + "Pane",
        (PlaceholderPane,),
        {
            "PANE_ID": pane_id,
            "TITLE": _PLACEHOLDER_TITLES.get(pane_id, pane_id),
            "OWNS": frozenset(),
        },
    )


def all_panes() -> list[type[Pane]]:
    """Every pane class, in rail order."""
    classes: list[type[Pane]] = []
    for pane_id, target in _REGISTRY.items():
        if target is None:
            classes.append(_placeholder_for(pane_id))
            continue
        module_name, _, class_name = target.partition(":")
        module = importlib.import_module("." + module_name, __name__)
        classes.append(getattr(module, class_name))
    return classes
