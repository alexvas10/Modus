from typing import List

import gi
from fabric.core.service import Signal
from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.flowbox import FlowBox

from .api.result import SearchResult
from .grid_item import GridItem

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


class LaunchpadGrid(Box):
    """Fullscreen paginated app-icon grid, macOS-Launchpad-style.

    Renders `SearchResult` objects (the same objects the applications plugin
    returns) as a Gtk.Stack of fixed-column-count FlowBox pages, with a row of
    page-indicator dots below.
    """

    @Signal
    def item_clicked(self, index: int) -> None:
        """Emitted when a grid item is clicked (flat index into full results list)."""
        pass

    @Signal
    def item_hovered(self, index: int) -> None:
        """Emitted when a grid item is hovered (flat index into full results list)."""
        pass

    @Signal
    def page_changed(self, page_index: int) -> None:
        """Emitted when the visible page changes."""
        pass

    def __init__(self, columns: int = 7, rows: int = 5, **kwargs):
        super().__init__(name="launchpad-grid", orientation="v", spacing=0, **kwargs)

        self.columns = columns
        self.rows = rows
        self.per_page = columns * rows

        self.results: List[SearchResult] = []
        self.current_page = 0
        self.total_pages = 1

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)

        self.dots_box = Box(
            name="launchpad-dots",
            orientation="h",
            spacing=0,
            h_align="center",
            v_align="center",
        )

        self.add(self.stack)
        self.add(self.dots_box)

    def set_results(self, results: List[SearchResult], selected_index: int = 0):
        """Rebuild all pages/dots from a flat list of results."""
        self.results = results or []

        for child in list(self.stack.get_children()):
            self.stack.remove(child)

        for child in list(self.dots_box.get_children()):
            self.dots_box.remove(child)

        if not self.results:
            self.total_pages = 1
            self.current_page = 0
            return

        self.total_pages = max(
            1, (len(self.results) + self.per_page - 1) // self.per_page
        )

        for page_index in range(self.total_pages):
            start = page_index * self.per_page
            end = start + self.per_page
            page_results = self.results[start:end]

            flowbox = FlowBox(
                name="launchpad-page",
                orientation="h",
                row_spacing=8,
                column_spacing=8,
                h_align="center",
                v_align="center",
            )
            flowbox.set_min_children_per_line(self.columns)
            flowbox.set_max_children_per_line(self.columns)
            flowbox.set_homogeneous(True)
            flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
            flowbox.set_activate_on_single_click(True)

            for offset, result in enumerate(page_results):
                flat_index = start + offset
                item = GridItem(
                    result=result,
                    selected=(flat_index == selected_index),
                    index=flat_index,
                )
                item.clicked.connect(
                    lambda _, idx=flat_index: self.item_clicked.emit(idx)
                )
                item.hovered.connect(
                    lambda _, idx=flat_index: self.item_hovered.emit(idx)
                )
                flowbox.add(item)

            self.stack.add_named(flowbox, f"page-{page_index}")

            dot = EventBox(name="launchpad-dot")
            dot.connect(
                "button-press-event",
                lambda _w, _e, p=page_index: self.go_to_page(p),
            )
            self.dots_box.add(dot)

        self.dots_box.set_visible(self.total_pages > 1)

        self.stack.show_all()
        self.dots_box.show_all()

        target_page = min(max(selected_index, 0) // self.per_page, self.total_pages - 1)
        self.go_to_page(target_page)
        self.set_selected_index(selected_index)

    def go_to_page(self, page_index: int):
        """Switch the visible page and update dot active-state."""
        page_index = max(0, min(page_index, self.total_pages - 1))
        self.current_page = page_index

        self.stack.set_visible_child_name(f"page-{page_index}")

        for i, dot in enumerate(self.dots_box.get_children()):
            if i == page_index:
                dot.add_style_class("active")
            else:
                dot.remove_style_class("active")

        self.page_changed.emit(page_index)

    def set_selected_index(self, index: int):
        """Highlight the grid item at the given flat index, jumping page if needed."""
        if not self.results or index < 0 or index >= len(self.results):
            return

        page = index // self.per_page
        if page != self.current_page:
            self.go_to_page(page)

        current_page_widget = self.stack.get_child_by_name(f"page-{self.current_page}")
        if current_page_widget is None:
            return

        for child in current_page_widget.get_children():
            # FlowBox wraps each added widget in a Gtk.FlowBoxChild
            item = child.get_child() if isinstance(child, Gtk.FlowBoxChild) else child
            if isinstance(item, GridItem):
                item.set_selected(item.index == index)
