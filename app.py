#!/usr/bin/env python3
"""
OpenVidDL — Téléchargeur de vidéos open source (licence MIT).

Interface web locale construite sur yt-dlp (+1800 sites pris en charge)
et FFmpeg (conversion vers tous les formats courants).

Usage :
    python app.py                      # ouvre http://127.0.0.1:8765
    python app.py --port 9000          # autre port
    python app.py --output ~/Vidéos    # autre dossier de destination
    python app.py --host 0.0.0.0       # accessible depuis le réseau local (téléphone…)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

__version__ = "1.0.0"

# --------------------------------------------------------------------------- version compilée (.exe / .app)
FROZEN = getattr(sys, "frozen", False)
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
USER_DIR = Path.home() / ".openviddl"
# yt-dlp mis à jour depuis l'application (version compilée). Un dossier par version de l'application :
# une nouvelle version installée repart toujours de son moteur embarqué, plus récent.
ENGINE_DIR = USER_DIR / "engine" / __version__

if FROZEN:
    # Fenêtre sans console (macOS .app) : stdout/stderr n'existent pas -> journal dans un fichier
    if sys.stdout is None or sys.stderr is None:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        _log = open(USER_DIR / "openviddl.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or _log
        sys.stderr = sys.stderr or _log
    # Accents et symboles sans plantage, quelle que soit la console
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(errors="replace", line_buffering=True)
        except Exception:
            pass
    # FFmpeg embarqué dans l'exécutable
    _ff = BASE_DIR / "ffmpeg"
    if _ff.is_dir():
        os.environ["PATH"] = str(_ff) + os.pathsep + os.environ.get("PATH", "")
    # Moteur yt-dlp plus récent téléchargé par le bouton « Mettre à jour » (prioritaire sur celui embarqué)
    _wheels = sorted(ENGINE_DIR.glob("yt_dlp-*.whl"), key=lambda p: p.stat().st_mtime) if ENGINE_DIR.is_dir() else []
    if _wheels:
        sys.path.insert(0, str(_wheels[-1]))

try:
    from flask import Flask, abort, jsonify, render_template, request, send_file
except ImportError:
    sys.exit("Flask n'est pas installé. Lancez d'abord install.sh (Linux/macOS) ou install.bat (Windows).")

try:
    import yt_dlp
    from yt_dlp.utils import DownloadCancelled
except ImportError:
    sys.exit("yt-dlp n'est pas installé. Lancez d'abord install.sh (Linux/macOS) ou install.bat (Windows).")

DEFAULT_DIR = Path(os.environ.get("OPENVIDDL_DIR", Path.home() / "Downloads" / "OpenVidDL")).expanduser()

# Conteneurs vidéo proposés -> (format de fusion yt-dlp, post-traitement FFmpeg)
VIDEO_FORMATS = {
    "mp4": ("mp4", "FFmpegVideoRemuxer"),
    "mkv": ("mkv", "FFmpegVideoRemuxer"),
    "webm": ("webm", "FFmpegVideoConvertor"),  # webm impose VP8/VP9/AV1 -> réencodage si besoin
    "mov": ("mp4", "FFmpegVideoRemuxer"),
    "avi": ("mkv", "FFmpegVideoConvertor"),
}
# Formats audio proposés -> codec FFmpegExtractAudio
AUDIO_FORMATS = {"mp3": "mp3", "m4a": "m4a", "opus": "opus", "flac": "flac", "wav": "wav", "ogg": "vorbis"}
BROWSERS = {"chrome", "chromium", "firefox", "edge", "brave", "opera", "vivaldi", "safari"}
QUALITIES = {"best", "4320", "2160", "1440", "1080", "720", "480", "360", "240", "144"}

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.config["DOWNLOAD_DIR"] = DEFAULT_DIR
app.config["LOCAL_ONLY"] = True
app.config["FFMPEG"] = None

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
SLOTS = threading.Semaphore(int(os.environ.get("OPENVIDDL_PARALLEL", "3")))
PUBLIC_FIELDS = ("id", "url", "title", "status", "stage", "progress", "speed", "eta", "item", "n_items",
                 "error", "warning", "format", "created", "files")


# --------------------------------------------------------------------------- FFmpeg
def setup_ffmpeg() -> str | None:
    """Utilise le FFmpeg du système, sinon télécharge automatiquement une version statique."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return "intégré" if FROZEN and (BASE_DIR / "ffmpeg").is_dir() else "système"
    try:
        import static_ffmpeg  # type: ignore

        print("• Préparation de FFmpeg (premier lancement : téléchargement unique ~70 Mo)…")
        static_ffmpeg.add_paths()
        if shutil.which("ffmpeg"):
            return "intégré (static-ffmpeg)"
    except Exception as exc:  # pragma: no cover
        print(f"⚠ Impossible de préparer FFmpeg automatiquement : {exc}")
    print("⚠ FFmpeg introuvable : les conversions et la fusion audio+vidéo seront indisponibles.")
    return None


# --------------------------------------------------------------------------- yt-dlp
class JobLogger:
    """Redirige les messages yt-dlp vers le job (au lieu de la console)."""

    def __init__(self, job: dict):
        self.job = job

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.job["warning"] = strip_ansi(msg)[:300]

    def error(self, msg):
        self.job["last_error"] = strip_ansi(msg)


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", str(text))


def clean_error(err) -> str:
    msg = strip_ansi(str(err)).replace("ERROR: ", "").strip()
    msg = re.split(r";?\s*please report this issue", msg, flags=re.I)[0].strip()
    hints = {
        "Unable to connect": "Connexion au site impossible : vérifiez votre connexion internet (ou proxy/VPN).",
        "Connection refused": "Le site a refusé la connexion : vérifiez le lien et votre connexion internet.",
        "Name or service not known": "Adresse introuvable : vérifiez le lien et votre connexion internet.",
        "getaddrinfo failed": "Adresse introuvable : vérifiez le lien et votre connexion internet.",
        "Sign in to confirm": "Le site demande une connexion : choisissez votre navigateur dans « Cookies ».",
        "Private video": "Vidéo privée : connectez-vous dans votre navigateur puis utilisez l'option « Cookies ».",
        "Unsupported URL": "Lien non pris en charge par ce site.",
        "DRM": "Contenu protégé par DRM : son téléchargement n'est pas possible.",
        "ffmpeg": "FFmpeg est requis pour cette opération (relancez l'installation).",
        "HTTP Error 403": "Accès refusé par le site : mettez à jour le moteur (bouton ⟳) puis réessayez.",
    }
    for key, hint in hints.items():
        if key.lower() in msg.lower():
            return f"{hint}\n\nDétail : {msg[:400]}"
    return msg[:600]


def format_selector(fmt: str, quality: str) -> str:
    h = f"[height<={quality}]" if quality != "best" else ""
    if fmt in AUDIO_FORMATS:
        return "bestaudio/best"
    if fmt in ("mp4", "mov"):  # privilégie H.264/AAC : lisible partout sans réencodage
        return (f"bv*{h}[ext=mp4]+ba[ext=m4a]/b{h}[ext=mp4]/"
                f"bv*{h}+ba/b{h}/bv*+ba/b")
    if fmt == "webm":
        return f"bv*{h}[ext=webm]+ba[ext=webm]/bv*{h}+ba/b{h}/bv*+ba/b"
    return f"bv*{h}+ba/b{h}/bv*+ba/b"  # mkv, avi, original


def build_ydl_opts(job: dict, o: dict) -> dict:
    fmt, quality = o["format"], o["quality"]
    name = "%(title).150B [%(id)s].%(ext)s"
    if o["playlist"]:
        name = "%(playlist_title,playlist_id|Playlist).100B/%(playlist_index|0)03d - " + name

    opts = {
        "format": format_selector(fmt, quality),
        "outtmpl": {"default": name},
        # Chaque tâche travaille dans son propre dossier : aucune collision entre téléchargements
        # simultanés, et un MP3 ne réutilise/supprime jamais un MP4 déjà présent.
        "paths": {"home": str(job_dir(job))},
        "noplaylist": not o["playlist"],
        "ignoreerrors": "only_download" if o["playlist"] else False,
        "windowsfilenames": True,
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "continuedl": True,
        "logger": JobLogger(job),
        "progress_hooks": [make_progress_hook(job)],
        "postprocessor_hooks": [make_pp_hook(job)],
    }
    if o.get("cookies") in BROWSERS:
        opts["cookiesfrombrowser"] = (o["cookies"],)

    pps: list[dict] = []
    if fmt in AUDIO_FORMATS:
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": AUDIO_FORMATS[fmt], "preferredquality": "0"})
    elif fmt in VIDEO_FORMATS:
        merge, pp = VIDEO_FORMATS[fmt]
        opts["merge_output_format"] = merge
        pps.append({"key": pp, "preferedformat": fmt})

    if o["subtitles"]:
        opts.update(writesubtitles=True, writeautomaticsub=False,
                    subtitleslangs=["fr.*", "en.*", "-live_chat"])
        if fmt not in AUDIO_FORMATS and fmt != "avi":
            pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

    pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": fmt != "avi"})
    opts["postprocessors"] = pps
    return opts


def make_progress_hook(job: dict):
    def hook(d):
        if job["cancel"]:
            raise DownloadCancelled("Téléchargement annulé")
        info = d.get("info_dict") or {}
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            job.update(
                status="downloading",
                progress=round(done * 100 / total, 1) if total else None,
                speed=d.get("speed"),
                eta=d.get("eta"),
                title=info.get("title") or job["title"],
                item=info.get("playlist_index"),
                n_items=info.get("n_entries") or info.get("playlist_count"),
            )
            fid = info.get("format_id", "")
            job["stage"] = "audio" if (info.get("vcodec") == "none" and "+" not in fid) else "vidéo"
        elif d["status"] == "finished":
            job["progress"] = 100
    return hook


def make_pp_hook(job: dict):
    labels = {"Merger": "Fusion audio + vidéo", "FFmpegExtractAudio": "Extraction audio",
              "FFmpegVideoConvertor": "Conversion", "FFmpegVideoRemuxer": "Remuxage",
              "FFmpegEmbedSubtitle": "Ajout des sous-titres", "FFmpegMetadata": "Métadonnées"}

    def hook(d):
        if d["status"] == "started":
            job.update(status="processing", stage=labels.get(d.get("postprocessor"), "Finalisation"), speed=None, eta=None)
        elif d["status"] == "finished" and d.get("postprocessor") == "MoveFiles":
            path = (d.get("info_dict") or {}).get("filepath")
            if path:
                job["_seen"].append(path)
    return hook


def job_dir(job: dict) -> Path:
    return Path(app.config["DOWNLOAD_DIR"]) / ".openviddl-tmp" / job["id"]


PARTIAL = re.compile(r"\.(part|ytdl|temp)$|\.part-Frag|\.f\d+\.\w+$", re.I)


def publish_files(job: dict) -> list[str]:
    """Déplace les fichiers terminés du dossier de travail vers le dossier de destination."""
    src, dest_root = job_dir(job), Path(app.config["DOWNLOAD_DIR"])
    moved: list[str] = []
    if src.is_dir():
        for f in sorted(p for p in src.rglob("*") if p.is_file()):
            if PARTIAL.search(f.name):
                continue
            dest = dest_root / f.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest))
            moved.append(str(dest))
    shutil.rmtree(src, ignore_errors=True)
    return moved


def collect_files(info) -> list[str]:
    out: list[str] = []
    if not info:
        return out
    if info.get("_type") in ("playlist", "multi_video"):
        for entry in info.get("entries") or []:
            out += collect_files(entry)
        return out
    for rd in info.get("requested_downloads") or []:
        path = rd.get("filepath") or rd.get("_filename")
        if path:
            out.append(path)
    if info.get("filepath"):
        out.append(info["filepath"])
    return out


def run_job(job: dict, options: dict) -> None:
    with SLOTS:
        if job["cancel"]:
            job["status"] = "cancelled"
            return
        job["status"] = "starting"
        try:
            Path(app.config["DOWNLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
            with yt_dlp.YoutubeDL(build_ydl_opts(job, options)) as ydl:
                info = ydl.extract_info(job["url"], download=True)
            produced = {os.path.basename(p) for p in collect_files(info) + job["_seen"] if p}
            files = publish_files(job)
            # fichiers principaux d'abord (vidéo/audio), puis sous-titres éventuels
            files.sort(key=lambda p: (os.path.basename(p) not in produced, p))
            if not files:
                raise RuntimeError(job.get("last_error") or "Aucun fichier n'a été téléchargé.")
            if info and not job["title"]:
                job["title"] = info.get("title")
            job.update(status="done", progress=100, files=files, speed=None, eta=None, stage=None)
        except DownloadCancelled:
            job.update(status="cancelled", speed=None, eta=None)
        except Exception as exc:
            if job["cancel"]:
                job.update(status="cancelled", speed=None, eta=None)
            else:
                job.update(status="error", error=clean_error(job.get("last_error") or exc), speed=None, eta=None)
    if job["status"] != "done":
        # playlist interrompue : on conserve les éléments déjà terminés
        kept = publish_files(job) if job.get("n_items") else (shutil.rmtree(job_dir(job), ignore_errors=True) or [])
        job["files"] = kept


def public(job: dict) -> dict:
    data = {k: job.get(k) for k in PUBLIC_FIELDS}
    data["files"] = [{"name": os.path.basename(p), "path": p} for p in job.get("files") or []]
    return data


def local_request() -> bool:
    return request.remote_addr in ("127.0.0.1", "::1")


# --------------------------------------------------------------------------- routes
@app.get("/")
def index():
    return render_template("index.html", version=__version__)


@app.get("/api/status")
def api_status():
    try:
        from yt_dlp.extractor import gen_extractor_classes
        n_sites = sum(1 for _ in gen_extractor_classes())
    except Exception:
        n_sites = None
    return jsonify(
        frozen=FROZEN,
        version=__version__,
        ytdlp=yt_dlp.version.__version__,
        ffmpeg=app.config["FFMPEG"],
        download_dir=str(app.config["DOWNLOAD_DIR"]),
        sites=n_sites,
        local=local_request(),
    )


@app.post("/api/info")
def api_info():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not re.match(r"^https?://", url, re.I):
        return jsonify(error="Lien invalide : il doit commencer par http:// ou https://"), 400
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist", "noplaylist": not data.get("playlist")}
    if data.get("cookies") in BROWSERS:
        opts["cookiesfrombrowser"] = (data["cookies"],)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.sanitize_info(ydl.extract_info(url, download=False))
    except Exception as exc:
        return jsonify(error=clean_error(exc)), 422
    heights = sorted({f.get("height") for f in info.get("formats") or [] if f.get("height")}, reverse=True)
    is_pl = info.get("_type") == "playlist"
    thumb = info.get("thumbnail")
    if not thumb and info.get("thumbnails"):
        thumb = info["thumbnails"][-1].get("url")
    return jsonify(
        title=info.get("title"),
        uploader=info.get("uploader") or info.get("channel"),
        duration=info.get("duration"),
        thumbnail=thumb,
        site=info.get("extractor_key") or info.get("ie_key"),
        is_playlist=is_pl,
        count=len(info.get("entries") or []) if is_pl else None,
        heights=heights,
    )


@app.post("/api/download")
def api_download():
    data = request.get_json(silent=True) or {}
    urls = [u.strip() for u in data.get("urls") or [] if isinstance(u, str) and u.strip()]
    urls = [u for u in urls if re.match(r"^https?://", u, re.I)]
    if not urls:
        return jsonify(error="Ajoutez au moins un lien valide (http:// ou https://)."), 400
    fmt = data.get("format", "mp4")
    if fmt not in VIDEO_FORMATS and fmt not in AUDIO_FORMATS and fmt != "original":
        return jsonify(error="Format inconnu."), 400
    quality = str(data.get("quality", "best"))
    if quality not in QUALITIES:
        quality = "best"
    options = {"format": fmt, "quality": quality, "playlist": bool(data.get("playlist")),
               "subtitles": bool(data.get("subtitles")), "cookies": data.get("cookies") or ""}
    if (fmt != "original") and not app.config["FFMPEG"]:
        return jsonify(error="FFmpeg est introuvable : seul le format « Original » est disponible. Relancez l'installation."), 400

    ids = []
    for url in urls[:100]:
        jid = uuid.uuid4().hex[:10]
        job = {"id": jid, "url": url, "title": None, "status": "queued", "stage": None, "progress": 0,
               "speed": None, "eta": None, "item": None, "n_items": None, "error": None, "warning": None,
               "format": fmt.upper() + ("" if quality == "best" or fmt in AUDIO_FORMATS else f" {quality}p"),
               "created": time.time(), "files": [], "cancel": False, "_seen": []}
        with JOBS_LOCK:
            JOBS[jid] = job
        threading.Thread(target=run_job, args=(job, options), daemon=True).start()
        ids.append(jid)
    return jsonify(ids=ids)


@app.get("/api/jobs")
def api_jobs():
    with JOBS_LOCK:
        jobs = sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)
        return jsonify([public(j) for j in jobs])


@app.post("/api/jobs/<jid>/cancel")
def api_cancel(jid):
    job = JOBS.get(jid) or abort(404)
    job["cancel"] = True
    if job["status"] == "queued":
        job["status"] = "cancelled"
    return jsonify(ok=True)


@app.delete("/api/jobs/<jid>")
def api_remove(jid):
    with JOBS_LOCK:
        job = JOBS.get(jid)
        if job and job["status"] in ("done", "error", "cancelled"):
            del JOBS[jid]
    return jsonify(ok=True)


@app.post("/api/jobs/clear")
def api_clear():
    with JOBS_LOCK:
        for jid in [k for k, j in JOBS.items() if j["status"] in ("done", "error", "cancelled")]:
            del JOBS[jid]
    return jsonify(ok=True)


@app.get("/api/file/<jid>/<int:n>")
def api_file(jid, n):
    job = JOBS.get(jid) or abort(404)
    files = job.get("files") or []
    if n < 0 or n >= len(files) or not os.path.isfile(files[n]):
        abort(404)
    return send_file(files[n], as_attachment=True, download_name=os.path.basename(files[n]))


@app.post("/api/open-folder")
def api_open_folder():
    if not local_request():
        return jsonify(error="Disponible uniquement sur l'ordinateur qui exécute OpenVidDL."), 403
    folder = Path(app.config["DOWNLOAD_DIR"])
    folder.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:
        return jsonify(error=str(exc)), 500
    return jsonify(ok=True)


@app.post("/api/update")
def api_update():
    """Met à jour yt-dlp (les sites changent souvent : c'est la clé pour que tout continue de marcher)."""
    if not local_request():
        return jsonify(error="Disponible uniquement sur l'ordinateur qui exécute OpenVidDL."), 403
    if FROZEN:
        return update_engine_frozen()
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        return jsonify(error=str(exc)), 500
    if res.returncode != 0:
        return jsonify(error=(res.stderr or res.stdout)[-800:]), 500
    out = subprocess.run([sys.executable, "-c", "import yt_dlp;print(yt_dlp.version.__version__)"],
                         capture_output=True, text=True).stdout.strip()
    changed = out and out != yt_dlp.version.__version__
    return jsonify(ok=True, version=out, restart=bool(changed))


def update_engine_frozen():
    """Version compilée : télécharge la dernière roue yt-dlp depuis PyPI (pur Python, importable telle quelle)."""
    import json
    import ssl
    import urllib.request

    contexts = []
    try:
        import certifi
        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    contexts.append(ssl.create_default_context())  # magasin du système (proxy d'entreprise, etc.)

    def fetch(url, timeout):
        err = None
        for ctx in contexts:
            try:
                return urllib.request.urlopen(url, timeout=timeout, context=ctx)
            except Exception as exc:  # essaie le contexte suivant
                err = exc
        raise err

    try:
        with fetch("https://pypi.org/pypi/yt-dlp/json", 30) as r:
            meta = json.load(r)
        latest = meta["info"]["version"]
        if latest == yt_dlp.version.__version__:
            return jsonify(ok=True, version=latest, restart=False)
        wheel = next(f for f in meta["urls"] if f["filename"].endswith("py3-none-any.whl"))
        ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = ENGINE_DIR / (wheel["filename"] + ".part")
        with fetch(wheel["url"], 300) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        for old in ENGINE_DIR.glob("yt_dlp-*.whl"):
            old.unlink(missing_ok=True)
        tmp.replace(ENGINE_DIR / wheel["filename"])
        return jsonify(ok=True, version=latest, restart=True)
    except Exception as exc:
        return jsonify(error=f"Mise à jour impossible : {exc}"), 500


@app.post("/api/shutdown")
def api_shutdown():
    if not local_request():
        return jsonify(error="Disponible uniquement sur l'ordinateur qui exécute OpenVidDL."), 403
    for job in JOBS.values():
        job["cancel"] = True
    threading.Timer(0.8, lambda: os._exit(0)).start()
    return jsonify(ok=True)


def already_running(host: str, port: int) -> bool:
    """True si une instance d'OpenVidDL répond déjà sur ce port."""
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/status", timeout=1.5) as r:
            return "ytdlp" in json.load(r)
    except Exception:
        return False


def port_free(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


# --------------------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description="OpenVidDL — téléchargeur de vidéos open source")
    parser.add_argument("--host", default=os.environ.get("OPENVIDDL_HOST", "127.0.0.1"),
                        help="adresse d'écoute (0.0.0.0 = réseau local)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPENVIDDL_PORT", "8765")))
    parser.add_argument("--output", "-o", default=str(DEFAULT_DIR), help="dossier de destination")
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args()

    probe = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    if already_running(probe, args.port):
        # Double-clic alors que l'application tourne déjà : on rouvre simplement l'interface
        print("OpenVidDL est déjà lancé : ouverture de l'interface.")
        webbrowser.open(f"http://{probe}:{args.port}")
        return
    if not port_free(args.host, args.port):
        for p in range(args.port + 1, args.port + 50):
            if port_free(args.host, p):
                args.port = p
                break

    app.config["DOWNLOAD_DIR"] = Path(args.output).expanduser().resolve()
    app.config["DOWNLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["FFMPEG"] = setup_ffmpeg()

    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}"
    print(f"\n  OpenVidDL {__version__}  (yt-dlp {yt_dlp.version.__version__}, FFmpeg : {app.config['FFMPEG'] or 'absent'})")
    print(f"  Dossier : {app.config['DOWNLOAD_DIR']}")
    print(f"  Ouvrez  : {url}")
    if args.host in ("0.0.0.0", "::"):
        print("  ⚠ Mode réseau : toute personne sur votre réseau local peut utiliser l'application.")
    print("  Pour quitter : bouton « Quitter » de l'interface" + (", ou fermez cette fenêtre.\n" if FROZEN else " ou Ctrl+C.\n"))

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=16, _quiet=True)
    except ImportError:
        app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
