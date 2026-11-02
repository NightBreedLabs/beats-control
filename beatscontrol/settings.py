"""Small JSON settings store in the app's private config directory."""
import json
import os
from pathlib import Path

from gi.repository import GLib

DEFAULTS = {
    'autostart': False,
    'background': False,
    'restore_anc': False,
    'preferred_anc': True,
    'low_battery_alert': True,
    'low_battery_level': 20,
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

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.values, indent=2))
        os.replace(temp, self.path)
