# Flathub preparation notes

Done:

- The manifest builds everything from source with `org.gnome.Sdk`, including a pinned PipeWire archive.
- No host service, host config access or `org.freedesktop.systemd1` permission is needed by default.
- The app ships a desktop file, icon and metainfo.
- The app ID, `io.github.NightBreedLabs.BeatsControl`, uses the project's GitHub organization.

Still needed before submitting:

- **Name and trademark:** check Flathub's rules on using a third party's brand name in the app name and icon, and state clearly that the app is unofficial.
- **Metainfo:** add screenshots, developer information and a fuller description, then run `flatpak run --command=flatpak-builder-lint org.flatpak.Builder appstream` on it.
- **Manifest:** run the Flathub linter on the manifest, and point the app source at a tagged Git commit instead of a local directory.
- **Permissions:** expect review questions about `--filesystem=xdg-run/pipewire-0`, the StatusNotifierWatcher access and the `org.mpris.MediaPlayer2.*` wildcard.
