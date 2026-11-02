#!/usr/bin/env bash
# Copies the app into a Flatpak prefix.
set -euo pipefail
prefix="$1"
id=com.nightbreedlabs.BeatsControl
install -Dm755 beats-control "$prefix/bin/beats-control"
install -Dm644 -t "$prefix/share/beats-control/beatscontrol" beatscontrol/*.py
install -Dm644 "data/$id.desktop" "$prefix/share/applications/$id.desktop"
install -Dm644 "data/$id.metainfo.xml" "$prefix/share/metainfo/$id.metainfo.xml"
install -Dm644 "data/$id.svg" "$prefix/share/icons/hicolor/scalable/apps/$id.svg"
