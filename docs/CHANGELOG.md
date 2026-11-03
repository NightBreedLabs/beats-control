# Changelog

## 0.8.0 (unreleased)

- The EQ engine is now inside the app, built from PipeWire source. It runs only while the EQ is on, and no host service is needed.
- A smart filter inserts the EQ, so the default output stays on the headphones and desktop volume is the real volume.
- The systemd permission is gone by default. EasyEffects bypass is an optional override.
- If the app crashes while the EQ is on, reopening it restores EasyEffects' output.
- Fixed the EQ sink staying at a restored 40%, which cut audio by 24 dB with the EQ on.
- Players paused by an audio mode change now resume by themselves.
- Tested on KDE Plasma.
- The README has a stable download link. `docs/FLATHUB.md` lists what remains for Flathub.

## 0.7.0

- First public release, with 32-band EQ, typed dB values, two-way volume sync, smaller button steps, codec and mode selection, and battery options.
