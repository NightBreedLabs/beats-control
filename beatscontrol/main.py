"""Beats Control application and window."""
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk

from . import APP_ID, __version__, audio, autostart
from .bluez import Headphones
from .settings import Settings
from .tray import Tray


CLI_PATH = '/com/nightbreedlabs/BeatsControl/cli'
CLI_IFACE = 'com.nightbreedlabs.BeatsControl.Cli'
CLI_XML = f'''<node><interface name="{CLI_IFACE}"><method name="Run">
<arg type="s" direction="in"/><arg type="i" direction="out"/><arg type="s" direction="out"/>
</method></interface></node>'''


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Beats Control', default_width=460, default_height=760)
        self.app = app
        self.updating = False
        self.volume_source = 0
        page = Adw.PreferencesPage()

        hero = Adw.PreferencesGroup()
        self.device_row = Adw.ActionRow()
        self.device_icon = Gtk.Image(icon_name='audio-headphones-symbolic', pixel_size=32)
        self.device_row.add_prefix(self.device_icon)
        self.connect_button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.connect_button.connect('clicked', self.on_connect_clicked)
        self.device_row.add_suffix(self.connect_button)
        hero.add(self.device_row)
        self.battery_row = Adw.ActionRow(title='Battery')
        self.battery_bar = Gtk.LevelBar(min_value=0, max_value=100, valign=Gtk.Align.CENTER, hexpand=True)
        self.battery_bar.set_size_request(150, -1)
        self.battery_row.add_suffix(self.battery_bar)
        hero.add(self.battery_row)
        page.add(hero)

        sound = Adw.PreferencesGroup(title='Sound')
        self.anc_row = Adw.SwitchRow(title='Noise cancelling', subtitle='Pure ANC')
        self.anc_row.connect('notify::active', self.on_anc)
        sound.add(self.anc_row)
        self.volume_row = Adw.ActionRow(title='Volume')
        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume_scale.set_hexpand(True)
        self.volume_scale.set_size_request(190, -1)
        self.volume_scale.connect('value-changed', self.on_volume)
        self.volume_row.add_suffix(self.volume_scale)
        sound.add(self.volume_row)
        self.mode_row = Adw.ComboRow(title='Audio mode', subtitle='The microphone needs Calls mode, which lowers sound quality', model=Gtk.StringList.new(['Music', 'Calls']))
        self.mode_row.connect('notify::selected', self.on_mode)
        sound.add(self.mode_row)
        page.add(sound)

        behaviour = Adw.PreferencesGroup(title='App')
        self.autostart_row = Adw.SwitchRow(title='Start at login', subtitle='Opens hidden in the tray')
        self.autostart_row.connect('notify::active', self.on_autostart)
        behaviour.add(self.autostart_row)
        self.background_row = Adw.SwitchRow(title='Run in background', subtitle='Stay in the tray when this window closes')
        self.background_row.connect('notify::active', self.on_setting, 'background')
        behaviour.add(self.background_row)
        self.restore_row = Adw.SwitchRow(title='Restore noise cancelling choice', subtitle='The headphones turn it on at power-on. This applies your last choice when they connect')
        self.restore_row.connect('notify::active', self.on_setting, 'restore_anc')
        behaviour.add(self.restore_row)
        self.alert_row = Adw.SwitchRow(title='Low battery alert', subtitle='Notify at 20% or below')
        self.alert_row.connect('notify::active', self.on_setting, 'low_battery_alert')
        behaviour.add(self.alert_row)
        page.add(behaviour)

        about = Adw.PreferencesGroup(title='Device')
        self.name_row = Adw.EntryRow(title='Name on this computer', show_apply_button=True)
        self.name_row.connect('apply', self.on_rename)
        about.add(self.name_row)
        self.model_row = Adw.ActionRow(title='Model', subtitle='Beats Studio3 Wireless', css_classes=['property'])
        about.add(self.model_row)
        self.firmware_row = Adw.ActionRow(title='Firmware code', css_classes=['property'])
        about.add(self.firmware_row)
        self.address_row = Adw.ActionRow(title='Bluetooth address', css_classes=['property'], subtitle_selectable=True)
        about.add(self.address_row)
        page.add(about)

        content = Adw.ToolbarView()
        content.add_top_bar(Adw.HeaderBar())
        self.toasts = Adw.ToastOverlay(child=page)
        content.set_content(self.toasts)
        self.set_content(content)
        self.connect('close-request', self.on_close)
        self.apply_settings()
        self.changed_id = self.app.headphones.connect('changed', lambda *_: self.refresh())
        self.refresh()

    def apply_settings(self):
        self.updating = True
        settings = self.app.settings
        self.autostart_row.set_active(settings['autostart'])
        self.background_row.set_active(settings['background'])
        self.restore_row.set_active(settings['restore_anc'])
        self.alert_row.set_active(settings['low_battery_alert'])
        self.updating = False

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text))

    def refresh(self):
        h = self.app.headphones
        self.updating = True
        self.device_row.set_title(GLib.markup_escape_text(h.name))
        if not h.found:
            status = h.error or 'Pair the headphones in Bluetooth settings first'
        elif not h.connected:
            status = 'Not connected'
        elif h.control_ready:
            status = 'Connected'
        else:
            status = 'Connected, opening controls'
        self.device_row.set_subtitle(GLib.markup_escape_text(status))
        self.connect_button.set_visible(h.found)
        self.connect_button.set_label('Disconnect' if h.connected else 'Connect')
        self.battery_row.set_visible(h.battery is not None and h.connected)
        if h.battery is not None:
            self.battery_bar.set_value(h.battery)
            self.battery_row.set_subtitle(f'{h.battery}%' + (', charging' if h.charging else ''))
        has_anc = h.control_ready and h.anc is not None
        self.anc_row.set_sensitive(has_anc)
        if has_anc:
            self.anc_row.set_active(h.anc)
        self.volume_row.set_sensitive(h.connected)
        self.mode_row.set_sensitive(h.connected)
        if not self.name_row.get_text() or not self.name_row.has_focus():
            self.name_row.set_text(h.name if h.found else '')
        self.name_row.set_sensitive(h.found)
        self.firmware_row.set_subtitle(h.firmware or 'Unknown')
        self.address_row.set_subtitle(h.address or 'Unknown')
        self.updating = False
        if h.connected and h.address:
            audio.read_state(h.address, self.show_audio)

    def show_audio(self, volume, _muted, profile):
        self.updating = True
        if volume is not None and not self.volume_source:
            self.volume_scale.set_value(volume)
        if profile:
            self.mode_row.set_selected(1 if profile.startswith('headset') else 0)
        self.updating = False

    def on_connect_clicked(self, _button):
        h = self.app.headphones
        action = h.disconnect_device if h.connected else h.connect_device
        action(lambda error: error and self.toast('Could not reach the headphones. Check they are on and nearby'))

    def on_anc(self, row, _param):
        if self.updating:
            return
        self.app.set_anc(row.get_active())

    def on_volume(self, scale):
        if self.updating:
            return
        if self.volume_source:
            GLib.source_remove(self.volume_source)
        self.volume_source = GLib.timeout_add(120, self.apply_volume)

    def apply_volume(self):
        self.volume_source = 0
        audio.set_volume(self.app.headphones.address, self.volume_scale.get_value())
        return GLib.SOURCE_REMOVE

    def on_mode(self, row, _param):
        if self.updating:
            return

        def done(result):
            if result is None:
                self.toast('Could not change audio mode')
        audio.set_profile(self.app.headphones.address, audio.CALLS if row.get_selected() else audio.MUSIC, done)

    def on_setting(self, row, _param, key):
        if not self.updating:
            self.app.settings[key] = row.get_active()

    def on_autostart(self, row, _param):
        if self.updating:
            return
        wanted = row.get_active()

        def done(granted, message):
            if granted:
                self.app.settings['autostart'] = wanted
            else:
                self.updating = True
                row.set_active(self.app.settings['autostart'])
                self.updating = False
                self.toast(message or 'Could not change start at login')
        autostart.request(self.app.get_dbus_connection(), wanted, done)

    def on_rename(self, row):
        text = row.get_text().strip()
        if text:
            self.app.headphones.rename(text)

    def on_close(self, _window):
        if self.app.settings['background']:
            # Free the window's memory while the app waits in the tray.
            self.app.headphones.disconnect(self.changed_id)
            self.app.window = None
            return False
        self.app.quit()
        return True


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option('background', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Start hidden in the tray', None)
        self.add_main_option('anc', 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING, 'Set noise cancelling', 'on|off|toggle')
        self.add_main_option('status', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Print current status', None)
        self.add_main_option('quit', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Quit the running app', None)
        self.add_main_option('version', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Print version', None)
        self.window = None
        self.tray = None
        self.applied = False
        self.alerted = False

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.settings = Settings()
        self.headphones = Headphones()
        self.headphones.connect('changed', self.on_changed)
        connection = self.get_dbus_connection()
        self.tray = Tray(connection, self.show_window, self.toggle_anc, self.quit)
        connection.register_object(CLI_PATH, Gio.DBusNodeInfo.new_for_xml(CLI_XML).interfaces[0], self.on_cli)
        self.hold()

    def do_shutdown(self):
        self.headphones.shutdown()
        Adw.Application.do_shutdown(self)

    def do_handle_local_options(self, options):
        if options.contains('version'):
            print(f'Beats Control {__version__}')
            return 0
        command = 'status' if options.contains('status') else None
        if options.contains('anc'):
            command = options.lookup_value('anc').get_string()
        if command is None:
            return -1
        # A running copy cannot print into another sandbox, so ask it over D-Bus.
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        owner = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'NameHasOwner', GLib.Variant('(s)', (APP_ID,)), None, Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
        if not owner:
            return -1
        code, text = bus.call_sync(APP_ID, CLI_PATH, CLI_IFACE, 'Run', GLib.Variant('(s)', (command,)), None, Gio.DBusCallFlags.NONE, 5000, None).unpack()
        print(text, file=sys.stderr if code else sys.stdout, end='')
        return code

    def on_cli(self, _bus, _sender, _path, _iface, _method, params, invocation):
        code, text = self.cli(params.unpack()[0])
        invocation.return_value(GLib.Variant('(is)', (code, text)))

    def cli(self, command):
        if command == 'status':
            return 0, self.status_text()
        h = self.headphones
        wanted = {'on': True, 'off': False, 'toggle': None if h.anc is None else not h.anc}.get(command)
        if wanted is None or not self.set_anc(wanted):
            return 1, 'Could not set noise cancelling\n'
        return 0, ''

    def do_command_line(self, command_line):
        options = command_line.get_options_dict().end().unpack()
        if options.get('quit'):
            self.quit()
        elif options.get('status'):
            self.command_when_ready(command_line, 'status')
        elif 'anc' in options:
            self.command_when_ready(command_line, options['anc'])
        elif options.get('background'):
            if not self.settings['background']:
                self.show_window()
        else:
            self.show_window()
        return 0

    def command_when_ready(self, command_line, command):
        """Wait briefly for live headphone state, then answer while the caller is attached."""
        h = self.headphones
        started = GLib.get_monotonic_time()
        context = GLib.MainContext.default()
        while not (h.control_ready and h.anc is not None and h.battery is not None):
            elapsed = (GLib.get_monotonic_time() - started) / 1000000
            if elapsed > 15 or (elapsed > 2 and h.found and not h.connected):
                break
            wake = GLib.timeout_add(100, lambda: GLib.SOURCE_REMOVE)
            context.iteration(True)
            GLib.source_remove(wake) if context.find_source_by_id(wake) else None
        code, text = self.cli(command)
        (command_line.printerr_literal if code else command_line.print_literal)(text)
        command_line.set_exit_status(code)
        if not self.get_windows():
            # This copy was started only for this command. Running copies answer over D-Bus.
            GLib.idle_add(self.quit)

    def status_text(self):
        h = self.headphones
        anc = 'unknown' if h.anc is None else ('on' if h.anc else 'off')
        return (f'name: {h.name}\nconnected: {h.connected}\ncontrol: {h.control_ready}\nnoise_cancelling: {anc}\n'
                f'battery: {h.battery}\ncharging: {h.charging}\nfirmware: {h.firmware}\n')

    def set_anc(self, enabled):
        self.settings['preferred_anc'] = enabled
        return self.headphones.set_anc(enabled)

    def toggle_anc(self):
        if self.headphones.anc is not None:
            self.set_anc(not self.headphones.anc)

    def show_window(self):
        if not self.window:
            self.window = Window(self)
        self.window.set_visible(True)
        self.window.present()

    def on_changed(self, h):
        if not h.control_ready:
            self.applied = False
        elif h.anc is not None and not self.applied:
            self.applied = True
            if self.settings['restore_anc'] and h.anc != self.settings['preferred_anc']:
                h.set_anc(self.settings['preferred_anc'])
        if h.battery is not None:
            low = h.battery <= self.settings['low_battery_level'] and not h.charging
            if low and not self.alerted and self.settings['low_battery_alert'] and h.connected:
                notice = Gio.Notification.new('Beats battery is low')
                notice.set_body(f'{h.battery}% remaining')
                self.send_notification('low-battery', notice)
            self.alerted = low
        title = h.name
        if h.connected and h.battery is not None:
            title = f'{h.name}: {h.battery}%'
        elif not h.connected:
            title = f'{h.name}: not connected'
        if h.anc is None:
            label = 'Noise cancelling: unavailable'
        else:
            label = f"Noise cancelling: {'on' if h.anc else 'off'}"
        self.tray.update(title, label)


def main():
    return App().run(sys.argv)
