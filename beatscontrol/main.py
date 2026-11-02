"""Beats Control application and window."""
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk

from . import APP_ID, __version__, audio, autostart, eqconf
from .bluez import Headphones
from .eq import Equalizer
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
        self.step_values = [0, 4, 3, 1]
        self.step_row = Adw.ComboRow(title='Button volume step', subtitle='How far each headphone volume press moves', model=Gtk.StringList.new(['Headphones default, 6%', 'Small, 3%', 'Fine, 2%', 'Very fine, 1%']))
        self.step_row.connect('notify::selected', self.on_step)
        sound.add(self.step_row)
        self.notify_row = Adw.SwitchRow(title='Volume notifications', subtitle='Show the level when the headphone buttons change it')
        self.notify_row.connect('notify::active', self.on_setting, 'volume_notify')
        sound.add(self.notify_row)
        self.mode_row = Adw.ComboRow(title='Audio mode', subtitle='These headphones support only AAC and SBC. Calls mode enables the microphone but lowers quality', model=Gtk.StringList.new(['Music: AAC', 'Music: SBC-XQ', 'Calls']))
        self.mode_row.connect('notify::selected', self.on_mode)
        sound.add(self.mode_row)
        page.add(sound)

        equalizer = Adw.PreferencesGroup(title='Equalizer', description='Runs on this computer, only while enabled. Calls mode bypasses it')
        self.eq_row = Adw.SwitchRow(title='Enable equalizer')
        self.eq_row.connect('notify::active', self.on_eq_enabled)
        equalizer.add(self.eq_row)
        self.preset_names = list(eqconf.PRESETS) + [eqconf.CUSTOM]
        self.preset_row = Adw.ComboRow(title='Preset', model=Gtk.StringList.new(self.preset_names))
        self.preset_row.connect('notify::selected', self.on_preset)
        equalizer.add(self.preset_row)
        self.bypass_row = Adw.SwitchRow(title='Bypass EasyEffects while on', subtitle='Stops two equalizers stacking. Needs an optional permission, see the README')
        self.bypass_row.connect('notify::active', self.on_setting, 'eq_bypass_easyeffects')
        equalizer.add(self.bypass_row)
        self.level_row = Adw.ActionRow(title='Output level', subtitle='Only changes with presets or this slider. Lower it if boosted bands distort')
        self.level_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -12, 0, 0.1)
        self.level_scale.set_digits(1)
        self.level_scale.set_hexpand(True)
        self.level_scale.set_size_request(170, -1)
        self.level_scale.set_draw_value(True)
        self.level_scale.connect('value-changed', self.on_level)
        self.no_wheel(self.level_scale)
        self.level_row.add_suffix(self.level_scale)
        equalizer.add(self.level_row)
        bands = Gtk.Box(spacing=6, margin_top=10, margin_bottom=10, margin_start=8, margin_end=8)
        self.band_scales = []
        for index, label in enumerate(eqconf.LABELS):
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            # One shared value, so the slider and the number box can never disagree.
            adjustment = Gtk.Adjustment(lower=-eqconf.MAX_GAIN, upper=eqconf.MAX_GAIN, step_increment=0.1, page_increment=1.0)
            adjustment.connect('value-changed', self.on_band, index)
            scale = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=adjustment, digits=1, has_origin=False, draw_value=False, inverted=True)
            scale.set_round_digits(1)
            scale.set_size_request(46, 260)
            scale.set_halign(Gtk.Align.CENTER)
            scale.add_mark(0, Gtk.PositionType.RIGHT, None)
            self.no_wheel(scale)
            entry = Gtk.SpinButton(adjustment=adjustment, digits=1, numeric=True, orientation=Gtk.Orientation.VERTICAL)
            entry.set_tooltip_text(f'{eqconf.FREQUENCIES[index]:g} Hz gain in dB')
            entry.set_update_policy(Gtk.SpinButtonUpdatePolicy.IF_VALID)
            self.no_wheel(entry)
            self.band_scales.append(adjustment)
            column.append(scale)
            column.append(Gtk.Label(label=label, css_classes=['caption']))
            column.append(entry)
            bands.append(column)
        scroller = Gtk.ScrolledWindow(child=bands, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.band_scroller = scroller
        band_row = Gtk.ListBoxRow(activatable=False, selectable=False, child=scroller)
        equalizer.add(band_row)
        page.add(equalizer)

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

        battery = Adw.PreferencesGroup(title='Battery', description='Noise cancelling is the biggest drain: up to 22 hours with it on, up to 40 with it off')
        self.saver_row = Adw.SwitchRow(title='Battery saver', subtitle='Turn noise cancelling off at 30% or below')
        self.saver_row.connect('notify::active', self.on_setting, 'battery_saver')
        battery.add(self.saver_row)
        self.idle_values = [0, 15, 30, 60]
        self.idle_row = Adw.ComboRow(title='Disconnect when idle', subtitle='After this long without audio, while this app is running', model=Gtk.StringList.new(['Never', '15 minutes', '30 minutes', '1 hour']))
        self.idle_row.connect('notify::selected', self.on_idle)
        battery.add(self.idle_row)
        page.add(battery)

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

    def no_wheel(self, scale):
        """Stop the mouse wheel changing a slider while scrolling past it."""
        controller = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES)
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect('scroll', lambda *_: True)
        scale.add_controller(controller)

    def apply_settings(self):
        self.updating = True
        settings = self.app.settings
        self.autostart_row.set_active(settings['autostart'])
        self.background_row.set_active(settings['background'])
        self.restore_row.set_active(settings['restore_anc'])
        self.alert_row.set_active(settings['low_battery_alert'])
        step = settings['volume_step']
        self.step_row.set_selected(self.step_values.index(step) if step in self.step_values else 1)
        self.notify_row.set_active(settings['volume_notify'])
        self.eq_row.set_active(settings['eq_enabled'])
        self.bypass_row.set_active(settings['eq_bypass_easyeffects'])
        name = settings['eq_preset'] if settings['eq_preset'] in self.preset_names else eqconf.CUSTOM
        self.preset_row.set_selected(self.preset_names.index(name))
        for scale, gain in zip(self.band_scales, self.app.gains()):
            scale.set_value(gain)
        self.level_scale.set_value(settings['eq_level'])
        self.saver_row.set_active(settings['battery_saver'])
        minutes = settings['idle_minutes']
        self.idle_row.set_selected(self.idle_values.index(minutes) if minutes in self.idle_values else 0)
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
        self.volume_row.set_sensitive(h.connected and h.volume is not None)
        if h.volume is not None and not self.volume_source:
            self.volume_scale.set_value(audio.percent(h.volume))
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
        if self.app.mode_busy:
            # This reading may predate the switch, and would undo the user's choice on screen.
            return
        self.updating = True
        if profile:
            self.mode_row.set_selected(2 if profile.startswith('headset') else (1 if 'sbc' in profile else 0))
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
        self.app.headphones.set_volume(round(self.volume_scale.get_value() * 127 / 100))
        return GLib.SOURCE_REMOVE

    def on_mode(self, row, _param):
        if not self.updating:
            self.app.set_mode(audio.MODES[row.get_selected()])

    def on_step(self, row, _param):
        if not self.updating:
            self.app.settings['volume_step'] = self.step_values[row.get_selected()]

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

    def on_eq_enabled(self, row, _param):
        if not self.updating:
            self.app.set_eq(row.get_active())

    def on_preset(self, row, _param):
        if self.updating:
            return
        name = self.preset_names[row.get_selected()]
        self.app.settings['eq_preset'] = name
        if name != eqconf.CUSTOM:
            gains = [float(g) for g in eqconf.PRESETS[name]]
            level = eqconf.preset_level(gains)
            self.updating = True
            for scale, gain in zip(self.band_scales, gains):
                scale.set_value(gain)
            self.level_scale.set_value(level)
            self.updating = False
            self.app.settings['eq_level'] = level
            self.app.set_gains(gains)

    def on_level(self, scale):
        if not self.updating:
            self.app.settings['eq_level'] = scale.get_value()
            self.app.set_gains([s.get_value() for s in self.band_scales])

    def on_band(self, _scale, _index):
        if self.updating:
            return
        self.app.settings['eq_preset'] = eqconf.CUSTOM
        self.updating = True
        self.preset_row.set_selected(self.preset_names.index(eqconf.CUSTOM))
        self.updating = False
        self.app.set_gains([s.get_value() for s in self.band_scales])

    def on_idle(self, row, _param):
        if not self.updating:
            self.app.settings['idle_minutes'] = self.idle_values[row.get_selected()]
            self.app.watch_idle()

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
        self.add_main_option('eq', 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING, 'Turn the equalizer on or off', 'on|off')
        self.add_main_option('mode', 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING, 'Set the audio mode', 'aac|sbc-xq|calls')
        self.add_main_option('status', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Print current status', None)
        self.add_main_option('quit', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Quit the running app', None)
        self.add_main_option('version', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Print version', None)
        self.window = None
        self.tray = None
        self.applied = False
        self.alerted = False
        self.saved = False
        self.audio_checked = False
        self.mode_busy = False
        self.calls = False
        self.idle_source = 0
        self.idle_count = 0

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.settings = Settings()
        self.headphones = Headphones()
        self.headphones.connect('changed', self.on_changed)
        self.headphones.connect('volume-pressed', self.on_volume_pressed)
        connection = self.get_dbus_connection()
        self.eq = Equalizer(connection, self.eq_failed)
        self.tray = Tray(connection, self.show_window, self.toggle_anc, self.quit)
        connection.register_object(CLI_PATH, Gio.DBusNodeInfo.new_for_xml(CLI_XML).interfaces[0], self.on_cli)
        self.hold()

    def do_shutdown(self):
        self.eq.shutdown()
        self.headphones.shutdown()
        Adw.Application.do_shutdown(self)

    def do_handle_local_options(self, options):
        if options.contains('version'):
            print(f'Beats Control {__version__}')
            return 0
        command = 'status' if options.contains('status') else None
        if options.contains('anc'):
            command = options.lookup_value('anc').get_string()
        if options.contains('eq'):
            command = 'eq-' + options.lookup_value('eq').get_string()
        if options.contains('mode'):
            command = 'mode-' + options.lookup_value('mode').get_string()
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
        modes = {'mode-aac': audio.AAC, 'mode-sbc-xq': audio.SBC_XQ, 'mode-calls': audio.CALLS}
        if command in modes:
            if self.window:
                # Same path as the dropdown, so this also exercises the window's state.
                self.window.mode_row.set_selected(audio.MODES.index(modes[command]))
            else:
                self.set_mode(modes[command])
            return 0, ''
        if command in ('eq-on', 'eq-off'):
            self.set_eq(command == 'eq-on')
            if self.window:
                self.window.apply_settings()
            return 0, ''
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
        elif 'eq' in options:
            self.command_when_ready(command_line, 'eq-' + options['eq'])
        elif 'mode' in options:
            self.command_when_ready(command_line, 'mode-' + options['mode'])
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
                f'battery: {h.battery}\ncharging: {h.charging}\nfirmware: {h.firmware}\n'
                f"equalizer: {'on' if self.eq.active else 'off'}\nvolume: {h.volume}\n"
                f"mode_shown: {audio.MODES[self.window.mode_row.get_selected()] if self.window else 'no window'}\n")

    def set_eq(self, enabled):
        self.settings['eq_enabled'] = enabled
        self.refresh_eq()

    def gains(self):
        saved = self.settings['eq_gains']
        return saved if len(saved) == eqconf.BANDS else list(eqconf.PRESETS[self.settings['eq_preset']])

    def set_gains(self, gains):
        self.settings['eq_gains'] = [float(g) for g in gains]
        self.eq.update(gains, self.settings['eq_level'])

    def refresh_eq(self):
        h = self.headphones
        wanted = self.settings['eq_enabled'] and h.connected and h.control_ready and not self.mode_busy and not self.calls
        self.eq.bypass_easyeffects = self.settings['eq_bypass_easyeffects']
        self.eq.sync(wanted, h.address, self.gains(), self.settings['eq_level'])
        if not wanted and h.connected and h.control_ready and not self.mode_busy:
            self.eq.repair(h.address)

    def set_mode(self, profile):
        """Change audio mode with the EQ stopped, because the switch replaces the audio output."""
        if self.mode_busy:
            return
        self.mode_busy = True
        if profile != audio.CALLS:
            self.settings['audio_mode'] = profile
        self.refresh_eq()

        def switch():
            if self.eq.active or self.eq.busy:
                return GLib.SOURCE_CONTINUE
            self.calls = profile == audio.CALLS
            audio.set_profile(self.headphones.address, profile, finished)
            return GLib.SOURCE_REMOVE

        def finished(result):
            if result is None and self.window:
                self.window.toast('Could not change audio mode')
            GLib.timeout_add(1500, settle)

        def settle():
            self.mode_busy = False
            self.refresh_eq()
            if self.window:
                self.window.refresh()
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(200, switch)

    def on_volume_pressed(self, h, old, value):
        step = self.settings['volume_step']
        if step and abs(value - old) > step:
            h.set_volume(old + (step if value > old else -step))
        if self.settings['volume_notify'] and h.volume is not None:
            notice = Gio.Notification.new(f'Beats volume {audio.percent(h.volume)}%')
            notice.set_priority(Gio.NotificationPriority.LOW)
            self.send_notification('volume', notice)

    def check_audio(self, _volume, _muted, profile):
        """A failed Bluetooth transport can leave the card off, with no audio output."""
        self.calls = bool(profile) and profile.startswith('headset')
        chosen = self.settings['audio_mode'] or audio.AAC
        if profile == 'off' or (not self.calls and profile != chosen):
            # Linux can bring the headphones back on its default codec.
            self.set_mode(chosen)

    def eq_failed(self):
        if self.window:
            self.window.toast('Could not start the equalizer')

    def watch_idle(self):
        """Check for playback once a minute, only when idle disconnect is enabled."""
        minutes = self.settings['idle_minutes']
        if minutes and self.headphones.connected and not self.idle_source:
            self.idle_count = 0
            self.idle_source = GLib.timeout_add_seconds(60, self.idle_tick)
        elif (not minutes or not self.headphones.connected) and self.idle_source:
            GLib.source_remove(self.idle_source)
            self.idle_source = 0

    def idle_tick(self):
        def check(playing):
            self.idle_count = 0 if playing else self.idle_count + 1
            if self.idle_count >= self.settings['idle_minutes'] > 0:
                self.idle_count = 0
                self.headphones.disconnect_device()
        audio.is_playing(self.headphones.address, check)
        return GLib.SOURCE_CONTINUE

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
            save = h.battery <= self.settings['battery_saver_level'] and not h.charging
            if save and not self.saved and self.settings['battery_saver'] and h.anc:
                h.set_anc(False)
            self.saved = save
        if h.control_ready and not self.audio_checked:
            self.audio_checked = True
            audio.read_state(h.address, self.check_audio)
        elif not h.connected:
            self.audio_checked = False
        self.refresh_eq()
        self.watch_idle()
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
