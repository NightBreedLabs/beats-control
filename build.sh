#!/usr/bin/env bash
# Builds from source, makes a single-file bundle and installs it for the current user.
# Needs: flatpak install flathub org.flatpak.Builder org.gnome.Sdk//50
set -euo pipefail
cd "$(dirname "$0")"
id=com.nightbreedlabs.BeatsControl
b=.flatpak
flatpak run --filesystem="$PWD" org.flatpak.Builder --user --force-clean --state-dir="$b/state" --repo="$b/repo" "$b/app" "$id.yml"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo "$b/repo" beats-control.flatpak "$id"
flatpak install --user -y --noninteractive --reinstall ./beats-control.flatpak
