#!/usr/bin/env bash
# Builds and installs for the current user. The app has no compiled code, so the
# Platform runtime is enough and the larger SDK is not required.
set -euo pipefail
cd "$(dirname "$0")"
id=com.nightbreedlabs.BeatsControl
b=.flatpak; rm -rf "$b/app"; mkdir -p "$b"
flatpak build-init "$b/app" "$id" org.gnome.Platform org.gnome.Platform 50
./install-files.sh "$b/app/files"
flatpak build-finish "$b/app" --command=beats-control --share=ipc --socket=wayland --socket=fallback-x11 \
    --device=dri --socket=pulseaudio --system-talk-name=org.bluez --talk-name=org.kde.StatusNotifierWatcher
flatpak build-export "$b/repo" "$b/app" >/dev/null
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo "$b/repo" beats-control.flatpak "$id"
flatpak install --user -y --noninteractive --reinstall ./beats-control.flatpak
