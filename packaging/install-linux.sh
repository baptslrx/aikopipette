#!/bin/bash
# Installe AikoPipette pour l'utilisateur courant (pas besoin de sudo)
set -e
cd "$(dirname "$0")"
DEST="$HOME/.local/share/aikopipette"
mkdir -p "$DEST" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"
pkill -x AikoPipette 2>/dev/null || true
rm -rf "$DEST/app"
cp -r AikoPipette "$DEST/app"
cp AikoPipette/_internal/assets/icon-256.png "$HOME/.local/share/icons/hicolor/256x256/apps/aikopipette.png" 2>/dev/null || true
cat > "$HOME/.local/share/applications/aikopipette.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=AikoPipette
Comment=Pipette à couleurs et palettes
Exec=$DEST/app/AikoPipette
Icon=aikopipette
Categories=Utility;
DESK
echo "✓ AikoPipette installé. Lance-le depuis ton menu d'applications (ou : $DEST/app/AikoPipette)"
if ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor; then
  echo "ℹ Si l'appli ne démarre pas : sudo apt install libxcb-cursor0"
fi
nohup "$DEST/app/AikoPipette" >/dev/null 2>&1 &
