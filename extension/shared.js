// Code commun à la fenêtre (popup) et à l'arrière-plan de l'extension.
// Fonctionne avec Chrome, Edge, Brave, Opera, Vivaldi (API chrome.*) et Firefox (API browser.*).
"use strict";

var ext = globalThis.browser ?? globalThis.chrome;

var OVD = {
  DEFAULTS: { server: "http://127.0.0.1:8765", format: "mp4", quality: "best", subtitles: false, cookies: "" },
  LAUNCH_URL: "openviddl://start",
  INSTALL_URL: "https://github.com/AliouSignate/OpenVidDL",
  AUDIO: ["mp3", "m4a", "opus", "flac", "wav", "ogg"],
  ACTIVE: ["queued", "starting", "downloading", "processing"],

  async settings() {
    const s = await ext.storage.local.get(OVD.DEFAULTS);
    return { ...OVD.DEFAULTS, ...s };
  },

  async base() {
    return (await OVD.settings()).server.replace(/\/+$/, "");
  },

  /** Appel à l'application OpenVidDL locale. */
  async call(path, { method = "GET", body, timeout = 8000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const r = await fetch((await OVD.base()) + path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      let data = {};
      try { data = await r.json(); } catch (_) { /* réponse vide */ }
      if (!r.ok) throw new Error(data.error || `Erreur ${r.status}`);
      return data;
    } finally {
      clearTimeout(timer);
    }
  },

  async status() {
    try { return await OVD.call("/api/status", { timeout: 1500 }); } catch (_) { return null; }
  },

  async download(urls, opts = {}) {
    const s = await OVD.settings();
    return OVD.call("/api/download", {
      method: "POST",
      body: {
        urls,
        format: opts.format || s.format,
        quality: opts.quality || s.quality,
        subtitles: opts.subtitles ?? s.subtitles,
        playlist: !!opts.playlist,
        cookies: opts.cookies ?? s.cookies,
      },
    });
  },

  /** Le lien openviddl:// n'existe qu'avec l'installateur Windows et l'app macOS. */
  async canLaunch() {
    try {
      const { os } = await ext.runtime.getPlatformInfo();
      return os === "win" || os === "mac";
    } catch (_) {
      return false;
    }
  },

  isDownloadable(url) {
    return /^https?:\/\//i.test(url || "") && !/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//i.test(url);
  },

  async waitOnline(ms = 25000) {
    const end = Date.now() + ms;
    while (Date.now() < end) {
      if (await OVD.status()) return true;
      await new Promise((r) => setTimeout(r, 1000));
    }
    return false;
  },
};
