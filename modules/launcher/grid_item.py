import gi
from fabric.core.service import Signal
from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from modules.launcher.result import Result

gi.require_version("Gtk", "3.0")


class GridItem(EventBox):
    """
    Widget for displaying a single application in the Launchpad-style grid.
    Icon on top, label centered below - no subtitle/plugin text.
    """

    # Signals
    @Signal
    def clicked(self, index: int) -> None:
        """Emitted when grid item is clicked."""
        pass

    @Signal
    def hovered(self, index: int) -> None:
        """Emitted when grid item is hovered."""
        pass

    def __init__(
        self, result: Result, selected: bool = False, index: int = 0, **kwargs
    ):
        super().__init__(name="launchpad-grid-item", **kwargs)

        self.result = result
        self._selected = selected
        self.index = index

        # Setup UI
        self._setup_ui()

        # Connect signals
        self.connect("button-press-event", self._on_button_press)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)

        # Set initial selection state
        self.set_selected(selected)

    def _setup_ui(self):
        """Setup the grid item UI."""
        main_box = Box(
            name="grid-item-box",
            orientation="v",
            spacing=0,
            h_align="center",
            v_align="center",
        )
        self.add(main_box)

        # Icon
        if self.result.icon:
            icon_widget = Image(pixbuf=self.result.icon, name="grid-item-icon")
        elif self.result.icon_name:
            icon_widget = Image(
                icon_name=self.result.icon_name, icon_size=96, name="grid-item-icon"
            )
        elif self.result.icon_markup:
            icon_widget = Label(
                markup=self.result.icon_markup, name="grid-item-icon-label"
            )
        else:
            icon_widget = Image(
                icon_name="application-default-icon",
                icon_size=96,
                name="grid-item-icon",
            )

        main_box.add(icon_widget)

        # Label (wraps up to 2 lines, centered)
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
        """Set the selection state of this grid item."""
        self._selected = selected

        if selected:
            self.add_style_class("selected")
        else:
            self.remove_style_class("selected")

    def get_selected(self) -> bool:
        """Get the selection state of this grid item."""
        return self._selected

    def _on_button_press(self, widget, event):
        """Handle button press events."""
        if event.button == 1:  # Left click
            self.clicked.emit(self.index)
            return True
        return False

    def _on_enter(self, widget, event):
        """Handle mouse enter events."""
        self.hovered.emit(self.index)
        return False

    def _on_leave(self, widget, event):
        """Handle mouse leave events."""
        return False
