#!/usr/bin/env bash
# Installation d'OpenVidDL pour Linux et macOS
set -e
cd "$(dirname "$0")"

echo "=== Installation d'OpenVidDL ==="
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "❌ Python 3.10+ est requis."
  echo "   macOS : brew install python   |   Debian/Ubuntu : sudo apt install python3 python3-venv"
  exit 1
fi
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "❌ Python 3.10 minimum requis (trouvé : $("$PY" --version))."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "• Création de l'environnement isolé (.venv)…"
  "$PY" -m venv .venv || { echo "❌ Sur Debian/Ubuntu : sudo apt install python3-venv"; exit 1; }
fi

echo "• Installation des dépendances…"
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt -q

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "• Téléchargement de FFmpeg (une seule fois)…"
  .venv/bin/python -c "import static_ffmpeg; static_ffmpeg.add_paths()" || echo "⚠ FFmpeg sera retenté au lancement."
fi

chmod +x run.sh
echo ""
echo "✅ Installation terminée. Lancez l'application avec :  ./run.sh"
