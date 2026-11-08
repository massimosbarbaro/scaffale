#!/usr/bin/env bash
# Mette «Scaffale» nel menu delle applicazioni e un'icona sul desktop.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
QUI="$(pwd)"
VOCE="[Desktop Entry]
Type=Application
Name=Scaffale
Comment=Cerca dentro il tuo archivio
Exec=\"$QUI/avvia.sh\"
Path=$QUI
Icon=$QUI/scaffale.png
Terminal=true
Categories=Office;Utility;"
mkdir -p "$HOME/.local/share/applications"
printf "%s\n" "$VOCE" > "$HOME/.local/share/applications/scaffale.desktop"
chmod +x "$HOME/.local/share/applications/scaffale.desktop"
SCRIVANIA="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$SCRIVANIA" ]; then
  cp "$HOME/.local/share/applications/scaffale.desktop" "$SCRIVANIA/Scaffale.desktop"
  chmod +x "$SCRIVANIA/Scaffale.desktop"
  # GNOME vuole che l'icona sul desktop sia dichiarata «fidata»
  command -v gio >/dev/null && gio set "$SCRIVANIA/Scaffale.desktop" metadata::trusted true 2>/dev/null
fi
echo "  Fatto: trovi Scaffale nel menu delle applicazioni e sul desktop."
