# ⬇ OpenVidDL

**Téléchargeur de vidéos libre et open source.** Collez un lien, choisissez le format, cliquez sur *Télécharger*.

- 🌍 **Plus de 1 700 sites** : YouTube, TikTok, Instagram, Facebook, X/Twitter, Vimeo, Dailymotion, Twitch, Reddit, SoundCloud, Bilibili, sites d'actualités… ainsi que les liens directs vers des fichiers vidéo et les flux HLS/DASH (`.m3u8`, `.mpd`).
- 🎞 **Tous les formats courants** :
  - vidéo : **MP4**, **MKV**, **WEBM**, **MOV**, **AVI**, ou l'original sans conversion ;
  - audio seul : **MP3**, **M4A/AAC**, **OPUS**, **FLAC**, **WAV**, **OGG**.
- 📺 Qualité au choix, de 144p jusqu'à 8K.
- 📚 Playlists et chaînes entières, plusieurs liens à la fois (un par ligne), 3 téléchargements en parallèle.
- 💬 Sous-titres FR/EN intégrés dans la vidéo, métadonnées et chapitres conservés.
- 🔐 Vidéos privées ou réservées aux membres, en réutilisant la session de votre navigateur (option *Cookies*).
- 📱 Accessible depuis votre téléphone sur le réseau local (option `--host 0.0.0.0`).
- 🖥 Windows, macOS, Linux et Docker. Aucune publicité, aucun traçage.

Le moteur est [yt-dlp](https://github.com/yt-dlp/yt-dlp), et les conversions sont faites par [FFmpeg](https://ffmpeg.org).

---

## 🚀 Installation

### ✅ Le plus simple : l'installateur (sans Python, FFmpeg inclus)

Téléchargez le fichier correspondant à votre système dans la page **[Releases](../../releases/latest)** :

| Système | Fichier | Comment faire |
|---|---|---|
| **Windows 10/11** | `OpenVidDL-Setup-x.y.z.exe` | Double-cliquez, puis *Suivant → Installer*. Une icône apparaît sur le bureau et dans le menu Démarrer. Aucun droit administrateur n'est nécessaire. |
| Windows (portable) | `OpenVidDL-Windows-portable.zip` | Décompressez, puis lancez `OpenVidDL.exe` (rien n'est installé, fonctionne depuis une clé USB). |
| **macOS** (Apple Silicon) | `OpenVidDL-macOS.dmg` | Ouvrez le .dmg et glissez **OpenVidDL** dans *Applications*. |
| **Linux** (x86_64) | `OpenVidDL-Linux-x86_64.tar.gz` | `tar xzf OpenVidDL-Linux-*.tar.gz && ./OpenVidDL` |

L'application ouvre automatiquement son interface dans votre navigateur. Si vous la relancez alors qu'elle tourne déjà, elle rouvre simplement l'interface. Pour l'arrêter, utilisez le bouton **⏻ Quitter**.

> **Premier lancement :** l'application n'est pas signée par un certificat payant, donc le système affiche un avertissement.
> - **Windows (SmartScreen) :** cliquez sur *Informations complémentaires*, puis *Exécuter quand même*.
> - **macOS :** faites un clic droit sur l'app, puis *Ouvrir* et *Ouvrir*. Si ça ne suffit pas, allez dans *Réglages Système → Confidentialité et sécurité* et cliquez sur *Ouvrir quand même*.

### 🐍 Depuis le code source (Python 3.10+)

| Windows | macOS / Linux |
|---|---|
| Double-cliquez sur `install.bat`, puis sur `run.bat` | `./install.sh` puis `./run.sh` |

> Sur Debian/Ubuntu, si l'installeur le demande : `sudo apt install python3 python3-venv`

### 🐳 Docker (serveur, NAS…)
```bash
docker compose up -d
# puis ouvrez http://localhost:8765. Les fichiers arrivent dans ./downloads
```

---

## 🏗 Créer les exécutables

### Automatiquement avec GitHub (recommandé, gratuit)
Le fichier `.github/workflows/build.yml` compile Windows, macOS et Linux sur les serveurs de GitHub :

1. Créez un dépôt sur GitHub et envoyez-y ce dossier (`git init`, `git add .`, `git commit -m "OpenVidDL"`, `git push`).
2. Ouvrez l'onglet **Actions** : la compilation démarre seule (environ 10 minutes). Les exécutables sont ensuite téléchargeables dans la section **Artifacts**.
3. Pour une version officielle, créez un tag : `git tag v1.0.0 && git push --tags`. Une **Release** publique est alors créée avec l'installateur `.exe`, le `.dmg` et le binaire Linux.

### Sur votre propre ordinateur
Chaque système ne peut compiler que pour lui-même : le `.exe` se fabrique sous Windows, le `.dmg` sous macOS.

- **Windows :** installez Python 3.10+ et [Inno Setup 6](https://jrsoftware.org/isdl.php), puis double-cliquez sur **`build_windows.bat`**. Le résultat est `dist\OpenVidDL-Setup-x.y.z.exe`.
- **macOS / Linux :** lancez `pip install -r requirements.txt pyinstaller`, puis `python build.py`.

---

## 📖 Utilisation

1. Collez un ou plusieurs liens (un par ligne).
2. Cliquez sur *Aperçu* pour vérifier la vidéo (facultatif).
3. Choisissez le **format** et la **qualité**, puis cliquez sur **Télécharger** (raccourci : Ctrl+Entrée).
4. Les fichiers arrivent dans **`Téléchargements/OpenVidDL`**. Le bouton 📂 *Dossier* l'ouvre directement, et chaque fichier peut aussi être récupéré depuis la liste.

### Options de lancement
| Commande | Effet |
|---|---|
| `run.sh --output ~/Vidéos` | Change le dossier de destination |
| `run.sh --port 9000` | Change le port |
| `run.sh --host 0.0.0.0` | Rend l'application accessible depuis les autres appareils du réseau local, comme votre téléphone (à utiliser uniquement sur un réseau de confiance) |
| `run.sh --no-browser` | N'ouvre pas le navigateur automatiquement |

Sous Windows, remplacez `run.sh` par `run.bat`. Variables d'environnement équivalentes : `OPENVIDDL_DIR`, `OPENVIDDL_PORT`, `OPENVIDDL_HOST`, `OPENVIDDL_PARALLEL`.

---

## 🛠 Dépannage

| Problème | Solution |
|---|---|
| Un site qui marchait ne marche plus / « HTTP Error 403 » | Les sites changent souvent. Cliquez sur **⟳ Mettre à jour**, puis relancez l'application. Cela fonctionne aussi avec la version installée par le .exe, sans réinstaller. |
| « Sign in to confirm », vidéo privée ou 18+ | Connectez-vous au site dans votre navigateur, puis choisissez ce navigateur dans **Cookies**. Fermez Chrome/Edge avant si une erreur de base de données apparaît. |
| « FFmpeg absent » | Relancez l'installation, ou installez FFmpeg vous-même (`winget install ffmpeg`, `brew install ffmpeg`, `sudo apt install ffmpeg`). |
| Netflix, Disney+, Prime Video, Spotify… | Ces contenus sont protégés par DRM : ils ne peuvent pas être téléchargés, et c'est voulu. |

---

## ⚖️ Usage responsable

OpenVidDL est un outil. Ne téléchargez que des contenus dont vous détenez les droits, des contenus sous licence libre, ou des copies autorisées pour un usage privé selon la loi de votre pays. Respectez aussi les conditions d'utilisation des plateformes. Les auteurs déclinent toute responsabilité en cas d'usage abusif.

## 🤝 Contribuer

Tout le code tient dans **`app.py`** (serveur Flask + yt-dlp) et **`templates/index.html`** (interface). La compilation est gérée par `build.py` (PyInstaller) et `installer/OpenVidDL.iss` (Inno Setup). Les *issues* et *pull requests* sont les bienvenues.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 📄 Licence

[MIT](LICENSE). Vous pouvez utiliser, modifier et redistribuer ce code librement.
