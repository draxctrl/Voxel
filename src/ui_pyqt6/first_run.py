"""The first run: four screens that end with the user having dictated.

A new user's first dictation otherwise happens in some other
application, where a bad key, the wrong microphone and no internet all
look identical - nothing appears, and nothing says why. Here Voxel is
holding the problem and can explain it.

The dictation on the last screen is diverted: it is shown in the box on
that screen, not typed into whatever is behind the window, and not
written to History.
"""
from __future__ import annotations

import logging
import webbrowser
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .icons import icon as load_icon
from .keys import pretty_hotkey
from .panes.widgets import ChoiceRow
from .theme import current_palette

logger = logging.getLogger(__name__)

GROQ_CONSOLE = "https://console.groq.com/keys"

DEFAULT_SIZE = (720, 620)


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    subtitle: str


STEPS: tuple[Step, ...] = (
    Step("welcome", "Welcome to Voxel",
         "Hold a hotkey, speak, and clean text appears wherever your cursor "
         "is. Setting up takes about a minute."),
    Step("listening", "Choose how Voxel listens",
         "You can change this later, and switch between them whenever you "
         "like."),
    Step("microphone", "Which microphone?",
         "Say something. Pick the one whose bars move."),
    Step("try", "Try it",
         "Hold your shortcut and say anything. What you say appears below - "
         "it will not be typed anywhere else."),
)


def needs_first_run(config) -> bool:
    """Whether this user should be shown the first run.

    Not "do they have an API key": that would hand the wizard to an
    offline-only user on every launch. Anyone already set up either way
    is treated as done.
    """
    if config.get("onboarding_complete", False):
        return False
    if str(config.get("api_key", "") or "").strip():
        return False
    if config.get("offline_mode", False):
        return False
    return True


class FirstRunWindow(QWidget):
    """The four screens, in a window of their own."""

    finished = pyqtSignal()
    #: Emitted from the dictation thread; Qt delivers it on the GUI one.
    dictation_arrived = pyqtSignal(str)

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.dictation_arrived.connect(self.show_dictation)
        self.ctx = ctx
        self._index = 0
        self._listening: str | None = None
        self._key_ok = False
        self._key_note = ""
        self._dictation = ""
        self._done = False
        self._palette = dict(current_palette())

        self.setWindowTitle("Welcome to Voxel")
        self.resize(*DEFAULT_SIZE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(44, 38, 44, 32)
        outer.setSpacing(0)

        self._step_label = QLabel("", self)
        self._step_label.setObjectName("first_run_step")
        outer.addWidget(self._step_label)
        outer.addSpacing(10)

        self._title = QLabel("", self)
        self._title.setObjectName("first_run_title")
        self._title.setWordWrap(True)
        outer.addWidget(self._title)
        outer.addSpacing(8)

        self._subtitle = QLabel("", self)
        self._subtitle.setObjectName("first_run_subtitle")
        self._subtitle.setWordWrap(True)
        outer.addWidget(self._subtitle)
        outer.addSpacing(26)

        self._stack = QStackedWidget(self)
        outer.addWidget(self._stack, 1)

        self._build_welcome()
        self._build_listening()
        self._build_microphone()
        self._build_try()

        outer.addSpacing(18)
        outer.addLayout(self._build_footer())

        self.restyle(self._palette)
        self._refresh()

    # ------------------------------------------------------------------
    # the screens

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget(self._stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self._stack.addWidget(page)
        return page, layout

    def _build_welcome(self) -> None:
        _page, layout = self._page()
        self._welcome_points = []
        for text in (
            "Works in any app - your browser, your editor, your chat",
            "Removes \"um\" and \"uh\", fixes grammar, adds punctuation",
            "Free, and it can run entirely on this computer",
        ):
            label = QLabel("•   " + text, _page)
            label.setObjectName("first_run_point")
            label.setWordWrap(True)
            self._welcome_points.append(label)
            layout.addWidget(label)
        layout.addStretch(1)

    def _build_listening(self) -> None:
        page, layout = self._page()
        self._listen_rows: dict[str, ChoiceRow] = {}
        for row_id, title, subtitle in (
            ("groq", "Fast and accurate",
             "Uses Groq, which is free. Takes about 30 seconds to set up - "
             "no card, no payment."),
            ("offline", "Private - stays on this computer",
             "Nothing is ever sent anywhere. Slower, and downloads 145 MB "
             "the first time."),
        ):
            row = ChoiceRow(row_id, title, subtitle, page)
            row.clicked.connect(self.choose_listening)
            self._listen_rows[row_id] = row
            layout.addWidget(row)

        self._key_area = QWidget(page)
        key_row = QHBoxLayout(self._key_area)
        key_row.setContentsMargins(0, 6, 0, 0)
        key_row.setSpacing(10)
        self._key_field = QLineEdit(self._key_area)
        self._key_field.setPlaceholderText("Paste your key here")
        self._key_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_field.setFixedHeight(42)
        self._key_field.returnPressed.connect(self._on_key_entered)
        key_row.addWidget(self._key_field, 1)
        self._key_button = QPushButton("Check it", self._key_area)
        self._key_button.setFixedHeight(42)
        self._key_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._key_button.clicked.connect(self._on_key_entered)
        key_row.addWidget(self._key_button)
        self._get_key_button = QPushButton("Get my free key", self._key_area)
        self._get_key_button.setFixedHeight(42)
        self._get_key_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._get_key_button.clicked.connect(self.open_groq_console)
        key_row.addWidget(self._get_key_button)
        layout.addWidget(self._key_area)

        self._key_note_label = QLabel("", page)
        self._key_note_label.setObjectName("first_run_note")
        self._key_note_label.setWordWrap(True)
        layout.addWidget(self._key_note_label)
        layout.addStretch(1)

    def _build_microphone(self) -> None:
        page, layout = self._page()
        # The microphone pane already lists devices with live meters and
        # writes the choice; showing it here beats a second copy of it.
        from .panes.microphone import MicrophonePane

        self._mic_pane = MicrophonePane(self.ctx, page)
        self._mic_pane.hide_header()
        layout.addWidget(self._mic_pane, 1)

    def _build_try(self) -> None:
        page, layout = self._page()
        self._dictation_box = QLabel("", page)
        self._dictation_box.setObjectName("first_run_box")
        self._dictation_box.setWordWrap(True)
        self._dictation_box.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._dictation_box.setMinimumHeight(150)
        layout.addWidget(self._dictation_box)
        self._try_hint = QLabel("", page)
        self._try_hint.setObjectName("first_run_note")
        self._try_hint.setWordWrap(True)
        layout.addWidget(self._try_hint)
        layout.addStretch(1)

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._dots = []
        for index in range(len(STEPS)):
            dot = QLabel("", self)
            dot.setFixedSize(10 if index else 22, 8)
            dot.setObjectName("first_run_dot")
            self._dots.append(dot)
            footer.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        footer.addStretch(1)

        self._back_button = QPushButton("Back", self)
        self._back_button.setFixedHeight(44)
        self._back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_button.clicked.connect(self.go_back)
        footer.addWidget(self._back_button)

        self._next_button = QPushButton("Continue", self)
        self._next_button.setObjectName("first_run_next")
        self._next_button.setFixedHeight(44)
        self._next_button.setMinimumWidth(170)
        self._next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_button.clicked.connect(self.go_next)
        footer.addWidget(self._next_button)
        return footer

    # ------------------------------------------------------------------
    # what the tests and main.py ask

    def current_step(self) -> str:
        return STEPS[self._index].key

    def step_number(self) -> int:
        return self._index + 1

    def step_label(self) -> str:
        return "STEP %d OF %d" % (self._index + 1, len(STEPS))

    def key_message(self) -> str:
        return self._key_note

    def dictation_text(self) -> str:
        return self._dictation_box.text()

    def listening_choice(self) -> str | None:
        return self._listening

    def wants_the_dictation(self) -> bool:
        """Whether the last screen is waiting for a dictation to show."""
        return (not self._done) and self.current_step() == "try"

    def can_continue(self) -> bool:
        if self.current_step() != "listening":
            return True
        if self._listening == "offline":
            return True
        return self._listening == "groq" and self._key_ok

    # ------------------------------------------------------------------
    # moving about

    def go_next(self) -> None:
        if not self.can_continue():
            return
        if self._index >= len(STEPS) - 1:
            self.finish()
            return
        self._index += 1
        self._refresh()

    def go_back(self) -> None:
        if self._index == 0:
            return
        self._index -= 1
        self._refresh()

    def finish(self) -> None:
        if self._done:
            return
        self._done = True
        self.ctx.apply("onboarding_complete", True)
        self.finished.emit()
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        # Someone who closes the wizard has made their choice; showing it
        # again on every launch would be nagging rather than helping.
        if not self._done:
            self._done = True
            self.ctx.apply("onboarding_complete", True)
            self.finished.emit()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # screen 2

    def choose_listening(self, row_id: str) -> None:
        if row_id not in ("groq", "offline"):
            return
        self._listening = row_id
        for key, row in self._listen_rows.items():
            row.set_selected(key == row_id)
        if row_id == "offline":
            self.ctx.apply("offline_mode", True)
            self._key_note = ""
        else:
            self.ctx.apply("offline_mode", False)
        self._refresh()

    def check_key(self, key: str) -> bool:
        """Ask Groq whether the key works. Replaced in tests."""
        try:
            from groq import Groq

            Groq(api_key=key).models.list()
            return True
        except Exception as e:
            logger.info("Key check failed: %s", e)
            return False

    def submit_key(self, key: str) -> None:
        key = (key or "").strip()
        if not key:
            self._key_ok = False
            self._key_note = "Paste your key into the box first."
            self._refresh()
            return
        if self.check_key(key):
            self._key_ok = True
            self._key_note = "Checked it - that key works."
            self.ctx.apply("api_key", key)
        else:
            self._key_ok = False
            self._key_note = (
                "That key did not work. Copy it again from Groq - it starts "
                "with gsk_ and it is easy to miss a character."
            )
        self._refresh()

    def _on_key_entered(self) -> None:
        self.submit_key(self._key_field.text())

    def open_groq_console(self) -> None:
        try:
            webbrowser.open(GROQ_CONSOLE)
        except Exception as e:  # pragma: no cover - depends on the desktop
            logger.warning("Could not open the Groq console: %s", e)

    # ------------------------------------------------------------------
    # screen 4

    def show_dictation(self, text: str) -> None:
        self._dictation = text or ""
        self._dictation_box.setText(self._dictation or "")
        self._refresh_try_hint()

    def _refresh_try_hint(self) -> None:
        shortcut = pretty_hotkey(self.ctx.config.get("hotkey", ""))
        if self._dictation:
            self._try_hint.setText(
                "That is what Voxel heard. From now on it goes wherever your "
                "cursor is."
            )
        else:
            self._try_hint.setText(
                "Waiting for you. Hold %s and say anything." % shortcut
                if shortcut else "Waiting for you."
            )

    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        step = STEPS[self._index]
        self._stack.setCurrentIndex(self._index)
        self._step_label.setText(self.step_label())
        self._title.setText(step.title)
        self._subtitle.setText(step.subtitle)

        self._key_area.setVisible(self._listening == "groq")
        self._key_note_label.setVisible(bool(self._key_note))
        self._key_note_label.setText(self._key_note)

        self._back_button.setVisible(self._index > 0)
        last = self._index == len(STEPS) - 1
        self._next_button.setText("Start using Voxel" if last else "Continue")
        self._next_button.setEnabled(self.can_continue())

        if step.key == "microphone":
            self._mic_pane.refresh()
        if step.key == "try":
            self._refresh_try_hint()

        self._restyle_dots()

    def _restyle_dots(self) -> None:
        p = self._palette
        for index, dot in enumerate(self._dots):
            on = index == self._index
            dot.setFixedSize(22 if on else 10, 8)
            dot.setStyleSheet(
                "background-color: %s; border-radius: 4px;"
                % (p["accent"] if on else p["row_border"])
            )

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        p = self._palette
        self.setStyleSheet(
            "QWidget { background-color: %s; }"
            "QLabel#first_run_step { color: %s; font-size: 12px;"
            " font-weight: 700; letter-spacing: 2px; }"
            "QLabel#first_run_title { color: %s; font-size: 32px;"
            " font-weight: 700; }"
            "QLabel#first_run_subtitle { color: %s; font-size: 15px; }"
            "QLabel#first_run_point { color: %s; font-size: 15px; }"
            "QLabel#first_run_note { color: %s; font-size: 13px; }"
            "QLabel#first_run_box { color: %s; background-color: %s;"
            " border: 1px solid %s; border-radius: 12px; padding: 18px;"
            " font-size: 17px; }"
            "QLineEdit { color: %s; background-color: %s; border: 1px solid %s;"
            " border-radius: 9px; padding: 0 12px; font-size: 14px; }"
            "QLineEdit:focus { border-color: %s; }"
            "QPushButton { color: %s; background-color: %s;"
            " border: 1px solid %s; border-radius: 9px; padding: 0 18px;"
            " font-size: 14px; }"
            "QPushButton:hover { border-color: %s; }"
            "QPushButton#first_run_next { color: #ffffff;"
            " background-color: %s; border: none; font-weight: 600; }"
            "QPushButton#first_run_next:disabled { color: %s;"
            " background-color: %s; }"
            % (
                p["pane"], p["faint"], p["text"], p["muted"], p["text"],
                p["muted"], p["text"], p["row"], p["row_border"],
                p["text"], p["card_alt"], p["row_border"], p["accent"],
                p["text"], p["card_alt"], p["row_border"], p["accent"],
                p["accent"], p["faint"], p["row"],
            )
        )
        for row in getattr(self, "_listen_rows", {}).values():
            row.restyle(p)
        if hasattr(self, "_mic_pane"):
            self._mic_pane.restyle(p)
        self._restyle_dots()
