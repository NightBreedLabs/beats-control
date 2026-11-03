# Beats Control

Unofficial Linux app for **Beats Studio3 Wireless** headphones, packaged as a Flatpak. It controls noise cancelling, shows live battery, keeps volume in sync, and adds a 32-band equalizer.

> **Made specifically for the Beats Studio3 Wireless.** It has been tested only on one Studio3 (firmware code `0244`) on Bazzite Linux with Niri and KDE Plasma. It might work with other Beats or Apple headphones, but that has not been tested in any way. The app currently looks only for the Studio3's product ID (`0x2009`), so other models will not be detected without changing the code. Sending these commands to another model could behave differently, so try that at your own risk.

Not affiliated with, endorsed by, or supported by Apple Inc. or Beats Electronics. Beats and Studio3 are trademarks of their owners.

## Features

| Feature | Status |
|---|---|
| Noise cancelling on or off, from the app, tray or command line | Tested on a Studio3 |
| Live battery level | Tested on a Studio3 |
| Volume kept in sync with the headphones and desktop | Tested on a Studio3 |
| Smaller steps for the headphone volume buttons | Tested on a Studio3 |
| 32-band EQ with presets, sliders and typed dB values | Response measured, tested on a Studio3 |
| EQ with EasyEffects running, and with it fully off | Tested on a Studio3 |
| AAC or SBC-XQ selection | Tested on a Studio3 |
| Music or Calls audio mode | Tested on a Studio3 |
| Connect, disconnect and automatic reconnect of controls | Tested on a Studio3 |
| Run in background, start at login | Tested on Niri and KDE Plasma |
| Tray icon with menu | Tested on KDE Plasma, and over D-Bus on Niri |
| Low battery alert at 20% or below | Not yet triggered |
| Battery saver and idle disconnect | Not yet triggered |
| Charging indicator | Not tested while charging |
| Restoring your noise cancelling choice | Not tested after a power cycle |
| Restoring your codec choice, recovering audio left off | Not tested after a reconnect |
| Name on this computer | Not tested |
| Install from the single file on an empty Flatpak setup | Tested, app not run on a second PC |
| KDE Plasma on Wayland | Tested, see [docs/TESTING.md](docs/TESTING.md) |
| GNOME and other desktops | Not tested |

### Equalizer

The EQ runs on your computer, not in the headphones. It uses 32 third-octave bands through PipeWire's filter engine, which is built into the app and runs only while the EQ is enabled. Your default output stays on the headphones, so your desktop's volume control keeps working normally.

- **Presets:** Flat, Warm, Deep Bass, Vocal, Bright, Treble Boost and Late Night. All except Flat build on a bright base curve tuned by ear on a Studio3.
- **Moving a band changes only that band.** If a large boost distorts, lower **Output level**.
- **EasyEffects:** not required. If you use it, see [EasyEffects users](#easyeffects-users).
- Calls mode bypasses the EQ.

### Not available

- **aptX and LDAC:** the headphones advertise only SBC and AAC-LC at up to 256 kbps. See [docs/RESEARCH.md](docs/RESEARCH.md).
- **EQ stored on the headphones:** the official Android app has no EQ feature for this model.
- **Firmware updates:** these need the official Beats app.
- **Serial number:** the headphones do not send device details on the channel this app uses.
- **Transparency mode, ear detection, custom button actions:** not Studio3 features.
- **Renaming stored on the headphones:** only the name on your computer changes.

## Install

You only need Flatpak with Flathub set up, and your Studio3 paired in your Bluetooth settings.

1. **[Download beats-control.flatpak](https://github.com/NightBreedLabs/beats-control/releases/latest/download/beats-control.flatpak)** from the [latest release](https://github.com/NightBreedLabs/beats-control/releases/latest).
2. Install it. Flatpak fetches anything else it needs automatically.

```bash
flatpak install --user ./beats-control.flatpak
```

3. Open **Beats Control** from your app launcher, or run:

```bash
flatpak run com.nightbreedlabs.BeatsControl
```

The first install downloads the GNOME runtime, which is several hundred MB if you do not already have it. Everything else is inside the app, including its EQ engine, so there is nothing else to install. To update, download and install the newest release. To remove it:

```bash
flatpak uninstall com.nightbreedlabs.BeatsControl
```

### Build from source

```bash
flatpak install flathub org.flatpak.Builder org.gnome.Sdk//50
git clone https://github.com/NightBreedLabs/beats-control.git
cd beats-control
./build.sh
```

The build compiles PipeWire's filter engine from source, so the first one takes several minutes.

## Permissions

| Permission | Used for |
|---|---|
| `org.bluez` on the system bus | Finding the headphones and opening the control channel |
| PipeWire and PulseAudio sockets | Volume, audio mode and the EQ |
| `org.kde.StatusNotifierWatcher` | The tray icon |
| `org.mpris.MediaPlayer2.*` on the session bus | Resuming players that an audio mode change paused |

### EasyEffects users

If EasyEffects is running, the EQ sits after it in the audio chain, so both apply and two equalizers can stack. Turn EasyEffects off or bypass it yourself, or give this app one optional permission so it can bypass EasyEffects while the EQ is on:

```bash
flatpak override --user --talk-name=org.freedesktop.systemd1 com.nightbreedlabs.BeatsControl
```

**That permission is powerful.** It lets the app run commands in your user session, outside the sandbox. It only works with the Flatpak version of EasyEffects, and it assumes EasyEffects should be active when the EQ is off. To undo it:

```bash
flatpak override --user --reset com.nightbreedlabs.BeatsControl
```

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

Protocol notes are in [docs/PROTOCOL.md](docs/PROTOCOL.md), research findings are in [docs/RESEARCH.md](docs/RESEARCH.md), test status is in [docs/TESTING.md](docs/TESTING.md), changes are in [docs/CHANGELOG.md](docs/CHANGELOG.md), and Flathub preparation notes are in [docs/FLATHUB.md](docs/FLATHUB.md).

## License

[MIT](LICENSE). This software comes with no warranty. It uses an undocumented protocol, and you use it at your own risk.
