"""Resumes media players that a mode change paused."""
from gi.repository import Gio, GLib

PREFIX = 'org.mpris.MediaPlayer2.'
PLAYER = 'org.mpris.MediaPlayer2.Player'
PATH = '/org/mpris/MediaPlayer2'


def _status(bus, name, done):
    def finish(connection, result):
        try:
            done(connection.call_finish(result).unpack()[0])
        except GLib.Error:
            done(None)
    bus.call(name, PATH, 'org.freedesktop.DBus.Properties', 'Get', GLib.Variant('(ss)', (PLAYER, 'PlaybackStatus')), None, Gio.DBusCallFlags.NONE, 1000, None, finish)


def playing(bus, done):
    """Call done(names of players that are playing now)."""
    def listed(connection, result):
        try:
            names = [n for n in connection.call_finish(result).unpack()[0] if n.startswith(PREFIX)]
        except GLib.Error:
            names = []
        if not names:
            done([])
            return
        found, left = [], [len(names)]

        def check(name, status):
            if status == 'Playing':
                found.append(name)
            left[0] -= 1
            if not left[0]:
                done(found)
        for name in names:
            _status(bus, name, lambda status, n=name: check(n, status))
    bus.call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'ListNames', None, None, Gio.DBusCallFlags.NONE, 1000, None, listed)


def resume(bus, names):
    """Press play only on players still paused, because some resume by themselves."""
    def press(name, status):
        if status == 'Paused':
            bus.call(name, PATH, PLAYER, 'Play', None, None, Gio.DBusCallFlags.NONE, 1000, None, None)
    for name in names:
        _status(bus, name, lambda status, n=name: press(n, status))
