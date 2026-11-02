"""Pure equalizer definitions and PipeWire filter-chain config rendering."""

import math

# EasyEffects' default 32-band layout: third-octave bands with Q 4.36.
FREQUENCIES = (22.4, 27.8, 34.51, 42.82, 53.14, 65.95, 81.83, 101.55, 126.0, 156.38, 194.06, 240.81,
               298.834, 370.834, 460.182, 571.057, 708.647, 879.387, 1091.26, 1354.19, 1680.47, 2085.35,
               2587.79, 3211.29, 3985.01, 4945.15, 6136.63, 7615.17, 9449.96, 11726.8, 14552.2, 18058.4)
LABELS = ('22', '28', '35', '43', '53', '66', '82', '102', '126', '156', '194', '241', '299', '371', '460', '571',
          '709', '879', '1.1k', '1.4k', '1.7k', '2.1k', '2.6k', '3.2k', '4k', '4.9k', '6.1k', '7.6k', '9.4k', '12k', '15k', '18k')
BANDS = len(FREQUENCIES)
MAX_GAIN = 12.0
Q = 4.36
RATE = 48000
SINK_NAME = 'beats_eq'
EASYEFFECTS = {0: 2, 3: 2, 5: 2, 6: 2, 26: 4, 27: 6, 28: 9, 29: 11, 30: 12, 31: 4}


def _shape(points):
    """Interpolate gains on a log-frequency axis between (frequency, dB) points."""
    points = sorted(points)
    values = []
    for frequency in FREQUENCIES:
        if frequency <= points[0][0]:
            values.append(points[0][1])
        elif frequency >= points[-1][0]:
            values.append(points[-1][1])
        else:
            for (f1, g1), (f2, g2) in zip(points, points[1:]):
                if f1 <= frequency <= f2:
                    t = math.log(frequency / f1) / math.log(f2 / f1)
                    values.append(g1 + t * (g2 - g1))
                    break
    return values


def _on_mine(points):
    """A gentle change added to the base curve, which corrects these headphones."""
    return tuple(round(EASYEFFECTS.get(i, 0) + g, 1) for i, g in enumerate(_shape(points)))


# This base curve is used by most presets. It was tuned by ear on a Studio3 for a brighter sound.
MINE = tuple(float(EASYEFFECTS.get(i, 0)) for i in range(BANDS))
PRESETS = {
    'Flat': (0.0,) * BANDS,
    'Warm': _on_mine([(60, 2.5), (250, 1), (800, 0), (6000, -1), (14000, -2)]),
    # A focused lift with a dip around 250 Hz, where bass turns to mud, and a little added air.
    'Deep Bass': _on_mine([(40, 3), (70, 3.5), (110, 2), (170, 0), (250, -2), (400, -1), (700, 0), (5000, 0), (9000, 1), (16000, 1)]),
    'Vocal': _on_mine([(150, -1), (500, 0), (2000, 2), (4000, 2), (8000, 0)]),
    'Bright': _on_mine([(800, 0), (3000, 1.5), (8000, 2)]),
    # The top bands are already near the limit, so this adds the presence and sparkle below them.
    'Treble Boost': _on_mine([(2000, 0), (3500, 1.5), (5000, 3), (7500, 4), (9500, 3), (11000, 2), (18000, 4)]),
    'Late Night': _on_mine([(60, -3), (150, -1), (500, 0), (6000, 0), (14000, -3)]),
}
CUSTOM = 'Custom'


def clamp(gains):
    values = [max(-MAX_GAIN, min(MAX_GAIN, float(g))) for g in gains]
    if len(values) != len(FREQUENCIES):
        raise ValueError('expected one gain per band')
    return values


def _peaking_db(frequency, center, gain):
    """Magnitude in dB of one RBJ peaking biquad."""
    if gain == 0:
        return 0.0
    amp = 10 ** (gain / 40)
    w0 = 2 * math.pi * center / RATE
    alpha = math.sin(w0) / (2 * Q)
    cos0 = math.cos(w0)
    b = (1 + alpha * amp, -2 * cos0, 1 - alpha * amp)
    a = (1 + alpha / amp, -2 * cos0, 1 - alpha / amp)
    w = 2 * math.pi * frequency / RATE
    z1, z2 = complex(math.cos(w), -math.sin(w)), complex(math.cos(2 * w), -math.sin(2 * w))
    return 20 * math.log10(abs((b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2)))


def response(gains, frequency):
    return sum(_peaking_db(frequency, c, g) for c, g in zip(FREQUENCIES, gains))


def _music_level(gains):
    """Level change of a curve on a typical music spectrum, in dB.

    Music energy per third octave falls about 1.5 dB per octave.
    """
    weights = [10 ** (-0.15 * math.log2(f / 1000)) for f in FREQUENCIES]
    power = sum(w * 10 ** (response(gains, f) / 10) for w, f in zip(weights, FREQUENCIES)) / sum(weights)
    return 10 * math.log10(power)


def preset_level(gains):
    """Output level that keeps a preset as loud as the base curve, which plays at 0 dB.

    This is set only when a preset is chosen. Moving a band must never change the other bands.
    """
    return min(0.0, _music_level(MINE) - _music_level(gains))


def props(gains, level):
    """SPA JSON for a live Props update of every gain."""
    values = clamp(gains)
    items = [f'"pre:Gain" {level:.2f}']
    items += [f'"eq{i + 1}:Gain" {g:.2f}' for i, g in enumerate(values)]
    return '{ params = [ ' + ' '.join(items) + ' ] }'


def render(gains, level, target):
    values = clamp(gains)
    nodes = []
    nodes += [f'{{ type = builtin name = pre label = bq_highshelf control = {{ "Freq" = 0 "Q" = 1.0 "Gain" = {level:.2f} }} }}']
    for i, gain in enumerate(values):
        nodes.append(f'{{ type = builtin name = eq{i + 1} label = bq_peaking control = {{ "Freq" = {FREQUENCIES[i]} "Q" = {Q} "Gain" = {gain:.2f} }} }}')
    names = ['pre'] + [f'eq{i + 1}' for i in range(len(values))]
    links = [f'{{ output = "{a}:Out" input = "{b}:In" }}' for a, b in zip(names, names[1:])]
    nl = '\n                '
    return f'''# Written by Beats Control. Changes here are replaced by the app.
context.properties = {{ core.daemon = false core.name = beats-control-eq }}
context.spa-libs = {{
    audio.convert.* = audioconvert/libspa-audioconvert
    support.*       = support/libspa-support
}}
context.modules = [
    {{ name = libpipewire-module-rt flags = [ ifexists nofail ] }}
    {{ name = libpipewire-module-protocol-native }}
    {{ name = libpipewire-module-client-node }}
    {{ name = libpipewire-module-adapter }}
    {{ name = libpipewire-module-filter-chain
        args = {{
            node.description = "Beats EQ"
            media.name = "Beats EQ"
            filter.graph = {{
                nodes = [
                {nl.join(nodes)}
                ]
                links = [
                {nl.join(links)}
                ]
            }}
            audio.channels = 2
            audio.position = [ FL FR ]
            capture.props = {{
                node.name = "{SINK_NAME}"
                media.class = Audio/Sink
                filter.smart = true
                filter.smart.name = "{SINK_NAME}"
                filter.smart.target = {{ node.name = "{target}" }}
            }}
            playback.props = {{
                node.name = "{SINK_NAME}_out"
                node.passive = true
                node.dont-fallback = true
                node.dont-move = true
                target.object = "{target}"
            }}
        }}
    }}
]
'''
