"""Synthesized menu bars for apps that export no DBus/GTK menu.

Most Linux apps never export a menu over DBus, which leaves the global menu
showing nothing but the window title. For those, we synthesize a plausible
menu bar from the app's category and drive it by sending the app's own
keyboard shortcuts back to it via `hyprctl dispatch sendshortcut`.
"""

import json
import re

from fabric.utils import exec_shell_command_async, logger
from gi.repository import Gtk

from utils.gtk_utils import setup_cursor_hover

# App category detection
_CATEGORY_PATTERNS = [
    ("browser", r"zen|firefox|chromium|brave|librewolf|vivaldi|opera|msedge|epiphany|falkon"),
    ("terminal", r"kitty|alacritty|foot|wezterm|konsole|xterm|gnome-terminal|tilix|urxvt"),
    ("editor", r"dev\.zed\.Zed|code|vscodium|codium|vim|nvim|emacs|sublime|gedit|kate|kwrite|mousepad|xed"),
    ("notes", r"obsidian|notion|logseq|joplin|cherrytree"),
    ("music", r"spotify|rhythmbox|clementine|elisa|strawberry|lollypop"),
    ("files", r"dolphin|nautilus|thunar|nemo|pcmanfm|ranger|yazi"),
    ("image", r"gimp|inkscape|krita|feh|eog|gwenview|shotwell|gthumb"),
]


def get_category(win_class: str) -> str:
    for cat, pattern in _CATEGORY_PATTERNS:
        if re.search(pattern, win_class or "", re.IGNORECASE):
            return cat
    return "generic"


# Per-category menu definitions.
# Each entry: (label, shortcut) or ("---",) for a divider.
# Shortcut format matches `hyprctl dispatch sendshortcut`: "MODS,key"
# e.g. "CTRL,t"  "SHIFT CTRL,z"  ",F11"
_MENUS: dict[str, dict[str, list | None]] = {
    "browser": {
        "File": [
            ("New Tab", "CTRL,t"),
            ("New Window", "CTRL,n"),
            ("---",),
            ("Save Page As…", "CTRL,s"),
            ("Print…", "CTRL,p"),
            ("---",),
            ("Close Tab", "CTRL,w"),
            ("Close Window", "SHIFT CTRL,w"),
        ],
        "Edit": [
            ("Undo", "CTRL,z"),
            ("Redo", "SHIFT CTRL,z"),
            ("---",),
            ("Cut", "CTRL,x"),
            ("Copy", "CTRL,c"),
            ("Paste", "CTRL,v"),
            ("Select All", "CTRL,a"),
            ("---",),
            ("Find…", "CTRL,f"),
        ],
        "View": [
            ("Zoom In", "CTRL,equal"),
            ("Zoom Out", "CTRL,minus"),
            ("Reset Zoom", "CTRL,0"),
            ("---",),
            ("Full Screen", ",F11"),
            ("---",),
            ("Developer Tools", "CTRL SHIFT,i"),
            ("View Source", "CTRL,u"),
        ],
        "Go": [
            ("Back", "ALT,Left"),
            ("Forward", "ALT,Right"),
            ("Reload", "CTRL,r"),
            ("---",),
            ("History", "CTRL,h"),
            ("Bookmarks", "CTRL,b"),
            ("Downloads", "CTRL,j"),
        ],
    },
    "terminal": {
        "File": [
            ("New Window", "SHIFT CTRL,n"),
            ("New Tab", "SHIFT CTRL,t"),
            ("---",),
            ("Close Tab", "SHIFT CTRL,w"),
            ("Close Window", "SHIFT CTRL,q"),
        ],
        "Edit": [
            ("Copy", "SHIFT CTRL,c"),
            ("Paste", "SHIFT CTRL,v"),
            ("Select All", "SHIFT CTRL,a"),
            ("---",),
            ("Clear Terminal", "CTRL,l"),
        ],
        "View": [
            ("Zoom In", "SHIFT CTRL,equal"),
            ("Zoom Out", "SHIFT CTRL,minus"),
            ("Reset Zoom", "SHIFT CTRL,0"),
            ("---",),
            ("Full Screen", ",F11"),
        ],
        "Go": None,
    },
    "editor": {
        "File": [
            ("New File", "CTRL,n"),
            ("Open…", "CTRL,o"),
            ("---",),
            ("Save", "CTRL,s"),
            ("Save As…", "SHIFT CTRL,s"),
            ("---",),
            ("Close", "CTRL,w"),
        ],
        "Edit": [
            ("Undo", "CTRL,z"),
            ("Redo", "SHIFT CTRL,z"),
            ("---",),
            ("Cut", "CTRL,x"),
            ("Copy", "CTRL,c"),
            ("Paste", "CTRL,v"),
            ("Select All", "CTRL,a"),
            ("---",),
            ("Find…", "CTRL,f"),
            ("Replace…", "CTRL,h"),
        ],
        "View": [
            ("Zoom In", "CTRL,equal"),
            ("Zoom Out", "CTRL,minus"),
            ("---",),
            ("Command Palette", "SHIFT CTRL,p"),
            ("Full Screen", ",F11"),
        ],
        "Go": [
            ("Go to File…", "CTRL,p"),
            ("Go to Line…", "CTRL,g"),
            ("---",),
            ("Back", "ALT,Left"),
            ("Forward", "ALT,Right"),
        ],
    },
    "notes": {
        "File": [
            ("New Note", "CTRL,n"),
            ("Open…", "CTRL,o"),
            ("---",),
            ("Close", "CTRL,w"),
        ],
        "Edit": [
            ("Undo", "CTRL,z"),
            ("Redo", "CTRL,y"),
            ("---",),
            ("Cut", "CTRL,x"),
            ("Copy", "CTRL,c"),
            ("Paste", "CTRL,v"),
            ("Select All", "CTRL,a"),
            ("---",),
            ("Find…", "CTRL,f"),
            ("Command Palette", "CTRL,p"),
        ],
        "View": [
            ("Zoom In", "CTRL,equal"),
            ("Zoom Out", "CTRL,minus"),
            ("---",),
            ("Full Screen", ",F11"),
        ],
        "Go": None,
    },
    "music": {
        "File": None,
        "Edit": None,
        "View": [
            ("Full Screen", ",F11"),
        ],
        "Go": None,
    },
    "files": {
        "File": [
            ("New Window", "CTRL,n"),
            ("New Tab", "CTRL,t"),
            ("New Folder", "SHIFT CTRL,n"),
            ("---",),
            ("Close", "CTRL,w"),
        ],
        "Edit": [
            ("Undo", "CTRL,z"),
            ("Cut", "CTRL,x"),
            ("Copy", "CTRL,c"),
            ("Paste", "CTRL,v"),
            ("Select All", "CTRL,a"),
            ("---",),
            ("Find…", "CTRL,f"),
        ],
        "View": [
            ("Zoom In", "CTRL,equal"),
            ("Zoom Out", "CTRL,minus"),
            ("---",),
            ("Show Hidden Files", "ALT,period"),
            ("Full Screen", ",F11"),
        ],
        "Go": [
            ("Back", "ALT,Left"),
            ("Forward", "ALT,Right"),
            ("Home", "ALT,Home"),
        ],
    },
    "image": {
        "File": [
            ("New…", "CTRL,n"),
            ("Open…", "CTRL,o"),
            ("---",),
            ("Save", "CTRL,s"),
            ("Save As…", "SHIFT CTRL,s"),
            ("Export…", "SHIFT CTRL,e"),
            ("---",),
            ("Close", "CTRL,w"),
        ],
        "Edit": [
            ("Undo", "CTRL,z"),
            ("Redo", "SHIFT CTRL,z"),
            ("---",),
            ("Cut", "CTRL,x"),
            ("Copy", "CTRL,c"),
            ("Paste", "CTRL,v"),
            ("Select All", "CTRL,a"),
            ("---",),
            ("Preferences", "SHIFT CTRL,p"),
        ],
        "View": [
            ("Zoom In", "CTRL,equal"),
            ("Zoom Out", "CTRL,minus"),
            ("Fit to Window", "SHIFT CTRL,e"),
            ("---",),
            ("Full Screen", ",F11"),
        ],
        "Go": None,
    },
    "generic": {
        "File": [
            ("Save", "CTRL,s"),
            ("---",),
            ("Close", "CTRL,w"),
        ],
        "Edit": [
            ("Undo", "CTRL,z"),
            ("Redo", "SHIFT CTRL,z"),
            ("---",),
            ("Cut", "CTRL,x"),
            ("Copy", "CTRL,c"),
            ("Paste", "CTRL,v"),
            ("Select All", "CTRL,a"),
            ("---",),
            ("Find…", "CTRL,f"),
        ],
        "View": [
            ("Full Screen", ",F11"),
        ],
        "Go": None,
    },
}

# Menu order as shown in the bar
_MENU_ORDER = ("File", "Edit", "View", "Go")


def get_active_window() -> tuple[str, str]:
    """Return (address, wm_class) of the focused window, or ("", "")."""
    try:
        import subprocess

        out = subprocess.run(
            ["hyprctl", "-j", "activewindow"],
            capture_output=True,
            text=True,
            timeout=1,
        ).stdout
        info = json.loads(out) if out else {}
        return info.get("address", "") or "", info.get("class", "") or ""
    except Exception as e:
        logger.warning(f"[FallbackMenu] activewindow query failed: {e}")
        return "", ""


def send_shortcut(shortcut: str, address: str):
    """Send a key shortcut to a window by address."""
    if not address:
        return
    exec_shell_command_async(
        f"hyprctl dispatch sendshortcut {shortcut},address:{address}",
        lambda *_: None,
    )


class FallbackMenuBuilder:
    """Builds synthesized menu buttons for a window class.

    The target address is captured when the menus are built (while the app is
    still focused) and refreshed on click when a real window is focused, so
    interacting with the panel itself never retargets the shortcut.
    """

    def __init__(self):
        self._target_address = ""

    def _resolve_address(self) -> str:
        address, wm_class = get_active_window()
        # Only retarget when a genuine window is focused; clicking the panel
        # must not clear the stored address.
        if address and wm_class:
            self._target_address = address
        return self._target_address

    def _build_menu(self, entries: list) -> Gtk.Menu:
        menu = Gtk.Menu()
        for entry in entries:
            if entry[0] == "---":
                menu.append(Gtk.SeparatorMenuItem())
                continue

            label, shortcut = entry[0], entry[1]
            item = Gtk.MenuItem.new_with_label(label)
            item.connect(
                "activate",
                lambda _, sc=shortcut: send_shortcut(sc, self._resolve_address()),
            )
            menu.append(item)
        menu.show_all()
        return menu

    def build_buttons(self, wm_class: str) -> list[Gtk.MenuButton]:
        """Return menu buttons for the given window class, or [] if none apply."""
        category = get_category(wm_class)
        spec = _MENUS.get(category)
        if not spec:
            return []

        # Capture the target while the app is still the focused window.
        self._resolve_address()

        buttons = []
        for name in _MENU_ORDER:
            entries = spec.get(name)
            if not entries:
                continue

            button = Gtk.MenuButton(label=name, name="global-menu")
            button.get_style_context().add_class("global-menu")
            setup_cursor_hover(button, "pointer")
            button.set_popup(self._build_menu(entries))
            button.show_all()
            buttons.append(button)

        logger.info(
            f"[FallbackMenu] built {len(buttons)} menus for "
            f"class={wm_class!r} category={category}"
        )
        return buttons
