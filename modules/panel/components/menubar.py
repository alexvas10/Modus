import json
import re
import subprocess

from fabric.hyprland.widgets import HyprlandActiveWindow as ActiveWindow
from fabric.utils import FormattedString
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.label import Label
from gi.repository import GLib

from modules.about import About, AboutApp
from utils.roam import modus_service
from widgets.dropdown import ModusDropdown, dropdown_divider
from widgets.mousecapture import DropDownMouseCapture
from utils.app_name_resolver import format_window


# ── App category detection ─────────────────────────────────────────────────

_CATEGORY_PATTERNS = [
    ("browser",   r"zen|firefox|chromium|brave|librewolf|vivaldi|opera|msedge|epiphany|falkon"),
    ("terminal",  r"kitty|alacritty|foot|wezterm|konsole|xterm|gnome-terminal|tilix|urxvt"),
    ("editor",    r"dev\.zed\.Zed|code|vscodium|codium|vim|nvim|emacs|sublime|gedit|kate|kwrite|mousepad|xed"),
    ("notes",     r"obsidian|notion|logseq|joplin|cherrytree"),
    ("music",     r"(?i)spotify|rhythmbox|clementine|elisa|strawberry|lollypop"),
    ("files",     r"dolphin|nautilus|thunar|nemo|pcmanfm|ranger|yazi"),
    ("image",     r"gimp|inkscape|krita|feh|eog|gwenview|shotwell|gthumb"),
]

def _get_category(win_class: str) -> str:
    for cat, pattern in _CATEGORY_PATTERNS:
        if re.search(pattern, win_class or "", re.IGNORECASE):
            return cat
    return "generic"


# ── Per-category menu definitions ──────────────────────────────────────────
# Each entry: (label, shortcut) or ("---",) for divider
# Shortcut format for hyprctl dispatch sendshortcut: "MODS,key"
# e.g. "CTRL,t"  "SHIFT CTRL,z"  ",F11"

_MENUS: dict[str, dict[str, list | None]] = {
    "browser": {
        "File": [
            ("New Tab",        "CTRL,t"),
            ("New Window",     "CTRL,n"),
            ("---",),
            ("Save Page As…",  "CTRL,s"),
            ("Print…",         "CTRL,p"),
            ("---",),
            ("Close Tab",      "CTRL,w"),
            ("Close Window",   "SHIFT CTRL,w"),
        ],
        "Edit": [
            ("Undo",           "CTRL,z"),
            ("Redo",           "SHIFT CTRL,z"),
            ("---",),
            ("Cut",            "CTRL,x"),
            ("Copy",           "CTRL,c"),
            ("Paste",          "CTRL,v"),
            ("Select All",     "CTRL,a"),
            ("---",),
            ("Find…",          "CTRL,f"),
        ],
        "View": [
            ("Zoom In",        "CTRL,equal"),
            ("Zoom Out",       "CTRL,minus"),
            ("Reset Zoom",     "CTRL,0"),
            ("---",),
            ("Full Screen",    ",F11"),
            ("---",),
            ("Developer Tools","CTRL SHIFT,i"),
            ("View Source",    "CTRL,u"),
        ],
        "Go": [
            ("Back",           "ALT,Left"),
            ("Forward",        "ALT,Right"),
            ("Reload",         "CTRL,r"),
            ("---",),
            ("History",        "CTRL,h"),
            ("Bookmarks",      "CTRL,b"),
            ("Downloads",      "CTRL,j"),
        ],
    },
    "terminal": {
        "File": [
            ("New Window",     "SHIFT CTRL,n"),
            ("New Tab",        "SHIFT CTRL,t"),
            ("---",),
            ("Close Tab",      "SHIFT CTRL,w"),
            ("Close Window",   "SHIFT CTRL,q"),
        ],
        "Edit": [
            ("Copy",           "SHIFT CTRL,c"),
            ("Paste",          "SHIFT CTRL,v"),
            ("Select All",     "SHIFT CTRL,a"),
            ("---",),
            ("Clear Terminal", "CTRL,l"),
        ],
        "View": [
            ("Zoom In",        "SHIFT CTRL,equal"),
            ("Zoom Out",       "SHIFT CTRL,minus"),
            ("Reset Zoom",     "SHIFT CTRL,0"),
            ("---",),
            ("Full Screen",    ",F11"),
        ],
        "Go": None,
    },
    "editor": {
        "File": [
            ("New File",       "CTRL,n"),
            ("Open…",          "CTRL,o"),
            ("---",),
            ("Save",           "CTRL,s"),
            ("Save As…",       "SHIFT CTRL,s"),
            ("---",),
            ("Close",          "CTRL,w"),
        ],
        "Edit": [
            ("Undo",           "CTRL,z"),
            ("Redo",           "SHIFT CTRL,z"),
            ("---",),
            ("Cut",            "CTRL,x"),
            ("Copy",           "CTRL,c"),
            ("Paste",          "CTRL,v"),
            ("Select All",     "CTRL,a"),
            ("---",),
            ("Find…",          "CTRL,f"),
            ("Replace…",       "CTRL,h"),
        ],
        "View": [
            ("Zoom In",        "CTRL,equal"),
            ("Zoom Out",       "CTRL,minus"),
            ("---",),
            ("Command Palette","SHIFT CTRL,p"),
            ("Full Screen",    ",F11"),
        ],
        "Go": [
            ("Go to File…",    "CTRL,p"),
            ("Go to Line…",    "CTRL,g"),
            ("---",),
            ("Back",           "ALT,Left"),
            ("Forward",        "ALT,Right"),
        ],
    },
    "notes": {
        "File": [
            ("New Note",       "CTRL,n"),
            ("Open…",          "CTRL,o"),
            ("---",),
            ("Close",          "CTRL,w"),
        ],
        "Edit": [
            ("Undo",           "CTRL,z"),
            ("Redo",           "CTRL,y"),
            ("---",),
            ("Cut",            "CTRL,x"),
            ("Copy",           "CTRL,c"),
            ("Paste",          "CTRL,v"),
            ("Select All",     "CTRL,a"),
            ("---",),
            ("Find…",          "CTRL,f"),
            ("Command Palette","CTRL,p"),
        ],
        "View": [
            ("Zoom In",        "CTRL,equal"),
            ("Zoom Out",       "CTRL,minus"),
            ("---",),
            ("Full Screen",    ",F11"),
        ],
        "Go": None,
    },
    "music": {
        "File": None,
        "Edit": None,
        "View": [
            ("Full Screen",    ",F11"),
        ],
        "Go": None,
    },
    "files": {
        "File": [
            ("New Window",     "CTRL,n"),
            ("New Tab",        "CTRL,t"),
            ("New Folder",     "SHIFT CTRL,n"),
            ("---",),
            ("Close",          "CTRL,w"),
        ],
        "Edit": [
            ("Undo",           "CTRL,z"),
            ("Cut",            "CTRL,x"),
            ("Copy",           "CTRL,c"),
            ("Paste",          "CTRL,v"),
            ("Select All",     "CTRL,a"),
            ("---",),
            ("Find…",          "CTRL,f"),
        ],
        "View": [
            ("Zoom In",        "CTRL,equal"),
            ("Zoom Out",       "CTRL,minus"),
            ("---",),
            ("Show Hidden Files","ALT,period"),
            ("Full Screen",    ",F11"),
        ],
        "Go": [
            ("Back",           "ALT,Left"),
            ("Forward",        "ALT,Right"),
            ("Home",           "ALT,Home"),
        ],
    },
    "image": {
        "File": [
            ("New…",           "CTRL,n"),
            ("Open…",          "CTRL,o"),
            ("---",),
            ("Save",           "CTRL,s"),
            ("Save As…",       "SHIFT CTRL,s"),
            ("Export…",        "SHIFT CTRL,e"),
            ("---",),
            ("Close",          "CTRL,w"),
        ],
        "Edit": [
            ("Undo",           "CTRL,z"),
            ("Redo",           "SHIFT CTRL,z"),
            ("---",),
            ("Cut",            "CTRL,x"),
            ("Copy",           "CTRL,c"),
            ("Paste",          "CTRL,v"),
            ("Select All",     "CTRL,a"),
            ("---",),
            ("Preferences",    "SHIFT CTRL,p"),
        ],
        "View": [
            ("Zoom In",        "CTRL,equal"),
            ("Zoom Out",       "CTRL,minus"),
            ("Fit to Window",  "SHIFT CTRL,e"),
            ("---",),
            ("Full Screen",    ",F11"),
        ],
        "Go": None,
    },
    "generic": {
        "File": [
            ("Save",           "CTRL,s"),
            ("---",),
            ("Close",          "CTRL,w"),
        ],
        "Edit": [
            ("Undo",           "CTRL,z"),
            ("Redo",           "SHIFT CTRL,z"),
            ("---",),
            ("Cut",            "CTRL,x"),
            ("Copy",           "CTRL,c"),
            ("Paste",          "CTRL,v"),
            ("Select All",     "CTRL,a"),
            ("---",),
            ("Find…",          "CTRL,f"),
        ],
        "View": [
            ("Full Screen",    ",F11"),
        ],
        "Go": None,
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────

def show_about_app():
    try:
        wmclass = title = ""
        if hasattr(modus_service, "_hyprland_connection") and modus_service._hyprland_connection:
            data = modus_service._hyprland_connection.send_command("j/activewindow").reply
            if data:
                info = json.loads(data.decode("utf-8"))
                wmclass = info.get("class", "")
                title = info.get("title", "")
        if not wmclass and not title:
            return
        app_name = modus_service.current_active_app_name or "Finder"
        if app_name == "Finder":
            return
        AboutApp(app_name=app_name, wmclass=wmclass).toggle(None)
    except Exception:
        app_name = modus_service.current_active_app_name or ""
        if app_name and app_name != "Finder":
            AboutApp(app_name=app_name, wmclass="").toggle(None)


def _send_shortcut(shortcut: str, address: str):
    """Send a key shortcut to a window by address via hyprctl."""
    cmd = f"hyprctl dispatch sendshortcut {shortcut},address:{address}"
    subprocess.Popen(
        f"nohup {cmd} &",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _make_option(label: str, keybind: str = "", on_click: str = "", on_clicked=None):
    def _run(button):
        if on_clicked:
            on_clicked(button)
        else:
            subprocess.Popen(
                f"nohup {on_click} &",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        from widgets.dropdown import dropdowns
        for dd in dropdowns:
            if dd.is_visible() and hasattr(dd, "hide_via_mousecapture"):
                dd.hide_via_mousecapture()
                break

    return Button(
        child=CenterBox(
            start_children=[Label(label=label, h_align="start", name="dropdown-option-label")],
            end_children=[Label(label=keybind, h_align="end", name="dropdown-option-keybind")],
            orientation="horizontal",
            h_align="fill",
            h_expand=True,
            v_expand=True,
        ),
        name="dropdown-option",
        h_align="fill",
        on_clicked=_run,
        h_expand=True,
        v_expand=True,
    )


def _build_shortcut_items(items: list, get_address) -> list:
    """Build dropdown children from a menu spec list."""
    children = []
    for entry in items:
        if entry[0] == "---":
            children.append(dropdown_divider("---"))
        else:
            label, shortcut = entry
            # Capture shortcut and address getter in closure
            def make_cb(sc=shortcut, ga=get_address):
                def cb(_btn):
                    addr = ga()
                    if addr:
                        _send_shortcut(sc, addr)
                    from widgets.dropdown import dropdowns
                    for dd in dropdowns:
                        if dd.is_visible() and hasattr(dd, "hide_via_mousecapture"):
                            dd.hide_via_mousecapture()
                            break
                return cb
            children.append(_make_option(label, on_clicked=make_cb()))
    return children


# ── Static dropdowns ───────────────────────────────────────────────────────

class SystemDropdown(ModusDropdown):
    def __init__(self, parent, **kwargs):
        super().__init__(
            dropdown_id="os-menu",
            parent=parent,
            dropdown_children=[
                _make_option("About this PC", on_clicked=lambda _: About().toggle(_)),
                dropdown_divider("---"),
                _make_option("System Settings..."),
                dropdown_divider("---"),
                _make_option("Force Quit", "", "hyprctl kill"),
                dropdown_divider("---"),
                _make_option("Sleep", "", "systemctl suspend"),
                _make_option("Restart...", "", "systemctl reboot"),
                _make_option("Shut Down...", "", "shutdown now"),
                dropdown_divider("---"),
                _make_option("Lock Screen", "󰘳     L", "python ~/.config/Modus/lock.py"),
            ],
            **kwargs,
        )


# ── MenuBarDropdowns ───────────────────────────────────────────────────────

class MenuBarDropdowns:
    def __init__(self, parent, menubar_box):
        self._parent = parent
        self._menubar_box = menubar_box
        self._target_address: str | None = None  # window to send shortcuts to
        self._dynamic_buttons: list[Button] = []
        self._active_dynamic_btn: Button | None = None

        # ── Apple / OS menu ──────────────────────────────────────────────
        self.system_dropdown = SystemDropdown(parent=parent)
        self.menu_button_dropdown = DropDownMouseCapture(
            layer="bottom", child_window=self.system_dropdown, cover_panel=False
        )
        self.menu_button = Button(
            label="Modus",
            name="menu-button",
            style_classes="button",
            on_clicked=lambda _: self.menu_button_dropdown.toggle_mousecapture(),
        )
        self.menu_button_dropdown.child_window.set_pointing_to(self.menu_button)

        # ── Title / app-name dropdown ────────────────────────────────────
        self.global_title_menu_about = _make_option(
            f"About {modus_service.current_active_app_name}",
            on_clicked=lambda _: show_about_app(),
        )
        self._title_dropdown_menu = ModusDropdown(
            dropdown_id="global-menu-title",
            parent=parent,
            dropdown_children=[self.global_title_menu_about],
        )
        self.global_menu_title = DropDownMouseCapture(
            layer="bottom", child_window=self._title_dropdown_menu, cover_panel=False
        )
        self.global_menu_button_title = Button(
            child=ActiveWindow(
                formatter=FormattedString(
                    "{ format_window(win_title, win_class) }",
                    format_window=format_window,
                )
            ),
            name="global-title-button",
            style_classes="button",
            on_clicked=self._on_title_clicked,
        )
        self._title_dropdown_menu.set_pointing_to(self.global_menu_button_title)

        # ── Dynamic app menus (File / Edit / View / Go) ──────────────────
        self._file_menu = ModusDropdown(dropdown_id="global-menu-file", parent=parent, dropdown_children=[])
        self.global_menu_file = DropDownMouseCapture(layer="bottom", child_window=self._file_menu, cover_panel=False)
        self.global_menu_button_file = Button(
            label="File", name="global-menu-button-file", style_classes="button",
            on_clicked=lambda _: self.global_menu_file.toggle_mousecapture(),
        )
        self._file_menu.set_pointing_to(self.global_menu_button_file)

        self._edit_menu = ModusDropdown(dropdown_id="global-menu-edit", parent=parent, dropdown_children=[])
        self.global_menu_edit = DropDownMouseCapture(layer="bottom", child_window=self._edit_menu, cover_panel=False)
        self.global_menu_button_edit = Button(
            label="Edit", name="global-menu-button-edit", style_classes="button",
            on_clicked=lambda _: self.global_menu_edit.toggle_mousecapture(),
        )
        self._edit_menu.set_pointing_to(self.global_menu_button_edit)

        self._view_menu = ModusDropdown(dropdown_id="global-menu-view", parent=parent, dropdown_children=[])
        self.global_menu_view = DropDownMouseCapture(layer="bottom", child_window=self._view_menu, cover_panel=False)
        self.global_menu_button_view = Button(
            label="View", name="global-menu-button-view", style_classes="button",
            on_clicked=lambda _: self.global_menu_view.toggle_mousecapture(),
        )
        self._view_menu.set_pointing_to(self.global_menu_button_view)

        self._go_menu = ModusDropdown(dropdown_id="global-menu-go", parent=parent, dropdown_children=[])
        self.global_menu_go = DropDownMouseCapture(layer="bottom", child_window=self._go_menu, cover_panel=False)
        self.global_menu_button_go = Button(
            label="Go", name="global-menu-button-go", style_classes="button",
            on_clicked=lambda _: self.global_menu_go.toggle_mousecapture(),
        )
        self._go_menu.set_pointing_to(self.global_menu_button_go)

        # ── Static Window / Help menus ────────────────────────────────────
        self._window_menu = ModusDropdown(
            dropdown_id="global-menu-window",
            parent=parent,
            dropdown_children=[
                _make_option(
                    "Zoom In", "󰍉     +",
                    on_click="hyprctl -q keyword cursor:zoom_factor $(hyprctl getoption cursor:zoom_factor -j | jq '.float * 1.1')",
                ),
                _make_option(
                    "Zoom Out", "󰍉     -",
                    on_click="hyprctl -q keyword cursor:zoom_factor $(hyprctl getoption cursor:zoom_factor -j | jq '(.float * 0.9) | if . < 1 then 1 else . end')",
                ),
                dropdown_divider("---"),
                _make_option("Move Window to Left",   on_click="hyprctl dispatch movewindow l"),
                _make_option("Move Window to Right",  on_click="hyprctl dispatch movewindow r"),
                _make_option("Cycle Through Windows", on_click="hyprctl dispatch cyclenext"),
                dropdown_divider("---"),
                _make_option("Float",         on_click="hyprctl dispatch togglefloating"),
                _make_option("Quit",          on_click="hyprctl dispatch killactive"),
                _make_option("Pseudo",        on_click="hyprctl dispatch pseudo"),
                _make_option("Toggle Split",  on_click="hyprctl dispatch togglesplit"),
                _make_option("Center",        on_click="hyprctl dispatch centerwindow"),
                _make_option("Group",         on_click="hyprctl dispatch togglegroup"),
                _make_option(
                    "Pin",
                    on_clicked=lambda _: subprocess.run("bash ~/.config/scripts/winpin.sh", shell=True),
                ),
            ],
        )
        self.global_menu_window = DropDownMouseCapture(layer="bottom", child_window=self._window_menu, cover_panel=False)
        self.global_menu_button_window = Button(
            label="Window", name="global-menu-button-window", style_classes="button",
            on_clicked=lambda _: self.global_menu_window.toggle_mousecapture(),
        )
        self._window_menu.set_pointing_to(self.global_menu_button_window)

        self._help_menu = ModusDropdown(
            dropdown_id="global-menu-help",
            parent=parent,
            dropdown_children=[
                _make_option("Modus", on_click="xdg-open https://github.com/S4NKALP/Modus/issues"),
                dropdown_divider("---"),
                _make_option("Hyprland Wiki", on_click="xdg-open https://wiki.hyprland.org/"),
            ],
        )
        self.global_menu_help = DropDownMouseCapture(layer="bottom", child_window=self._help_menu, cover_panel=False)
        self.global_menu_button_help = Button(
            label="Help", name="global-menu-button-help", style_classes="button",
            on_clicked=lambda _: self.global_menu_help.toggle_mousecapture(),
        )
        self._help_menu.set_pointing_to(self.global_menu_button_help)

        # ── D-Bus dynamic menu (bonus: for GTK3 apps that support it) ────
        self._dyn_dropdown = _DynDropdown(parent=parent)
        self._dyn_capture = DropDownMouseCapture(layer="bottom", child_window=self._dyn_dropdown, cover_panel=False)

        # ── Signal connections ────────────────────────────────────────────
        modus_service.connect(
            "current-active-app-name-changed",
            lambda _, value: self.global_title_menu_about.set_property("label", f"About {value}"),
        )
        modus_service.connect("current-active-app-name-changed", self._on_app_changed)
        modus_service.connect("current-dropdown-changed", self.changed_dropdown)
        modus_service.connect("dropdowns-hide-changed", self.hide_dropdowns)

        # ── Hover-to-open (macOS behavior) ────────────────────────────────
        self._hover_pairs = [
            (self.global_menu_button_file, self.global_menu_file),
            (self.global_menu_button_edit, self.global_menu_edit),
            (self.global_menu_button_view, self.global_menu_view),
            (self.global_menu_button_go, self.global_menu_go),
            (self.global_menu_button_window, self.global_menu_window),
            (self.global_menu_button_help, self.global_menu_help),
        ]
        for btn, capture in self._hover_pairs:
            btn.connect(
                "enter-notify-event",
                lambda _b, _e, c=capture: self._hover_open(c),
            )
        self.global_menu_button_title.connect(
            "enter-notify-event", self._on_title_hover
        )

    # ── Hover helpers ──────────────────────────────────────────────────────

    def _all_captures(self):
        return [c for _, c in self._hover_pairs] + [
            self.menu_button_dropdown,
            self.global_menu_title,
            self._dyn_capture,
        ]

    def _any_menu_open(self) -> bool:
        return any(c.is_visible() for c in self._all_captures())

    def _hide_other_dropdowns(self, target):
        for capture in self._all_captures():
            if capture is not target and capture.is_visible():
                capture.set_child_window_visible(False)
        if target is not self._dyn_capture:
            self._active_dynamic_btn = None

    def close_open_menus(self, *_):
        for capture in self._all_captures():
            if capture.is_visible():
                capture.set_child_window_visible(False)
        self._active_dynamic_btn = None
        return False

    def _hover_open(self, capture):
        # macOS behavior: hover only tracks once a menu was opened by click
        if not self._any_menu_open():
            return False
        self._hide_other_dropdowns(capture)
        if not capture.is_visible():
            capture.set_child_window_visible(True)
        return False

    def _on_title_hover(self, *_):
        if self._title_has_target():
            self._hover_open(self.global_menu_title)
        return False

    def hover_system_dropdown(self, imac_button):
        self.system_dropdown.set_pointing_to(imac_button)
        self._hover_open(self.menu_button_dropdown)

    # ── Get target address (call before sending shortcuts) ────────────────

    def _get_target_address(self) -> str | None:
        return self._target_address

    def _update_target(self):
        try:
            if hasattr(modus_service, "_hyprland_connection") and modus_service._hyprland_connection:
                data = modus_service._hyprland_connection.send_command("j/activewindow").reply
                if data:
                    info = json.loads(data.decode("utf-8"))
                    addr = info.get("address", "")
                    cls = info.get("class", "")
                    if addr and cls:  # Don't overwrite if clicking on the panel itself
                        self._target_address = addr
                        return cls
        except Exception:
            pass
        return ""

    # ── Title button ──────────────────────────────────────────────────────

    def _title_has_target(self) -> bool:
        try:
            if hasattr(modus_service, "_hyprland_connection") and modus_service._hyprland_connection:
                data = modus_service._hyprland_connection.send_command("j/activewindow").reply
                if data:
                    info = json.loads(data.decode("utf-8"))
                    if info.get("class") or info.get("title"):
                        return True
            app = modus_service.current_active_app_name or ""
            return bool(app and app != "Finder")
        except Exception:
            return False

    def _on_title_clicked(self, _):
        if self._title_has_target():
            self.global_menu_title.toggle_mousecapture()

    # ── App context menus ─────────────────────────────────────────────────

    def _on_app_changed(self, _, value):
        GLib.idle_add(self._refresh_context_menus)

    def _rebuild_dropdown(self, modus_dropdown, items_spec: list | None):
        """Replace contents of an existing ModusDropdown in-place."""
        box = modus_dropdown.dropdown
        for child in box.get_children():
            box.remove(child)
        if items_spec:
            for w in _build_shortcut_items(items_spec, self._get_target_address):
                box.add(w)
        box.show_all()

    def _refresh_context_menus(self):
        win_class = self._update_target()

        # Also check D-Bus global menu (for GTK3 apps)
        try:
            from services.appmenu import get_registrar, fetch_menu
            pid = self._get_active_pid()
            if pid:
                info = get_registrar().get_menu_for_pid(pid)
                if info:
                    service, path = info
                    items = fetch_menu(service, path)
                    self._set_dynamic_buttons(items, service, path)
                    # Still update the static menus for the app class
        except Exception:
            self._set_dynamic_buttons([], "", "")

        category = _get_category(win_class)
        menus = _MENUS.get(category, _MENUS["generic"])

        self._rebuild_dropdown(self._file_menu,   menus.get("File"))
        self._rebuild_dropdown(self._edit_menu,   menus.get("Edit"))
        self._rebuild_dropdown(self._view_menu,   menus.get("View"))
        self._rebuild_dropdown(self._go_menu,     menus.get("Go"))

        # Show/hide File/Edit/View/Go buttons based on whether they have items
        for btn, spec_key in [
            (self.global_menu_button_file, "File"),
            (self.global_menu_button_edit, "Edit"),
            (self.global_menu_button_view, "View"),
            (self.global_menu_button_go,   "Go"),
        ]:
            has_items = bool(menus.get(spec_key))
            btn.set_visible(has_items)
            btn.set_no_show_all(not has_items)

        self._menubar_box.show_all()
        return False

    def _get_active_pid(self) -> int | None:
        try:
            if not (hasattr(modus_service, "_hyprland_connection") and modus_service._hyprland_connection):
                return None
            data = modus_service._hyprland_connection.send_command("j/activewindow").reply
            if not data:
                return None
            return json.loads(data.decode("utf-8")).get("pid")
        except Exception:
            return None

    def _set_dynamic_buttons(self, top_items: list, service: str, path: str):
        for btn in self._dynamic_buttons:
            self._menubar_box.remove(btn)
        self._dynamic_buttons = []
        self._active_dynamic_btn = None

        if self._dyn_capture.is_visible():
            self._dyn_capture.set_child_window_visible(False)

        for item in top_items:
            if not item.get("visible", True) or not item.get("label", ""):
                continue
            if item.get("type") == "separator":
                continue
            self._add_dynamic_button(item, service, path)

    def _add_dynamic_button(self, item: dict, service: str, path: str):
        from services.appmenu import activate_item
        label = item["label"]
        children = item.get("children", [])
        btn = Button(label=label, name="global-menu-button-dynamic", style_classes="button")

        def on_click(_, b=btn, sub=children, svc=service, pth=path):
            if self._dyn_capture.is_visible() and self._active_dynamic_btn is b:
                self._dyn_capture.set_child_window_visible(False)
                self._active_dynamic_btn = None
                return
            self._active_dynamic_btn = b
            self._dyn_dropdown.set_items(sub, svc, pth)
            self._dyn_dropdown.set_pointing_to(b)
            self._dyn_capture.set_child_window_visible(True)

        def on_hover(_w, _e, b=btn, sub=children, svc=service, pth=path):
            if not self._any_menu_open():
                return False
            if self._dyn_capture.is_visible() and self._active_dynamic_btn is b:
                return False
            self._hide_other_dropdowns(self._dyn_capture)
            self._active_dynamic_btn = b
            self._dyn_dropdown.set_items(sub, svc, pth)
            self._dyn_dropdown.set_pointing_to(b)
            self._dyn_capture.set_child_window_visible(True)
            return False

        btn.connect("clicked", on_click)
        btn.connect("enter-notify-event", on_hover)
        self._dynamic_buttons.append(btn)
        self._menubar_box.add(btn)

    # ── Dropdown highlight helpers ────────────────────────────────────────

    def hide_dropdowns(self, *_):
        for btn in [
            self.menu_button,
            self.global_menu_button_title,
            self.global_menu_button_file,
            self.global_menu_button_edit,
            self.global_menu_button_view,
            self.global_menu_button_go,
            self.global_menu_button_window,
            self.global_menu_button_help,
        ]:
            btn.remove_style_class("active")
        for btn in self._dynamic_buttons:
            btn.remove_style_class("active")

    def changed_dropdown(self, _, dropdown_id):
        self.hide_dropdowns()
        match dropdown_id:
            case "os-menu":
                self.menu_button.add_style_class("active")
            case "global-menu-title":
                self.global_menu_button_title.add_style_class("active")
            case "global-menu-file":
                self.global_menu_button_file.add_style_class("active")
            case "global-menu-edit":
                self.global_menu_button_edit.add_style_class("active")
            case "global-menu-view":
                self.global_menu_button_view.add_style_class("active")
            case "global-menu-go":
                self.global_menu_button_go.add_style_class("active")
            case "global-menu-window":
                self.global_menu_button_window.add_style_class("active")
            case "global-menu-help":
                self.global_menu_button_help.add_style_class("active")
            case "dynamic-app-menu" if self._active_dynamic_btn:
                self._active_dynamic_btn.add_style_class("active")


# ── D-Bus dynamic dropdown (for GTK3 apps) ────────────────────────────────

class _DynDropdown(ModusDropdown):
    def __init__(self, parent, **kwargs):
        super().__init__(dropdown_id="dynamic-app-menu", parent=parent, dropdown_children=[], **kwargs)

    def set_items(self, items: list, service: str, path: str):
        from services.appmenu import activate_item
        for child in self.dropdown.get_children():
            self.dropdown.remove(child)
        for item in items:
            item_type = item.get("type", "standard")
            label = item.get("label", "")
            enabled = item.get("enabled", True)
            if item_type == "separator" or not label:
                self.dropdown.add(dropdown_divider("---"))
                continue
            item_id = item["id"]
            opt = _make_option(
                label,
                on_clicked=lambda _, iid=item_id, svc=service, pth=path: activate_item(svc, pth, iid),
            )
            if not enabled:
                opt.set_sensitive(False)
            self.dropdown.add(opt)
        self.dropdown.show_all()


# ── MenuBar ────────────────────────────────────────────────────────────────

class MenuBar(Box):
    def __init__(self, parent_window=None, **kwargs):
        if parent_window is None:
            parent_window = kwargs.pop("parent_window", None)

        super().__init__(name="menubar", orientation="horizontal", spacing=0, **kwargs)

        self.dropdown_system = MenuBarDropdowns(parent=parent_window, menubar_box=self)

        self.children = [
            self.dropdown_system.global_menu_button_title,
            self.dropdown_system.global_menu_button_file,
            self.dropdown_system.global_menu_button_edit,
            self.dropdown_system.global_menu_button_view,
            self.dropdown_system.global_menu_button_go,
            self.dropdown_system.global_menu_button_window,
            self.dropdown_system.global_menu_button_help,
        ]

        # Populate menus for whatever is active at startup
        GLib.timeout_add(500, self.dropdown_system._refresh_context_menus)

    def show_system_dropdown(self, imac_button):
        mc = self.dropdown_system.menu_button_dropdown
        self.dropdown_system.menu_button_dropdown.child_window.set_pointing_to(imac_button)
        if mc.is_visible():
            mc.set_child_window_visible(False)
        else:
            mc.set_child_window_visible(True)

    def hover_system_dropdown(self, imac_button):
        self.dropdown_system.hover_system_dropdown(imac_button)

    def close_open_menus(self, *_):
        self.dropdown_system.close_open_menus()
