#!/usr/bin/env bash
# Lance OpenVidDL (et met à jour le moteur yt-dlp en silence)
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || ./install.sh || exit 1
.venv/bin/python -m pip install -q --upgrade "yt-dlp[default]" >/dev/null 2>&1 || true
exec .venv/bin/python app.py "$@"
