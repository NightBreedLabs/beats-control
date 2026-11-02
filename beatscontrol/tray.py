"""Minimal StatusNotifierItem with a menu, for tray hosts such as Noctalia and Plasma."""
from gi.repository import Gio, GLib

from . import APP_ID

ITEM_PATH = '/StatusNotifierItem'
MENU_PATH = '/StatusNotifierMenu'
WATCHER = 'org.kde.StatusNotifierWatcher'
ITEM_XML = '''<node><interface name="org.kde.StatusNotifierItem">
<property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/>
<property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/>
<property name="IconName" type="s" access="read"/><property name="ItemIsMenu" type="b" access="read"/>
<property name="Menu" type="o" access="read"/><property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
<signal name="NewTitle"/><signal name="NewToolTip"/><signal name="NewStatus"><arg type="s"/></signal>
</interface></node>'''
MENU_XML = '''<node><interface name="com.canonical.dbusmenu">
<property name="Version" type="u" access="read"/><property name="Status" type="s" access="read"/>
<method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/><arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
<method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/></method>
<method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
<method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
<signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
</interface></node>'''


class Tray:
    def __init__(self, connection, activate, toggle_anc, quit_app):
        self.bus = connection
        self.activate, self.toggle_anc, self.quit_app = activate, toggle_anc, quit_app
        self.title = 'Beats Control'
        self.anc_label = 'Noise cancelling: unavailable'
        self.revision = 1
        item = Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self.bus.register_object(ITEM_PATH, item, self._item_call, self._item_property)
        self.bus.register_object(MENU_PATH, menu, self._menu_call, self._menu_property)
        Gio.bus_watch_name_on_connection(self.bus, WATCHER, Gio.BusNameWatcherFlags.NONE, self._register, None)

    def _register(self, *_):
        self.bus.call(WATCHER, '/StatusNotifierWatcher', WATCHER, 'RegisterStatusNotifierItem', GLib.Variant('(s)', (ITEM_PATH,)), None, Gio.DBusCallFlags.NONE, 5000, None, self._registered)

    def _registered(self, bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error:
            pass

    def _item_property(self, _b, _s, _p, _i, name):
        return {
            'Category': GLib.Variant('s', 'Hardware'),
            'Id': GLib.Variant('s', APP_ID),
            'Title': GLib.Variant('s', self.title),
            'Status': GLib.Variant('s', 'Active'),
            'IconName': GLib.Variant('s', APP_ID),
            'ItemIsMenu': GLib.Variant('b', False),
            'Menu': GLib.Variant('o', MENU_PATH),
            'ToolTip': GLib.Variant('(sa(iiay)ss)', (APP_ID, [], self.title, '')),
        }.get(name)

    def _item_call(self, _b, _s, _p, _i, method, _params, invocation):
        if method == 'Activate':
            self.activate()
        elif method == 'SecondaryActivate':
            self.toggle_anc()
        invocation.return_value(None)

    def _menu_property(self, _b, _s, _p, _i, name):
        return {'Version': GLib.Variant('u', 3), 'Status': GLib.Variant('s', 'normal')}.get(name)

    def _entries(self):
        return [(1, self.title, False), (2, self.anc_label, True), (3, 'Open Beats Control', True), (4, 'Quit', True)]

    def _node(self, entry):
        identity, label, enabled = entry
        return GLib.Variant('(ia{sv}av)', (identity, {'label': GLib.Variant('s', label), 'enabled': GLib.Variant('b', enabled)}, []))

    def _menu_call(self, _b, _s, _p, _i, method, params, invocation):
        if method == 'GetLayout':
            children = [GLib.Variant('v', self._node(e)) for e in self._entries()]
            root = (0, {'children-display': GLib.Variant('s', 'submenu')}, [c.get_variant() and GLib.Variant('v', c.get_variant()).get_variant() for c in children])
            invocation.return_value(GLib.Variant('(u(ia{sv}av))', (self.revision, root)))
        elif method == 'GetGroupProperties':
            invocation.return_value(GLib.Variant('(a(ia{sv}))', ([],)))
        elif method == 'AboutToShow':
            invocation.return_value(GLib.Variant('(b)', (False,)))
        else:
            identity, kind = params.get_child_value(0).get_int32(), params.get_child_value(1).get_string()
            invocation.return_value(None)
            if kind == 'clicked':
                {2: self.toggle_anc, 3: self.activate, 4: self.quit_app}.get(identity, lambda: None)()

    def update(self, title, anc_label):
        if (title, anc_label) == (self.title, self.anc_label):
            return
        self.title, self.anc_label = title, anc_label
        self.revision += 1
        self.bus.emit_signal(None, ITEM_PATH, 'org.kde.StatusNotifierItem', 'NewTitle', None)
        self.bus.emit_signal(None, ITEM_PATH, 'org.kde.StatusNotifierItem', 'NewToolTip', None)
        self.bus.emit_signal(None, MENU_PATH, 'com.canonical.dbusmenu', 'LayoutUpdated', GLib.Variant('(ui)', (self.revision, 0)))
