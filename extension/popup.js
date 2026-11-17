"use strict";

const $ = (id) => document.getElementById(id);
const STATUS = {
  queued: "En attente", starting: "Analyse…", downloading: "Téléchargement", processing: "Traitement",
  done: "Terminé ✓", error: "Échec", cancelled: "Annulé",
};
let timer = null;

function msg(text, kind = "err") {
  const m = $("msg");
  m.hidden = !text;
  m.className = "msg " + kind;
  m.textContent = text || "";
}

function setMsg(text, kind = "err") {
  const m = $("setMsg");
  m.hidden = !text;
  m.className = "msg " + kind;
  m.textContent = text || "";
}

function setState(on) {
  $("state").className = "state " + (on ? "on" : "off");
  $("state").querySelector("b").textContent = on ? "prête" : "éteinte";
  $("online").hidden = !on;
  $("offline").hidden = on;
}

function fmtSpeed(b) {
  if (!b) return "";
  const u = ["o/s", "Ko/s", "Mo/s", "Go/s"];
  let i = 0;
  while (b >= 1024 && i < 3) { b /= 1024; i++; }
  return b.toFixed(1) + " " + u[i];
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function renderJobs(jobs) {
  const box = $("jobs");
  box.replaceChildren();
  for (const j of jobs.slice(0, 4)) {
    const card = el("div", "job " + j.status);
    card.appendChild(el("div", "t", j.title || j.url));
    const bar = el("div", "bar"), fill = el("i");
    fill.style.width = (["done", "error"].includes(j.status) ? 100 : (j.progress || 3)) + "%";
    bar.appendChild(fill);
    card.appendChild(bar);
    const line = el("div", "l");
    line.appendChild(el("span", "st-" + j.status, STATUS[j.status] || j.status));
    let right = j.format || "";
    if (j.status === "downloading" && j.progress != null) right = `${j.progress.toFixed(0)} % · ${fmtSpeed(j.speed)}`;
    if (j.status === "processing" && j.stage) right = j.stage;
    line.appendChild(el("span", null, right));
    card.appendChild(line);
    if (j.status === "error" && j.error) card.title = j.error;
    box.appendChild(card);
  }
}

async function refresh() {
  clearTimeout(timer);
  const st = await OVD.status();
  setState(!!st);
  let active = false;
  if (st) {
    try {
      const jobs = await OVD.call("/api/jobs", { timeout: 3000 });
      renderJobs(jobs);
      active = jobs.some((j) => OVD.ACTIVE.includes(j.status));
    } catch (_) { /* ignore */ }
  }
  timer = setTimeout(refresh, active ? 900 : 2500);
}

async function init() {
  const s = await OVD.settings();
  $("format").value = s.format;
  $("quality").value = s.quality;
  $("subtitles").checked = !!s.subtitles;
  $("server").value = s.server;
  $("cookies").value = s.cookies || "";
  $("lnkInstall").href = OVD.INSTALL_URL;
  $("quality").disabled = OVD.AUDIO.includes(s.format);

  // Page courante
  try {
    const [tab] = await ext.tabs.query({ active: true, currentWindow: true });
    if (tab && OVD.isDownloadable(tab.url)) {
      $("url").value = tab.url;
      $("pageTitle").textContent = tab.title || tab.url;
      $("pageHost").textContent = new URL(tab.url).hostname.replace(/^www\./, "");
      $("playlist").checked = /[?&]list=|\/playlist|\/sets\//i.test(tab.url) && !/[?&]v=/.test(tab.url);
    } else {
      $("pageTitle").textContent = "Cette page ne contient pas de lien téléchargeable";
      $("pageHost").textContent = "Collez un lien ci-dessous.";
    }
  } catch (_) { /* pas d'accès à l'onglet */ }

  if (!(await OVD.canLaunch())) {
    $("btnStart").hidden = true;
    $("startHint").hidden = false;
    $("startHint").textContent = "Lancez l'application OpenVidDL depuis votre menu d'applications, puis rouvrez cette fenêtre.";
  }
  refresh();
}

async function saveDefaults() {
  await ext.storage.local.set({
    format: $("format").value,
    quality: $("quality").value,
    subtitles: $("subtitles").checked,
  });
}

$("format").addEventListener("change", () => {
  $("quality").disabled = OVD.AUDIO.includes($("format").value);
  saveDefaults();
});
$("quality").addEventListener("change", saveDefaults);
$("subtitles").addEventListener("change", saveDefaults);

$("btnGo").addEventListener("click", async () => {
  const url = $("url").value.trim();
  if (!OVD.isDownloadable(url)) return msg("Lien invalide : il doit commencer par http:// ou https://");
  msg("");
  $("btnGo").disabled = true;
  try {
    const { ids } = await OVD.download([url], {
      format: $("format").value,
      quality: $("quality").value,
      subtitles: $("subtitles").checked,
      playlist: $("playlist").checked,
    });
    await ext.runtime.sendMessage({ type: "watch", ids }).catch(() => {});
    msg("Téléchargement lancé ! Vous serez prévenu à la fin, même si cette fenêtre est fermée.", "ok");
    refresh();
  } catch (e) {
    msg(e.message);
  }
  $("btnGo").disabled = false;
});

$("btnStart").addEventListener("click", async () => {
  $("btnStart").disabled = true;
  $("btnStart").textContent = "Démarrage…";
  try {
    const [tab] = await ext.tabs.query({ active: true, currentWindow: true });
    await ext.tabs.update(tab.id, { url: OVD.LAUNCH_URL });
  } catch (_) { /* refusé par le navigateur */ }
  const ok = await OVD.waitOnline(20000);
  $("btnStart").disabled = false;
  $("btnStart").textContent = "▶ Démarrer OpenVidDL";
  if (!ok) {
    $("startHint").hidden = false;
    $("startHint").textContent = "L'application n'a pas répondu. Est-elle installée ? Vous pouvez aussi la lancer depuis le menu Démarrer / Applications.";
  }
  refresh();
});

$("btnApp").addEventListener("click", async () => ext.tabs.create({ url: await OVD.base() }));
$("btnFolder").addEventListener("click", async () => {
  try { await OVD.call("/api/open-folder", { method: "POST" }); } catch (e) { msg(e.message); }
});

$("btnSave").addEventListener("click", async () => {
  let server = $("server").value.trim().replace(/\/+$/, "") || OVD.DEFAULTS.server;
  if (!/^https?:\/\/[^/]+$/i.test(server)) return setMsg("Adresse invalide (exemple : http://127.0.0.1:8765)");
  const host = new URL(server).hostname;
  if (!["127.0.0.1", "localhost"].includes(host)) {
    // Application sur un autre appareil du réseau : permission supplémentaire nécessaire
    // (sans numéro de port : Firefox ne l'accepte pas, et le motif couvre alors tous les ports)
    const granted = await ext.permissions.request({ origins: [`http://${host}/*`] }).catch(() => false);
    if (!granted) return setMsg("Permission refusée pour " + server);
  }
  await ext.storage.local.set({ server, cookies: $("cookies").value });
  await saveDefaults();
  setMsg("Réglages enregistrés ✓", "ok");
  refresh();
});

init();
