"""Volume and audio mode for the headphones, through pactl in the sandbox."""
import json

from gi.repository import Gio, GLib

AAC = 'a2dp-sink'
SBC_XQ = 'a2dp-sink-sbc_xq'
CALLS = 'headset-head-unit'
MODES = (AAC, SBC_XQ, CALLS)


def _run(args, done=None):
    try:
        process = Gio.Subprocess.new(['pactl', *args], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
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


def _key(address):
    return address.replace(':', '_')


def read_state(address, done):
    """Call done(volume_percent or None, muted, profile or None), ignoring the EQ sink."""
    key = _key(address)

    def got_cards(cards_text, volume, muted):
        profile = None
        for card in json.loads(cards_text or '[]'):
            if key in card.get('name', ''):
                profile = card.get('active_profile')
        done(volume, muted, profile)

    def got_sinks(text):
        volume, muted = None, False
        for sink in json.loads(text or '[]'):
            if key in sink.get('name', ''):
                channels = sink.get('volume') or {}
                first = next(iter(channels.values()), {})
                volume = int(str(first.get('value_percent', '0')).rstrip('%'))
                muted = sink.get('mute', False)
        _run(['--format=json', 'list', 'cards'], lambda t: got_cards(t, volume, muted))
    _run(['--format=json', 'list', 'sinks'], got_sinks)


def set_volume(address, percent):
    key = _key(address)

    def apply(text):
        for sink in json.loads(text or '[]'):
            if key in sink.get('name', ''):
                _run(['set-sink-volume', sink['name'], f'{int(percent)}%'])
    _run(['--format=json', 'list', 'sinks'], apply)


def set_profile(address, profile, done=None):
    _run(['set-card-profile', f'bluez_card.{_key(address)}', profile], done)


def is_playing(address, done):
    key = _key(address)

    def check(text):
        done(any(key in s.get('name', '') and s.get('state') == 'RUNNING' for s in json.loads(text or '[]')))
    _run(['--format=json', 'list', 'sinks'], check)


def percent(value):
    """The headphones report 0 to 127. PipeWire shows that value as a plain percentage."""
    return round(value * 100 / 127)
