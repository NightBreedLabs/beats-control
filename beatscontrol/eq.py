"""Runs the EQ as a private PipeWire process, only while it is enabled."""
import json
from pathlib import Path

from gi.repository import Gio, GLib

from . import eqconf

SYSTEMD = 'org.freedesktop.systemd1'
MANAGER = 'org.freedesktop.systemd1.Manager'
SYSTEMD_PATH = '/org/freedesktop/systemd1'
EASYEFFECTS_OUT = 'ee_soe_output_level:output_'
CHANNELS = ('FL', 'FR')


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

    def __init__(self, connection, on_failed):
        self.bus = connection
        self.on_failed = on_failed
        self.path = Path(GLib.get_user_config_dir()) / 'beats-control' / 'eq.conf'
        self.process = None
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
        self.bypass_easyeffects = True
        self.can_bypass = False
        self.easyeffects_linked = False
        self.settle_source = 0
        self.settle_count = 0
        self.repaired = False
        self._probe_session()

    def _probe_session(self):
        """EasyEffects bypass needs an optional permission, so find out if it was granted."""
        def finish(bus, result):
            try:
                bus.call_finish(result)
                self.can_bypass = True
            except GLib.Error:
                self.can_bypass = False
        self.bus.call(SYSTEMD, SYSTEMD_PATH, 'org.freedesktop.DBus.Peer', 'Ping', None, None, Gio.DBusCallFlags.NONE, 2000, None, finish)

    def _sinks(self, done):
        _run(['pactl', '--format=json', 'list', 'sinks'], lambda text: done(json.loads(text or '[]')))

    def _session_command(self, arguments, done):
        """Run one host command in the user session. Needs the optional systemd permission."""
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
            running = any(s.get('name') == 'easyeffects_sink' for s in sinks)
            if self.can_bypass and self.bypass_easyeffects and running:
                self._session_command(['/usr/bin/flatpak', 'run', '--command=easyeffects', 'com.github.wwmm.easyeffects', '-b', '1' if enabled else '2'], done)
            else:
                done()
        self._sinks(check)

    def _route_easyeffects(self, into_eq, done):
        """EasyEffects makes its own links, so PipeWire cannot place the EQ after it automatically."""
        def ports(text):
            if EASYEFFECTS_OUT + 'FL' not in (text or ''):
                self.easyeffects_linked = False
                done()
                return
            commands = []
            for channel in CHANNELS:
                source = EASYEFFECTS_OUT + channel
                old, new = f'{self.output}:playback_{channel}', f'{eqconf.SINK_NAME}:playback_{channel}'
                remove, add = (old, new) if into_eq else (new, old)
                commands += [['pw-link', '-d', source, remove], ['pw-link', source, add]]
            self.easyeffects_linked = into_eq
            self._run_all(commands, done)
        _run(['pw-link', '-o'], ports)

    def _run_all(self, commands, done):
        if not commands:
            done()
            return
        _run(commands[0], lambda _r: self._run_all(commands[1:], done))

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
        try:
            self.process = Gio.Subprocess.new(['pipewire', '-c', str(self.path)], Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error:
            self._failed()
            return
        self._wait(20)

    def _wait(self, left):
        def check(sinks):
            if any(s.get('name') == eqconf.SINK_NAME for s in sinks):
                self.active, self.tries = True, 0
                self._unity()
                self._easyeffects_bypass(True, lambda: self._route_easyeffects(True, self._settled))
            elif left:
                GLib.timeout_add(250, lambda: self._wait(left - 1) or GLib.SOURCE_REMOVE)
            else:
                self._kill()
                self._failed()
        self._sinks(check)

    def _unity(self):
        """Volume belongs to the headphones. Any cut on this sink is lost resolution."""
        _run(['pactl', 'set-sink-mute', eqconf.SINK_NAME, '0'])
        _run(['pactl', 'set-sink-volume', eqconf.SINK_NAME, '100%'])

    def _settled(self):
        self.settle_count = 2
        self.settle_source = GLib.timeout_add_seconds(3, self._settle)
        self._finish()

    def _settle(self):
        """EasyEffects can relink itself and a slower bypass command can land late, so re-apply both."""
        self.settle_count -= 1
        if not self.active or self.busy:
            self.settle_source = 0
            return GLib.SOURCE_REMOVE
        self._unity()
        self._easyeffects_bypass(True, lambda: self._route_easyeffects(True, lambda: None))
        if self.settle_count > 0:
            return GLib.SOURCE_CONTINUE
        self.settle_source = 0
        return GLib.SOURCE_REMOVE

    def repair(self, address):
        """After a crash, EasyEffects can stay bypassed or lose its output. Restore both once."""
        if self.repaired or self.active or self.busy or self.want:
            return
        self.repaired = True
        key = address.replace(':', '_')

        def check(attempts):
            def linked(text):
                # pw-link -l lists only linked ports, so a port with no output is simply absent.
                if EASYEFFECTS_OUT + 'FL' not in (text or '').splitlines():
                    _run(['pw-link', '-o'], ports)
                elif attempts:
                    GLib.timeout_add(3000, lambda: check(attempts - 1) or GLib.SOURCE_REMOVE)

            def ports(text):
                if EASYEFFECTS_OUT + 'FL' in (text or '').splitlines():
                    self._sinks(reconnect)

            def reconnect(sinks):
                output = next((s['name'] for s in sinks if key in s.get('name', '') and s['name'].startswith('bluez_output')), None)
                if output and not self.active:
                    self._run_all([['pw-link', EASYEFFECTS_OUT + c, f'{output}:playback_{c}'] for c in CHANNELS], lambda: None)
                if attempts:
                    GLib.timeout_add(3000, lambda: check(attempts - 1) or GLib.SOURCE_REMOVE)
            _run(['pw-link', '-l'], linked)

        # EasyEffects rebuilds its links when bypass changes, so check after it settles.
        self._easyeffects_bypass(False, lambda: GLib.timeout_add(2500, lambda: check(2) or GLib.SOURCE_REMOVE))

    def _kill(self):
        if self.process:
            self.process.force_exit()
            self.process = None

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

    def _stop(self):
        self.active = False
        if self.settle_source:
            GLib.source_remove(self.settle_source)
            self.settle_source = 0

        def stop():
            self._kill()
            self._finish()
        self._route_easyeffects(False, lambda: self._easyeffects_bypass(False, stop))

    def shutdown(self):
        """Blocking cleanup for app exit."""
        if self.active and self.easyeffects_linked:
            for channel in CHANNELS:
                source = EASYEFFECTS_OUT + channel
                for command in (['pw-link', '-d', source, f'{eqconf.SINK_NAME}:playback_{channel}'], ['pw-link', source, f'{self.output}:playback_{channel}']):
                    try:
                        Gio.Subprocess.new(command, Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE).wait(None)
                    except GLib.Error:
                        pass
        if self.active and self.can_bypass and self.bypass_easyeffects:
            done = GLib.MainLoop()
            self._session_command(['/usr/bin/flatpak', 'run', '--command=easyeffects', 'com.github.wwmm.easyeffects', '-b', '2'], done.quit)
            GLib.timeout_add(1500, done.quit)
            done.run()
        self.active = False
        self._kill()

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
