import gi
from fabric.core.service import Signal
from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label

from .api.result import SearchResult

gi.require_version("Gtk", "3.0")

ICON_SIZE = 96


class GridItem(EventBox):
    """A single application in the Launchpad-style grid.

    Icon on top, label centered below — no subtitle or plugin text.
    """

    @Signal
    def clicked(self, index: int) -> None:
        """Emitted when grid item is clicked."""
        pass

    @Signal
    def hovered(self, index: int) -> None:
        """Emitted when grid item is hovered."""
        pass

    def __init__(
        self, result: SearchResult, selected: bool = False, index: int = 0, **kwargs
    ):
        super().__init__(name="launchpad-grid-item", **kwargs)

        self.result = result
        self._selected = selected
        self.index = index

        self._setup_ui()

        self.connect("button-press-event", self._on_button_press)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)

        self.set_selected(selected)

    def _build_icon(self):
        # Applications carry their DesktopApp in metadata; that is the only
        # source that yields a real pixbuf at grid resolution.
        app = self.result.metadata.get("desktop_app")
        if app:
            try:
                pixbuf = app.get_icon_pixbuf(size=ICON_SIZE)
                if pixbuf:
                    return Image(pixbuf=pixbuf, name="grid-item-icon")
            except Exception:
                pass

        if self.result.icon_name:
            return Image(
                icon_name=self.result.icon_name,
                icon_size=ICON_SIZE,
                name="grid-item-icon",
            )

        return Image(
            icon_name="application-default-icon",
            icon_size=ICON_SIZE,
            name="grid-item-icon",
        )

    def _setup_ui(self):
        main_box = Box(
            name="grid-item-box",
            orientation="v",
            spacing=0,
            h_align="center",
            v_align="center",
        )
        self.add(main_box)

        main_box.add(self._build_icon())

        label = Label(
            label=self.result.title,
            name="grid-item-label",
            h_align="center",
            v_align="center",
            justification="center",
            ellipsization="end",
            max_chars_width=14,
            line_wrap="word-char",
        )
        label.set_lines(2)
        main_box.add(label)

    def set_selected(self, selected: bool):
        self._selected = selected

        if selected:
            self.add_style_class("selected")
        else:
            self.remove_style_class("selected")

    def get_selected(self) -> bool:
        return self._selected

    def _on_button_press(self, widget, event):
        if event.button == 1:
            self.clicked.emit(self.index)
            return True
        return False

    def _on_enter(self, widget, event):
        self.hovered.emit(self.index)
        return False

    def _on_leave(self, widget, event):
        return False
