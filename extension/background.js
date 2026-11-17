// Arrière-plan : menu du clic droit, notifications de fin et badge de l'icône.
// Chrome charge ce fichier comme « service worker », Firefox comme script d'arrière-plan.
"use strict";

if (typeof OVD === "undefined" && typeof importScripts === "function") {
  importScripts("shared.js");
}

const MENU = [
  { id: "ovd-mp4", title: "Vidéo MP4 (meilleure qualité)", opts: { format: "mp4", quality: "best" } },
  { id: "ovd-mp4-720", title: "Vidéo MP4 720p (plus léger)", opts: { format: "mp4", quality: "720" } },
  { id: "ovd-mp3", title: "Audio MP3", opts: { format: "mp3" } },
  { id: "ovd-default", title: "Avec mes réglages par défaut", opts: {} },
];

function buildMenus() {
  // Promesse sous Chrome (MV3) comme sous Firefox : pas de callback, pour rester compatible
  Promise.resolve(ext.contextMenus.removeAll()).then(() => {
    const contexts = ["page", "link", "video", "audio", "frame"];
    ext.contextMenus.create({ id: "ovd-root", title: "Télécharger avec OpenVidDL", contexts });
    for (const m of MENU) ext.contextMenus.create({ id: m.id, parentId: "ovd-root", title: m.title, contexts });
    ext.contextMenus.create({ id: "ovd-sep", parentId: "ovd-root", type: "separator", contexts });
    ext.contextMenus.create({ id: "ovd-open", parentId: "ovd-root", title: "Ouvrir OpenVidDL", contexts });
  });
}

ext.runtime.onInstalled.addListener(buildMenus);
ext.runtime.onStartup.addListener(() => { buildMenus(); refreshBadge(); });

function notify(title, message, id) {
  ext.notifications.create(id || "", {
    type: "basic",
    iconUrl: ext.runtime.getURL("icons/icon128.png"),
    title,
    message,
  });
}

ext.notifications.onClicked.addListener(async () => {
  ext.tabs.create({ url: await OVD.base() });
});

/** Choisit la meilleure adresse à envoyer : lien cliqué, lecteur intégré (iframe), sinon la page. */
function pickUrl(info, tab) {
  for (const u of [info.linkUrl, info.frameUrl, info.srcUrl, info.pageUrl, tab && tab.url]) {
    if (OVD.isDownloadable(u)) return u;
  }
  return null;
}

ext.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "ovd-open") {
    if (await OVD.status()) ext.tabs.create({ url: await OVD.base() });
    else await startApp(tab);
    return;
  }
  const item = MENU.find((m) => m.id === info.menuItemId);
  if (!item) return;
  const url = pickUrl(info, tab);
  if (!url) return notify("OpenVidDL", "Aucun lien téléchargeable ici.");
  await send([url], item.opts, tab);
});

/** Démarre l'application via le lien openviddl:// (Windows / macOS) puis attend qu'elle réponde. */
async function startApp(tab) {
  if (!(await OVD.canLaunch())) {
    notify("OpenVidDL n'est pas lancé", "Démarrez l'application OpenVidDL puis réessayez.");
    return false;
  }
  try {
    if (tab && tab.id != null) await ext.tabs.update(tab.id, { url: OVD.LAUNCH_URL });
  } catch (_) { /* le navigateur peut refuser : on attend quand même */ }
  const ok = await OVD.waitOnline(25000);
  if (!ok) notify("OpenVidDL ne répond pas", "Lancez l'application OpenVidDL (ou installez-la), puis réessayez.");
  return ok;
}

async function send(urls, opts, tab) {
  if (!(await OVD.status())) {
    notify("OpenVidDL", "Démarrage de l'application…");
    if (!(await startApp(tab))) return;
  }
  try {
    const { ids } = await OVD.download(urls, opts);
    await watch(ids);
    notify("Téléchargement lancé", urls.length > 1 ? `${urls.length} liens envoyés.` : urls[0]);
  } catch (e) {
    notify("Échec", e.message);
  }
}

// --------------------------------------------------------------- suivi des téléchargements
async function watch(ids) {
  const { watched = [] } = await ext.storage.local.get({ watched: [] });
  await ext.storage.local.set({ watched: [...new Set([...watched, ...ids])] });
  ext.alarms.create("ovd-poll", { periodInMinutes: 0.5 });
  poll();
}

let polling = false;
async function poll() {
  if (polling) return;
  polling = true;
  try {
    for (let i = 0; i < 600; i++) {  // ~20 minutes maximum par boucle (l'alarme relance ensuite)
      const more = await refreshBadge(true);
      if (!more) break;
      await new Promise((r) => setTimeout(r, 2000));
    }
  } finally {
    polling = false;
  }
}

/** Met à jour le badge (nombre de téléchargements en cours) et notifie les téléchargements finis. */
async function refreshBadge(notifyDone = false) {
  let jobs;
  try { jobs = await OVD.call("/api/jobs", { timeout: 3000 }); } catch (_) {
    ext.action.setBadgeText({ text: "" });
    return false;
  }
  const active = jobs.filter((j) => OVD.ACTIVE.includes(j.status)).length;
  ext.action.setBadgeBackgroundColor({ color: "#4f8cff" });
  ext.action.setBadgeText({ text: active ? String(active) : "" });

  const { watched = [] } = await ext.storage.local.get({ watched: [] });
  if (!watched.length) {
    ext.alarms.clear("ovd-poll");
    return active > 0;
  }
  const left = [];
  for (const id of watched) {
    const j = jobs.find((x) => x.id === id);
    if (!j) continue;
    if (OVD.ACTIVE.includes(j.status)) { left.push(id); continue; }
    if (!notifyDone) { left.push(id); continue; }
    if (j.status === "done") notify("Téléchargement terminé ✓", j.title || (j.files[0] && j.files[0].name) || j.url, "done-" + id);
    else if (j.status === "error") notify("Échec du téléchargement", (j.title || j.url) + "\n" + (j.error || "").split("\n")[0], "err-" + id);
  }
  await ext.storage.local.set({ watched: left });
  if (!left.length) ext.alarms.clear("ovd-poll");
  return left.length > 0 || active > 0;
}

ext.alarms.onAlarm.addListener((a) => { if (a.name === "ovd-poll") poll(); });

// Messages depuis la fenêtre de l'extension
ext.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg && msg.type === "watch") { watch(msg.ids).then(() => reply({ ok: true })); return true; }
  if (msg && msg.type === "badge") { refreshBadge().then(() => reply({ ok: true })); return true; }
  return false;
});
