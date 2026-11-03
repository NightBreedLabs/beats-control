"""BlueZ link: finds the headphones and gets the control channel as a file descriptor.

The Flatpak sandbox blocks AF_BLUETOOTH sockets, so BlueZ opens the channel through a
registered Profile1 object and passes the descriptor over D-Bus.
"""
import socket

from gi.repository import Gio, GLib, GObject

from .protocol import AAP_PSM, AAP_UUID, HANDSHAKE, SUBSCRIBE, set_anc, parse, AncState, Battery, HandshakeAck

BLUEZ = 'org.bluez'
DEVICE_IFACE = 'org.bluez.Device1'
TRANSPORT_IFACE = 'org.bluez.MediaTransport1'
PROFILE_PATH = '/io/github/NightBreedLabs/BeatsControl/profile'
MODALIAS = 'bluetooth:v004Cp2009'
PROFILE_XML = '''<node><interface name="org.bluez.Profile1">
<method name="Release"/>
<method name="NewConnection"><arg type="o" direction="in"/><arg type="h" direction="in"/><arg type="a{sv}" direction="in"/></method>
<method name="RequestDisconnection"><arg type="o" direction="in"/></method>
</interface></node>'''


class Headphones(GObject.Object):
    """Single headphone device state, updated from BlueZ and the control channel."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'volume-pressed': (GObject.SignalFlags.RUN_FIRST, None, (int, int)),
    }

    def __init__(self):
        super().__init__()
        self.path = None
        self.props = {}
        self.anc = None
        self.battery = None
        self.charging = False
        self.control_ready = False
        self.error = None
        self.transport = None
        self.volume = None
        self.expected_volume = None
        self._sock = None
        self._watch = 0
        self._retry = 0
        self._retry_source = 0
        self._registered = False
        self._subscriptions = []
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
        info = Gio.DBusNodeInfo.new_for_xml(PROFILE_XML).interfaces[0]
        self._object_id = self.bus.register_object(PROFILE_PATH, info, self._profile_call)
        Gio.bus_watch_name_on_connection(self.bus, BLUEZ, Gio.BusNameWatcherFlags.NONE, self._bluez_up, self._bluez_down)
        self._subscriptions.append(self.bus.signal_subscribe(BLUEZ, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', None, DEVICE_IFACE, Gio.DBusSignalFlags.NONE, self._on_properties))
        self._subscriptions.append(self.bus.signal_subscribe(BLUEZ, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', None, TRANSPORT_IFACE, Gio.DBusSignalFlags.NONE, self._on_transport))
        for name in ('InterfacesAdded', 'InterfacesRemoved'):
            self._subscriptions.append(self.bus.signal_subscribe(BLUEZ, 'org.freedesktop.DBus.ObjectManager', name, '/', None, Gio.DBusSignalFlags.NONE, lambda *a: self._refresh()))

    @property
    def found(self):
        return self.path is not None

    @property
    def connected(self):
        return bool(self.props.get('Connected'))

    @property
    def name(self):
        return self.props.get('Alias') or 'Beats Studio3'

    @property
    def address(self):
        return self.props.get('Address', '')

    @property
    def firmware(self):
        modalias = self.props.get('Modalias', '')
        return modalias.rsplit('d', 1)[-1] if MODALIAS in modalias else ''

    def _call(self, path, iface, method, args, done=None, timeout=20000):
        def finish(bus, result):
            try:
                reply = bus.call_finish(result)
                error = None
            except GLib.Error as exc:
                reply, error = None, exc
            if done:
                done(reply, error)
        self.bus.call(BLUEZ, path, iface, method, args, None, Gio.DBusCallFlags.NONE, timeout, None, finish)

    def _bluez_up(self, *_):
        options = {
            'Name': GLib.Variant('s', 'Beats Control'),
            'Role': GLib.Variant('s', 'client'),
            'PSM': GLib.Variant('q', AAP_PSM),
            'AutoConnect': GLib.Variant('b', False),
            'RequireAuthentication': GLib.Variant('b', False),
            'RequireAuthorization': GLib.Variant('b', False),
        }
        self._call('/org/bluez', 'org.bluez.ProfileManager1', 'RegisterProfile', GLib.Variant('(osa{sv})', (PROFILE_PATH, AAP_UUID, options)), self._registered_done)

    def _registered_done(self, _reply, error):
        self._registered = error is None or 'AlreadyExists' in error.message
        self.error = None if self._registered else error.message
        self._refresh()

    def _bluez_down(self, *_):
        self._registered = False
        self._close()
        self.path = None
        self.props = {}
        self.error = 'Bluetooth service is not running'
        self.emit('changed')

    def _refresh(self):
        self._call('/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects', None, self._objects)

    def _objects(self, reply, error):
        if error:
            self.error = error.message
            self.emit('changed')
            return
        previous = self.path
        self.path, self.props = None, {}
        objects = reply.unpack()[0]
        for path, interfaces in objects.items():
            device = interfaces.get(DEVICE_IFACE)
            if device and str(device.get('Modalias', '')).startswith(MODALIAS):
                self.path, self.props = path, dict(device)
                if device.get('Connected'):
                    break
        self.transport, self.volume = None, None
        for path, interfaces in objects.items():
            transport = interfaces.get(TRANSPORT_IFACE)
            if self.path and transport and path.startswith(self.path + '/'):
                self.transport = path
                self.volume = transport.get('Volume')
        if previous != self.path:
            self._close()
        self.emit('changed')
        self._ensure_channel()

    def _on_properties(self, _bus, _sender, path, _iface, _signal, params):
        if path != self.path:
            return
        _name, changed, _invalid = params.unpack()
        self.props.update(changed)
        if 'Connected' in changed:
            self._retry = 0
            if changed['Connected']:
                GLib.timeout_add(1200, self._ensure_channel)
            else:
                self._close()
        self.emit('changed')

    def _on_transport(self, _bus, _sender, path, _iface, _signal, params):
        _name, changed, _invalid = params.unpack()
        if path != self.transport or 'Volume' not in changed:
            return
        value, old = changed['Volume'], self.volume
        self.volume = value
        if value == self.expected_volume:
            self.expected_volume = None
        elif old is not None and value != old:
            self.emit('volume-pressed', old, value)
        self.emit('changed')

    def set_volume(self, value):
        value = max(0, min(127, int(value)))
        if not self.transport or value == self.volume:
            return
        self.volume, self.expected_volume = value, value
        self._call(self.transport, 'org.freedesktop.DBus.Properties', 'Set', GLib.Variant('(ssv)', (TRANSPORT_IFACE, 'Volume', GLib.Variant('q', value))))
        self.emit('changed')

    def _ensure_channel(self):
        if self._registered and self.connected and not self._sock and not self._retry_source:
            self._call(self.path, DEVICE_IFACE, 'ConnectProfile', GLib.Variant('(s)', (AAP_UUID,)), self._profile_done)
        return GLib.SOURCE_REMOVE

    def _profile_done(self, _reply, error):
        if not error or self._sock or self._retry >= 5:
            return
        self._retry += 1
        self._retry_source = GLib.timeout_add_seconds(2, self._retry_now)

    def _retry_now(self):
        self._retry_source = 0
        self._ensure_channel()
        return GLib.SOURCE_REMOVE

    def _profile_call(self, _bus, _sender, _path, _iface, method, params, invocation):
        if method == 'NewConnection':
            fds = invocation.get_message().get_unix_fd_list()
            self._open(fds.get(params.get_child_value(1).get_handle()))
        elif method == 'RequestDisconnection':
            self._close()
        invocation.return_value(None)

    def _open(self, fd):
        self._close()
        self._sock = socket.socket(fileno=fd)
        self._sock.setblocking(False)
        self._watch = GLib.io_add_watch(self._sock.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._readable)
        self._send(HANDSHAKE)

    def _send(self, frame):
        if not self._sock:
            return False
        try:
            self._sock.send(frame)
            return True
        except OSError:
            self._close()
            return False

    def _readable(self, _fd, _condition):
        try:
            frame = self._sock.recv(1024)
        except BlockingIOError:
            return GLib.SOURCE_CONTINUE
        except OSError:
            frame = b''
        if not frame:
            self._watch = 0
            self._close()
            return GLib.SOURCE_REMOVE
        self._handle(parse(frame))
        return GLib.SOURCE_CONTINUE

    def _handle(self, event):
        if isinstance(event, HandshakeAck):
            self._send(SUBSCRIBE)
            self.control_ready = True
        elif isinstance(event, AncState):
            self.anc = event.enabled
        elif isinstance(event, Battery):
            self.battery, self.charging = event.level, event.charging
        else:
            return
        self.emit('changed')

    def _close(self):
        if self._watch:
            GLib.source_remove(self._watch)
            self._watch = 0
        if self._sock:
            self._sock.close()
            self._sock = None
        was_ready = self.control_ready
        self.control_ready = False
        self.anc = None
        if was_ready:
            self.emit('changed')
            if self.connected:
                self._retry_source = self._retry_source or GLib.timeout_add_seconds(2, self._retry_now)

    def set_anc(self, enabled):
        return self.control_ready and self._send(set_anc(enabled))

    def connect_device(self, done=None):
        if self.path:
            self._call(self.path, DEVICE_IFACE, 'Connect', None, lambda _r, e: done and done(e), 30000)

    def disconnect_device(self, done=None):
        if self.path:
            self._call(self.path, DEVICE_IFACE, 'Disconnect', None, lambda _r, e: done and done(e))

    def rename(self, alias):
        if self.path:
            self._call(self.path, 'org.freedesktop.DBus.Properties', 'Set', GLib.Variant('(ssv)', (DEVICE_IFACE, 'Alias', GLib.Variant('s', alias))))

    def shutdown(self):
        self._close()
        if self._registered:
            try:
                self.bus.call_sync(BLUEZ, '/org/bluez', 'org.bluez.ProfileManager1', 'UnregisterProfile', GLib.Variant('(o)', (PROFILE_PATH,)), None, Gio.DBusCallFlags.NONE, 1500, None)
            except GLib.Error:
                pass
