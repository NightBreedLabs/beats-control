# Testing status for 0.8.0

## Tested on Bazzite with Niri

- EQ on and off, presets, sliders and typed values
- EQ with EasyEffects running, and with it fully off
- Mode changes between AAC, SBC-XQ and Calls
- Volume staying steady across toggles and restarts
- Recovery of EasyEffects' output after a forced kill
- Install from the single file into empty Flatpak storage

## Tested on KDE Plasma on Wayland

Checked by the owner on one Studio3, except where noted:

- The app opens and finds the headphones.
- The tray icon appears, a left click opens the window, and the right-click menu works.
- Run in background keeps the tray icon.
- Start at login worked after a reboot, confirmed in the session log.
- The EQ changes the sound with no volume jump when toggled.
- Plasma's volume control, the headphone buttons and the app stay in sync.
- Volume notifications appear once.
- AAC, SBC-XQ and Calls switch without losing audio.
- EasyEffects bypass and routing work.
- Players paused by a mode change resume after about 3 seconds, tested with Brave.

## Not tested

- GNOME and other desktops
- Low battery alert, battery saver and idle disconnect
- Charging indicator
- Restoring settings after a headphone power cycle
- Other Linux distributions, or a full run on a second PC
