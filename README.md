# Beats Control

Unofficial Linux app for **Beats Studio3 Wireless** headphones, packaged as a Flatpak. It controls noise cancelling, shows live battery, keeps volume in sync, and adds a 32-band equalizer.

> **Made specifically for the Beats Studio3 Wireless.** It has been tested only on one Studio3 (firmware code `0244`) on Bazzite Linux with Niri. It might work with other Beats or Apple headphones, but that has not been tested in any way. The app currently looks only for the Studio3's product ID (`0x2009`), so other models will not be detected without changing the code. Sending these commands to another model could behave differently, so try that at your own risk.

Not affiliated with, endorsed by, or supported by Apple Inc. or Beats Electronics. Beats and Studio3 are trademarks of their owners.

## Features

| Feature | Status |
|---|---|
| Noise cancelling on or off, from the app, tray or command line | Tested on a Studio3 |
| Live battery level | Tested on a Studio3 |
| Volume kept in sync with the headphones and desktop | Tested on a Studio3 |
| Smaller steps for the headphone volume buttons | Tested on a Studio3 |
| 32-band EQ with presets, sliders and typed dB values | Response measured, tested on a Studio3 |
| AAC or SBC-XQ selection | Tested on a Studio3 |
| Music or Calls audio mode | Tested on a Studio3 |
| Connect, disconnect and automatic reconnect of controls | Tested on a Studio3 |
| Run in background, start at login | Tested on Niri |
| Tray icon with menu | Tested over D-Bus on Niri with Noctalia |
| Low battery alert at 20% or below | Not yet triggered |
| Battery saver and idle disconnect | Not yet triggered |
| Charging indicator | Not tested while charging |
| Restoring your noise cancelling choice | Not tested after a power cycle |
| Restoring your codec choice, recovering audio left off | Not tested after a reconnect |
| Name on this computer | Not tested |
| KDE Plasma, GNOME and other desktops | Not tested |

### Equalizer

The EQ runs on your computer, not in the headphones. It uses 32 third-octave bands through PipeWire's `filter-chain.service`, which runs only while the EQ is enabled.

- **Presets:** Flat, Warm, Deep Bass, Vocal, Bright, Treble Boost and Late Night. All except Flat build on a bright base curve tuned by ear on a Studio3.
- **Moving a band changes only that band.** If a large boost distorts, lower **Output level**.
- **EasyEffects:** if the Flatpak version is running, the app bypasses it while the EQ is on so two equalizers do not stack, then turns it back on when the EQ is off. Turn off **Bypass EasyEffects while on** to prevent this.
- Calls mode bypasses the EQ.

### Not available

- **aptX and LDAC:** the headphones advertise only SBC and AAC-LC at up to 256 kbps. See [docs/RESEARCH.md](docs/RESEARCH.md).
- **EQ stored on the headphones:** the official Android app has no EQ feature for this model.
- **Firmware updates:** these need the official Beats app.
- **Serial number:** the headphones do not send device details on the channel this app uses.
- **Transparency mode, ear detection, custom button actions:** not Studio3 features.
- **Renaming stored on the headphones:** only the name on your computer changes.

## Requirements

- Linux with BlueZ, PipeWire with `pipewire-pulse`, and WirePlumber
- Flatpak with `org.gnome.Platform//50` from Flathub
- Beats Studio3 Wireless, already paired in your Bluetooth settings
- PipeWire's `filter-chain.service` as a user service, for the EQ

## Install

There is no Flathub release, so build it from source:

```bash
git clone https://github.com/NightBreedLabs/beats-control.git
cd beats-control
./build.sh
flatpak run com.nightbreedlabs.BeatsControl
```

The SDK is not needed because the app has no compiled code. To use `flatpak-builder` instead, use `com.nightbreedlabs.BeatsControl.yml`.

## Permissions

| Permission | Used for |
|---|---|
| `org.bluez` on the system bus | Finding the headphones and opening the control channel |
| PipeWire and PulseAudio sockets | Volume, audio mode and live EQ updates |
| `org.freedesktop.systemd1` on the session bus | Starting the EQ service and running audio commands |
| `xdg-config/pipewire/filter-chain.conf.d` | Writing the EQ configuration |
| `org.kde.StatusNotifierWatcher` | The tray icon |

**The systemd permission is powerful.** It lets the app start services and run commands in your user session, outside the sandbox, so treat this app as not fully sandboxed. Read the code in `beatscontrol/eq.py` if that matters to you.

## Command line

```bash
flatpak run com.nightbreedlabs.BeatsControl --status
flatpak run com.nightbreedlabs.BeatsControl --anc on      # or off, toggle
flatpak run com.nightbreedlabs.BeatsControl --eq on       # or off
flatpak run com.nightbreedlabs.BeatsControl --mode sbc-xq # or aac, calls
flatpak run com.nightbreedlabs.BeatsControl --background
flatpak run com.nightbreedlabs.BeatsControl --quit
```

## Tests

```bash
python3 -m unittest discover -s tests
```

Protocol notes are in [docs/PROTOCOL.md](docs/PROTOCOL.md), and research findings are in [docs/RESEARCH.md](docs/RESEARCH.md).

## License

[MIT](LICENSE). This software comes with no warranty. It uses an undocumented protocol, and you use it at your own risk.
