#!/usr/bin/env bash
# Creates a desktop / application-menu launcher for the RGB control app.
# Run it once on your PC from inside the project folder:  ./install-shortcut.sh
set -e

APPDIR="$(cd "$(dirname "$0")" && pwd)"
ICON="$APPDIR/assets/icon.svg"
DESKTOP_FILE_CONTENT="[Desktop Entry]
Type=Application
Name=My RGB Control
Comment=Control PC RGB fans, RAM and cooler
Exec=bash \"$APPDIR/run.sh\"
Path=$APPDIR
Icon=$ICON
Terminal=false
Categories=Utility;System;
StartupNotify=true"

# 1. Application-menu entry (shows up when you search your apps).
mkdir -p "$HOME/.local/share/applications"
MENU="$HOME/.local/share/applications/my-rgb-control.desktop"
echo "$DESKTOP_FILE_CONTENT" > "$MENU"
chmod +x "$MENU"
echo "Installed app-menu entry: $MENU"

# 2. A copy on the Desktop (if a Desktop folder exists).
if [ -d "$HOME/Desktop" ]; then
  DESK="$HOME/Desktop/my-rgb-control.desktop"
  echo "$DESKTOP_FILE_CONTENT" > "$DESK"
  chmod +x "$DESK"
  # GNOME requires desktop launchers to be marked "trusted" to run on click.
  gio set "$DESK" metadata::trusted true 2>/dev/null || true
  echo "Installed Desktop launcher: $DESK"
fi

# Refresh the menu database if the tool is available.
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo
echo "Done! Search your apps for 'RGB' (or look on your Desktop)."
echo "Tip: right-click it in the dock to pin it."
