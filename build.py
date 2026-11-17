#!/usr/bin/env python3
"""
Construit l'exécutable d'OpenVidDL pour le système courant (aucune compilation croisée).

    pip install -r requirements.txt pyinstaller
    python build.py

Résultats dans dist/ :
    Windows : dist/OpenVidDL/OpenVidDL.exe  (+ installateur via installer/OpenVidDL.iss)
    macOS   : dist/OpenVidDL.app            (+ dist/OpenVidDL-macOS.dmg)
    Linux   : dist/OpenVidDL                (fichier unique)

FFmpeg et ffprobe sont embarqués : l'utilisateur final n'a rien d'autre à installer.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
SYSTEM = platform.system()  # Windows | Darwin | Linux


def app_version() -> str:
    return re.search(r'__version__ = "([^"]+)"', (ROOT / "app.py").read_text("utf-8")).group(1)


def fetch_ffmpeg() -> Path:
    """Récupère ffmpeg + ffprobe statiques pour la plateforme courante (via static-ffmpeg)."""
    try:
        from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise

        ffmpeg, ffprobe = get_or_fetch_platform_executables_else_raise()
    except Exception as exc:
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if not (ffmpeg and ffprobe):
            sys.exit(f"❌ Impossible d'obtenir FFmpeg ({exc}). Installez ffmpeg puis relancez.")
        print(f"ℹ static-ffmpeg indisponible ({exc.__class__.__name__}) : utilisation du FFmpeg du système {ffmpeg}")
    out = BUILD / "ffmpeg"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for src in (ffmpeg, ffprobe):
        src = Path(src)
        if not src.exists() and Path(str(src) + ".exe").exists():
            src = Path(str(src) + ".exe")
        dst = out / src.name
        shutil.copy2(src, dst)
        dst.chmod(0o755)
    print(f"✓ FFmpeg prêt : {sorted(p.name for p in out.iterdir())}")
    return out


def pyinstaller(ffdir: Path) -> None:
    sep = os.pathsep  # ';' sous Windows, ':' ailleurs
    icon = ROOT / "assets" / ("icon.ico" if SYSTEM == "Windows" else "icon.icns" if SYSTEM == "Darwin" else "icon.png")
    args = [
        sys.executable, "-m", "PyInstaller", str(ROOT / "app.py"),
        "--name", "OpenVidDL", "--noconfirm", "--clean",
        "--distpath", str(DIST), "--workpath", str(BUILD / "pyi"), "--specpath", str(BUILD),
        "--icon", str(icon),
        "--add-data", f"{ROOT / 'templates'}{sep}templates",
        "--add-binary", f"{ffdir}{sep}ffmpeg",
        # yt-dlp charge ses extracteurs dynamiquement : on embarque tout
        "--collect-submodules", "yt_dlp",
        "--collect-data", "certifi",
        "--hidden-import", "waitress",
        "--exclude-module", "static_ffmpeg",
        "--exclude-module", "tkinter",
    ]
    if SYSTEM == "Windows":
        args += ["--onedir", "--console", "--version-file", str(write_win_version())]
    elif SYSTEM == "Darwin":
        args += ["--onedir", "--windowed", "--osx-bundle-identifier", "org.openviddl.app"]
    else:
        args += ["--onefile", "--console"]
    print("→", " ".join(args[2:5]), "…")
    subprocess.check_call(args)


def write_win_version() -> Path:
    v = app_version()
    nums = (v.split(".") + ["0", "0", "0", "0"])[:4]
    tup = ", ".join(n if n.isdigit() else "0" for n in nums)
    path = BUILD / "version_info.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup})),
  kids=[StringFileInfo([StringTable('040C04B0', [
    StringStruct('CompanyName', 'OpenVidDL'),
    StringStruct('FileDescription', 'OpenVidDL - Téléchargeur de vidéos'),
    StringStruct('FileVersion', '{v}'),
    StringStruct('ProductName', 'OpenVidDL'),
    StringStruct('ProductVersion', '{v}'),
    StringStruct('LegalCopyright', 'Licence MIT')])]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])])
""", encoding="utf-8")
    return path


def windows_installer() -> None:
    iscc = shutil.which("iscc") or next(
        (p for p in (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe")
         if Path(p).exists()), None)
    if not iscc:
        print("ℹ Inno Setup absent : l'installateur n'est pas généré (https://jrsoftware.org/isdl.php).")
        print(f"  L'application portable est prête : {DIST / 'OpenVidDL' / 'OpenVidDL.exe'}")
        return
    subprocess.check_call([iscc, f"/DAppVersion={app_version()}", str(ROOT / "installer" / "OpenVidDL.iss")])
    print(f"✓ Installateur : {DIST / f'OpenVidDL-Setup-{app_version()}.exe'}")


def mac_background_app() -> None:
    """Pas d'icône « qui ne répond pas » dans le Dock : l'application vit en arrière-plan,
    l'interface est dans le navigateur (un nouveau double-clic la rouvre)."""
    import plistlib

    app = DIST / "OpenVidDL.app"
    plist_path = app / "Contents" / "Info.plist"
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)
    plist.update(LSUIElement=True, CFBundleShortVersionString=app_version(), CFBundleVersion=app_version(),
                 CFBundleDisplayName="OpenVidDL", NSHighResolutionCapable=True)
    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)
    # signature ad hoc à refaire après modification du bundle (obligatoire sur Apple Silicon)
    subprocess.check_call(["codesign", "--force", "--deep", "--sign", "-", str(app)])


def mac_dmg() -> None:
    mac_background_app()
    dmg = DIST / "OpenVidDL-macOS.dmg"
    dmg.unlink(missing_ok=True)
    stage = BUILD / "dmg"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    subprocess.check_call(["ditto", str(DIST / "OpenVidDL.app"), str(stage / "OpenVidDL.app")])
    os.symlink("/Applications", stage / "Applications")
    subprocess.check_call(["hdiutil", "create", "-volname", "OpenVidDL", "-srcfolder", str(stage),
                           "-ov", "-format", "UDZO", str(dmg)])
    print(f"✓ Image disque : {dmg}")


def main() -> None:
    print(f"=== Construction d'OpenVidDL {app_version()} pour {SYSTEM} ({platform.machine()}) ===")
    ffdir = fetch_ffmpeg()
    pyinstaller(ffdir)
    if SYSTEM == "Windows":
        windows_installer()
    elif SYSTEM == "Darwin":
        mac_dmg()
    else:
        print(f"✓ Exécutable : {DIST / 'OpenVidDL'}")


if __name__ == "__main__":
    main()
