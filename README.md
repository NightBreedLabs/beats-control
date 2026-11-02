# Beats Control

Unofficial Linux app for **Beats Studio3 Wireless** headphones, packaged as a sandboxed Flatpak. It talks to the headphones the same way Apple's Android Beats app does, with no root and no raw Bluetooth access. Not affiliated with Apple or Beats.

## Features

| Feature | Status |
|---|---|
| Noise cancelling on or off | Tested on hardware |
| Live battery level | Tested on hardware |
| Volume | Tested on hardware |
| Music or Calls audio mode | Tested on hardware |
| Connect, disconnect, automatic recovery | Tested on hardware |
| Tray icon with menu | Registration, click and menu tested over D-Bus; not yet checked by eye in a tray |
| Start at login (XDG Background portal) | Tested |
| Run in background | Tested |
| Low battery alert, 20% or below | Not yet triggered on hardware |
| Charging indicator | Not yet tested while charging |
| Restore noise cancelling choice on connect | Connection path tested; not yet tested after a power cycle |
| Name on this computer | Local BlueZ alias; rename not yet tested |

### Not available

- **Firmware updates:** these need the official Beats app.
- **Serial number:** the Studio3 does not send device details on this channel. The firmware code comes from Bluetooth device information.
- **Transparency mode, ear detection, custom button actions:** not Studio3 features.
- **Renaming stored on the headphones:** only the name on this computer changes.

## Install

```bash
./build.sh
flatpak run com.nightbreedlabs.BeatsControl
```

`build.sh` needs `org.gnome.Platform//50`. The SDK is not needed because the app has no compiled code. For `flatpak-builder`, use `com.nightbreedlabs.BeatsControl.yml`.

## Command line

```bash
flatpak run com.nightbreedlabs.BeatsControl --status
flatpak run com.nightbreedlabs.BeatsControl --anc on    # also off or toggle
flatpak run com.nightbreedlabs.BeatsControl --background
flatpak run com.nightbreedlabs.BeatsControl --quit
```

## Tests

```bash
python3 -m unittest tests.test_protocol
```

Protocol notes are in [docs/PROTOCOL.md](docs/PROTOCOL.md).
