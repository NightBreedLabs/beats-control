"""Runs the EQ in the system filter-chain service, only while it is enabled."""
import json
from pathlib import Path

from gi.repository import Gio, GLib

from . import eqconf

SERVICE = 'filter-chain.service'
SYSTEMD = 'org.freedesktop.systemd1'
MANAGER = 'org.freedesktop.systemd1.Manager'
SYSTEMD_PATH = '/org/freedesktop/systemd1'


def _run(command, done=None):
    try:
        process = Gio.Subprocess.new(command, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
    except GLib.Error:
        if done:
            done(None)
        return

    def finish(proc, result):
        try:
            _ok, out, _err = proc.communicate_utf8_finish(result)
        except GLib.Error:
            out = None
        if done:
            done(out if proc.get_successful() else None)
    process.communicate_utf8_async(None, None, finish)


class Equalizer:
    """One operation runs at a time. Each finished step re-checks what is wanted."""

    MAX_TRIES = 6

    def __init__(self, connection, on_failed, on_volume):
        self.bus = connection
        self.on_failed = on_failed
        self.on_volume = on_volume
        self.path = Path.home() / '.config/pipewire/filter-chain.conf.d/beats-control-eq.conf'
        self.active = False
        self.busy = False
        self.want = False
        self.address = ''
        self.gains = []
        self.level = 0.0
        self.output = None
        self.tries = 0
        self.source = 0
        self.retry = 0
        self.unit_count = 0
        self.watcher = None
        self.watch_source = 0
        self.shown_volume = None
        self.bypass_easyeffects = True

    def _unit(self, method, done):
        def finish(bus, result):
            try:
                bus.call_finish(result)
                done(True)
            except GLib.Error:
                done(False)
        self.bus.call(SYSTEMD, SYSTEMD_PATH, MANAGER, method, GLib.Variant('(ss)', (SERVICE, 'replace')), None, Gio.DBusCallFlags.NONE, 10000, None, finish)

    def _sinks(self, done):
        _run(['pactl', '--format=json', 'list', 'sinks'], lambda text: done(json.loads(text or '[]')))

    def _session_command(self, arguments, done):
        """Run one host command in the user session, which the sandbox cannot do directly."""
        self.unit_count += 1
        command = GLib.Variant('a(sasb)', [(arguments[0], arguments, False)])
        properties = [('ExecStart', command), ('CollectMode', GLib.Variant('s', 'inactive-or-failed'))]
        name = f'beats-control-command-{GLib.get_monotonic_time()}-{self.unit_count}.service'
        call = GLib.Variant('(ssa(sv)a(sa(sv)))', (name, 'replace', properties, []))

        def finish(bus, result):
            try:
                bus.call_finish(result)
            except GLib.Error:
                pass
            GLib.timeout_add(300, lambda: done() or GLib.SOURCE_REMOVE)
        self.bus.call(SYSTEMD, SYSTEMD_PATH, MANAGER, 'StartTransientUnit', call, None, Gio.DBusCallFlags.NONE, 5000, None, finish)

    def _easyeffects_bypass(self, enabled, done):
        """Keep EasyEffects from stacking with this EQ. Skipped unless its service is running."""
        def check(sinks):
            if self.bypass_easyeffects and any(s.get('name') == 'easyeffects_sink' for s in sinks):
                self._session_command(['/usr/bin/flatpak', 'run', '--command=easyeffects', 'com.github.wwmm.easyeffects', '-b', '1' if enabled else '2'], done)
            else:
                done()
        self._sinks(check)

    def _set_default(self, sink, done):
        self._session_command(['/usr/bin/pactl', 'set-default-sink', sink], done)

    def sync(self, want, address, gains, level):
        if want and not self.want:
            self.tries = 0
        self.want, self.address, self.gains, self.level = want, address, list(gains), level
        self._step()

    def _step(self):
        if self.busy or self.retry:
            return
        if self.want and not self.active:
            self.busy = True
            self._sinks(self._start)
        elif not self.want and self.active:
            self.busy = True
            self._stop()

    def _finish(self):
        self.busy = False
        self._step()

    def _start(self, sinks):
        key = self.address.replace(':', '_')
        output = next((s['name'] for s in sinks if key and key in s.get('name', '') and s['name'].startswith('bluez_output')), None)
        if not output or not self.want:
            self._failed()
            return
        self.output = output
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(eqconf.render(self.gains, self.level, output))
        self._unit('RestartUnit', lambda ok: self._wait(20) if ok else self._failed())

    def _wait(self, left):
        def check(sinks):
            if any(s.get('name') == eqconf.SINK_NAME for s in sinks):
                self.active, self.tries = True, 0
                self._watch_volume()
                self._set_default(eqconf.SINK_NAME, lambda: self._easyeffects_bypass(True, self._finish))
            elif left:
                GLib.timeout_add(250, lambda: self._wait(left - 1) or GLib.SOURCE_REMOVE)
            else:
                self._unit('StopUnit', lambda _ok: self._failed())
        self._sinks(check)

    def _failed(self):
        # The Bluetooth output appears a moment after the headphones connect.
        self.busy = False
        self.tries += 1
        if not self.want:
            self._step()
        elif self.tries < self.MAX_TRIES:
            self.retry = GLib.timeout_add_seconds(2, self._retry)
        else:
            self.want = False
            self.on_failed()

    def _retry(self):
        self.retry = 0
        self._step()
        return GLib.SOURCE_REMOVE

    def _watch_volume(self):
        """Follow volume changes on the EQ sink, only while it exists."""
        try:
            self.watcher = Gio.Subprocess.new(['pactl', 'subscribe'], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error:
            return
        stream = Gio.DataInputStream.new(self.watcher.get_stdout_pipe())

        def line(source, result):
            try:
                text, _length = source.read_line_finish_utf8(result)
            except GLib.Error:
                return
            if text is None or not self.watcher:
                return
            if 'on sink #' in text and not self.watch_source:
                self.watch_source = GLib.timeout_add(100, self._read_volume)
            source.read_line_async(GLib.PRIORITY_DEFAULT, None, line)
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, line)

    def _read_volume(self):
        self.watch_source = 0

        def check(sinks):
            for sink in sinks:
                if sink.get('name') == eqconf.SINK_NAME:
                    value = int(str(next(iter(sink['volume'].values()))['value_percent']).rstrip('%'))
                    # Until the real volume has been shown, this sink holds a stale value that
                    # must never reach the headphones.
                    if self.shown_volume is None:
                        return
                    if self.show_pending:
                        self.show_pending = value != self.shown_volume
                    elif value != self.shown_volume:
                        self.shown_volume = value
                        self.on_volume(value)
        self._sinks(check)
        return GLib.SOURCE_REMOVE

    def show_volume(self, value):
        """Show the headphones' real volume on the EQ sink. This does not affect the audio."""
        if self.active and value != self.shown_volume:
            self.shown_volume = value
            self.show_pending = True
            _run(['pactl', 'set-sink-volume', eqconf.SINK_NAME, f'{value}%'])

    def _stop_watch(self):
        if self.watcher:
            self.watcher.force_exit()
            self.watcher = None
        self.shown_volume = None

    def _stop(self):
        self.active = False
        self._stop_watch()
        finish = lambda _ok: self._finish()
        stop = lambda: self._unit('StopUnit', finish)
        restore = (lambda: self._set_default(self.output, stop)) if self.output else stop
        self._easyeffects_bypass(False, restore)

    def shutdown(self):
        """Blocking cleanup for app exit."""
        if not self.active:
            return
        self.active = False
        self._stop_watch()
        try:
            self.bus.call_sync(SYSTEMD, SYSTEMD_PATH, MANAGER, 'StopUnit', GLib.Variant('(ss)', (SERVICE, 'replace')), None, Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error:
            pass

    def update(self, gains, level):
        """Apply gains live, limited to one update per 120 ms while sliders move."""
        self.gains, self.level = list(gains), level
        if self.active and not self.source:
            self.source = GLib.timeout_add(120, self._apply)

    def _apply(self):
        self.source = 0

        def apply(sinks):
            node = next((s for s in sinks if s.get('name') == eqconf.SINK_NAME), None)
            if node:
                self.path.write_text(eqconf.render(self.gains, self.level, self.output))
                _run(['pw-cli', 'set-param', str(node['properties']['object.id']), 'Props', eqconf.props(self.gains, self.level)])
        self._sinks(apply)
        return GLib.SOURCE_REMOVE
