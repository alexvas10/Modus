import time

import dbus
import dbus.service
import dbus.mainloop.glib
from loguru import logger

# Must run before any SessionBus() calls
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


# ── D-Bus registrar service ────────────────────────────────────────────────

class _RegistrarService(dbus.service.Object):
    """Owns com.canonical.AppMenu.Registrar and stores registrations."""

    def __init__(self, bus, pid_map: dict):
        self._bus = bus
        self._pid_map = pid_map  # shared with AppMenuRegistrar
        bus_name = dbus.service.BusName(
            "com.canonical.AppMenu.Registrar", bus, do_not_queue=True
        )
        super().__init__(bus_name, "/com/canonical/AppMenu/Registrar")

    def _pid_of(self, sender):
        try:
            proxy = self._bus.get_object(
                "org.freedesktop.DBus", "/org/freedesktop/DBus"
            )
            return int(
                dbus.Interface(proxy, "org.freedesktop.DBus")
                    .GetConnectionUnixProcessID(sender)
            )
        except Exception:
            return None

    @dbus.service.method(
        "com.canonical.AppMenu.Registrar",
        in_signature="uo", out_signature="",
        sender_keyword="sender",
    )
    def RegisterWindow(self, window_id, menu_path, sender=None):
        service = str(sender) if sender else ""
        path = str(menu_path)
        pid = self._pid_of(sender)
        if pid:
            self._pid_map[pid] = (service, path)
        logger.debug(f"[AppMenu] RegisterWindow pid={pid} service={service}")
        self.WindowRegistered(int(window_id), service, path)

    @dbus.service.method(
        "com.canonical.AppMenu.Registrar", in_signature="u", out_signature=""
    )
    def UnregisterWindow(self, window_id):
        self.WindowUnregistered(int(window_id))

    @dbus.service.method(
        "com.canonical.AppMenu.Registrar", in_signature="u", out_signature="so"
    )
    def GetMenuForWindow(self, window_id):
        raise dbus.exceptions.DBusException(
            name="com.canonical.AppMenu.Registrar.NoMenuWindowFound"
        )

    @dbus.service.signal("com.canonical.AppMenu.Registrar", signature="uso")
    def WindowRegistered(self, window_id, service, menu_path): pass

    @dbus.service.signal("com.canonical.AppMenu.Registrar", signature="u")
    def WindowUnregistered(self, window_id): pass


class AppMenuRegistrar:
    """
    Starts (or observes) com.canonical.AppMenu.Registrar and provides
    a PID-keyed lookup for registered menus.
    """

    def __init__(self):
        self._pid_map: dict[int, tuple[str, str]] = {}
        self._bus = dbus.SessionBus()
        self._service = None

        try:
            self._service = _RegistrarService(self._bus, self._pid_map)
            logger.info("[AppMenu] Acquired com.canonical.AppMenu.Registrar")
        except dbus.exceptions.NameExistsException:
            logger.info("[AppMenu] Registrar already running — connecting as observer")
            self._connect_observer()

    def _pid_of(self, service_name: str):
        try:
            proxy = self._bus.get_object(
                "org.freedesktop.DBus", "/org/freedesktop/DBus"
            )
            return int(
                dbus.Interface(proxy, "org.freedesktop.DBus")
                    .GetConnectionUnixProcessID(service_name)
            )
        except Exception:
            return None

    def _connect_observer(self):
        try:
            obj = self._bus.get_object(
                "com.canonical.AppMenu.Registrar",
                "/com/canonical/AppMenu/Registrar",
            )
            obj.connect_to_signal("WindowRegistered", self._on_registered)
        except Exception as e:
            logger.warning(f"[AppMenu] Observer connect failed: {e}")

    def _on_registered(self, window_id, service, menu_path):
        pid = self._pid_of(str(service))
        if pid:
            self._pid_map[pid] = (str(service), str(menu_path))

    def get_menu_for_pid(self, pid: int):
        """Return (service, path) tuple or None."""
        return self._pid_map.get(int(pid))


# ── Menu layout helpers ────────────────────────────────────────────────────

def _parse(layout):
    item_id, props, children = layout
    props = dict(props)
    return {
        "id": int(item_id),
        "label": str(props.get("label", "")).replace("_", ""),
        "enabled": bool(props.get("enabled", True)),
        "visible": bool(props.get("visible", True)),
        "type": str(props.get("type", "standard")),
        "children": [_parse(c) for c in children],
    }


def fetch_menu(service: str, path: str) -> list:
    """Return parsed top-level menu items (File, Edit, …) from a dbusmenu service."""
    try:
        bus = dbus.SessionBus()
        obj = bus.get_object(str(service), str(path))
        iface = dbus.Interface(obj, "com.canonical.dbusmenu")
        _, layout = iface.GetLayout(0, 3, dbus.Array([], signature="s"))
        root = _parse(layout)
        return [c for c in root.get("children", []) if c.get("visible", True)]
    except Exception as e:
        logger.warning(f"[AppMenu] fetch_menu failed: {e}")
        return []


def activate_item(service: str, path: str, item_id: int):
    """Fire a click event on a dbusmenu item."""
    try:
        bus = dbus.SessionBus()
        obj = bus.get_object(str(service), str(path))
        iface = dbus.Interface(obj, "com.canonical.dbusmenu")
        iface.Event(
            int(item_id), "clicked", dbus.String(""), dbus.UInt32(int(time.time()))
        )
    except Exception as e:
        logger.warning(f"[AppMenu] activate_item failed: {e}")


# ── Singleton ──────────────────────────────────────────────────────────────

_registrar: AppMenuRegistrar | None = None


def get_registrar() -> AppMenuRegistrar:
    global _registrar
    if _registrar is None:
        _registrar = AppMenuRegistrar()
    return _registrar
