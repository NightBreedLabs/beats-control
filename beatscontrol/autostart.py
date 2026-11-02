"""Start at login through the XDG Background portal."""
from gi.repository import Gio, GLib


def request(connection, enabled, done):
    """Ask for autostart on or off, then call done(granted, message)."""
    token = f'beats{GLib.random_int()}'
    sender = connection.get_unique_name()[1:].replace('.', '_')
    handle = f'/org/freedesktop/portal/desktop/request/{sender}/{token}'
    subscription = [0]

    def response(_bus, _sender, _path, _iface, _signal, params):
        connection.signal_unsubscribe(subscription[0])
        code, results = params.unpack()
        done(code == 0 and bool(results.get('autostart')) == enabled, None if code == 0 else 'Request was declined')

    subscription[0] = connection.signal_subscribe('org.freedesktop.portal.Desktop', 'org.freedesktop.portal.Request', 'Response', handle, None, Gio.DBusSignalFlags.NONE, response)
    options = {
        'handle_token': GLib.Variant('s', token),
        'reason': GLib.Variant('s', 'Show headphone status and keep your settings applied'),
        'autostart': GLib.Variant('b', enabled),
        'background': GLib.Variant('b', True),
        'commandline': GLib.Variant('as', ['beats-control', '--background']),
    }

    def called(bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error as exc:
            connection.signal_unsubscribe(subscription[0])
            done(False, exc.message)

    connection.call('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop', 'org.freedesktop.portal.Background', 'RequestBackground', GLib.Variant('(sa{sv})', ('', options)), None, Gio.DBusCallFlags.NONE, -1, None, called)
