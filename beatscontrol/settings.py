"""Small JSON settings store in the app's private config directory."""
import json
import os
from pathlib import Path

from gi.repository import GLib

from . import eqconf

DEFAULTS = {
    'autostart': False,
    'background': False,
    'restore_anc': False,
    'preferred_anc': True,
    'low_battery_alert': True,
    'low_battery_level': 20,
    'eq_enabled': False,
    'eq_preset': 'Bright',
    'eq_gains': [],
    'eq_level': eqconf.preset_level(eqconf.PRESETS['Bright']),
    'eq_bypass_easyeffects': True,
    'audio_mode': '',
    'volume_step': 4,
    'volume_notify': True,
    'battery_saver': False,
    'battery_saver_level': 30,
    'idle_minutes': 0,
}


class Settings:
    def __init__(self, path=None):
        self.path = Path(path or Path(GLib.get_user_config_dir()) / 'beats-control' / 'settings.json')
        self.values = dict(DEFAULTS)
        try:
            saved = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        if isinstance(saved, dict):
            self.values.update({k: v for k, v in saved.items() if k in DEFAULTS and isinstance(v, type(DEFAULTS[k]))})
            if 'eq_level' not in saved:
                # Before 0.4 the level moved with every slider, and it was not saved.
                self.values['eq_preset'] = DEFAULTS['eq_preset']
                self.values['eq_gains'] = []
                self.values['eq_level'] = DEFAULTS['eq_level']
            name = self.values['eq_preset']
            if name == 'My EasyEffects':
                # That preset was removed. Keep the sound you had selected as a custom curve.
                self.values['eq_preset'] = eqconf.CUSTOM
                self.values['eq_gains'] = self.values['eq_gains'] or list(eqconf.MINE)
            elif name in eqconf.PRESETS:
                # Pick up any retuning of the selected preset.
                self.values['eq_gains'] = list(eqconf.PRESETS[name])
                self.values['eq_level'] = eqconf.preset_level(eqconf.PRESETS[name])
            if len(self.values['eq_gains']) != 32:
                # Earlier versions stored a 10-band layout that cannot map onto this EQ.
                self.values['eq_preset'] = DEFAULTS['eq_preset']
                self.values['eq_gains'] = []
                self.values['eq_level'] = DEFAULTS['eq_level']

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.values, indent=2))
        os.replace(temp, self.path)
