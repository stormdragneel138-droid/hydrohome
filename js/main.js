// App shell: sign-in, sidebar, header, router, household switcher, notifications bell, auto-refresh.
import { api, ApiError, session } from "./api.js";
import { icon } from "./icons.js";
import { clock, errorText, esc, field, longDate, openModal, timeAgo, toast, todayISO } from "./ui.js";
import * as overview from "./overview.js";
import * as usage from "./usage.js";
import * as alerts from "./alerts.js";
import * as reminders from "./reminders.js";
import * as devices from "./devices.js";
import * as settings from "./settings.js";
import * as notify from "./notify.js";

const BRAND = "HydroHome";            // the name used in the Figma design; change it here
const REFRESH_MS = 60_000;           // dashboard re-reads the API this often
const NAV = [
  ["overview", "Overview", "layout-dashboard", overview], ["usage", "Usage insights", "chart-no-axes-combined", usage],
  ["alerts", "Alerts", "bell", alerts], ["reminders", "Reminders", "clock-3", reminders], ["devices", "Devices", "radio", devices],
];
const VIEWS = Object.fromEntries([...NAV.map(([k, , , m]) => [k, m]), ["settings", settings]]);

let installEvt = null;
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installEvt = e; const b = document.querySelector("[data-install]"); if (b) b.hidden = false; });
window.addEventListener("appinstalled", () => { installEvt = null; });
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));

const state = { user: null, households: [], hid: null, asOf: null, route: "overview" };
let pushSynced = false, renderId = 0, lastUpdated = null, shellData = { counts: { open_attention: 0, unread: 0 }, recent: [], sources: [], online: true };
const $ = (sel, el = document) => el.querySelector(sel);
const app = document.getElementById("app");

const ctx = {
  state,
  reload: () => renderView(),
  refreshShell: (full = false) => (full ? reloadHouseholds(state.hid) : refreshShell()),
  setUpdated: (d) => { lastUpdated = d; },
  reloadHouseholds: (id) => reloadHouseholds(id),
};

window.addEventListener("unhandledrejection", (e) => { e.preventDefault(); toast(errorText(e.reason).message, "error"); });
window.addEventListener("hydrohome:signed-out", () => { state.user = null; renderAuth("login"); });
window.addEventListener("hashchange", () => { if (state.user && state.hid) { routeFromHash(); renderView(); updateNavAndHeader(); } });

// ------------------------------------------------------------------ sign in
function renderAuth(mode) {
  const register = mode === "register";
  app.innerHTML = `<div class="auth"><div class="auth-card">
    <div class="brand">${icon("droplets", 28)}<span>${BRAND}</span></div>
    <div><h1>${register ? "Create your account" : "Welcome back"}</h1><p class="muted" style="margin-top:6px">Household Water Consumption Reminder System</p></div>
    <form novalidate><div class="form-error" hidden></div>
      ${register ? field("Your name", "name", "", 'autocomplete=name required maxlength=60') : ""}
      ${field("Email", "email", "", "type=email autocomplete=email required")}
      ${field("Password", "password", "", `type=password required minlength=8 autocomplete=${register ? "new-password" : "current-password"}`, register ? "At least 8 characters." : "")}
      <button class="btn primary" type="submit" style="padding:12px">${register ? "Create account" : "Sign in"}</button></form>
    <p class="switch">${register ? "Already have an account?" : "New here?"} <button data-switch>${register ? "Sign in" : "Create an account"}</button></p></div></div>`;
  $("[data-switch]").addEventListener("click", () => renderAuth(register ? "login" : "register"));
  $("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = Object.fromEntries(new FormData(e.target)), box = $(".form-error"), btn = $("[type=submit]");
    btn.disabled = true; box.hidden = true;
    try {
      const res = await api.post(register ? "/api/auth/register" : "/api/auth/login", v);
      session.set(res.token); state.user = res.user;
      await start();
    } catch (err) {
      const t = errorText(err);
      box.innerHTML = esc(t.message) + (t.details.length ? `<ul>${t.details.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : "");
      box.hidden = false; btn.disabled = false;
    }
  });
}

// ------------------------------------------------------------------- shell
const currentHousehold = () => state.households.find((h) => h.id === state.hid);
const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");

function renderShell() {
  app.innerHTML = `<div class="app">
    <aside class="sidebar">
      <div class="brand">${icon("droplets", 28)}<span>${BRAND}</span></div>
      <div class="switcher-wrap"><button class="switcher" data-switcher aria-haspopup="true">${icon("house", 18)}
        <span class="meta"><span class="name" data-hh-name></span><span class="sub" data-hh-sub></span></span>${icon("chevrons-up-down", 14)}</button>
        <div class="menu" data-switcher-menu hidden></div></div>
      <nav class="nav" aria-label="Main"><span class="nav-label">MENU</span>
        ${NAV.map(([k, label, ic]) => `<a class="nav-item" href="#/${k}" data-nav="${k}">${icon(ic, 18)}<span class="grow">${label}</span>${k === "alerts" ? `<span class="badge" data-badge hidden></span>` : ""}</a>`).join("")}</nav>
      <div class="spacer"></div>
      <div class="status-card" data-status></div>
      <div class="account"><a class="nav-item settings-link" href="#/settings" data-nav="settings" style="padding-left:12px">${icon("settings-2", 18)}<span>Settings</span></a>
        <div class="divider"></div>
        <button class="profile" data-profile><span class="avatar">${esc(initials(state.user.name))}</span>
          <span class="meta"><span class="name">${esc(state.user.name)}</span><span class="role" data-role></span></span>${icon("chevron-down", 14)}</button>
        <div class="menu" data-profile-menu hidden><button data-install hidden>${icon("download", 15)}Install app</button><button data-signout>${icon("log-out", 15)}Sign out</button></div></div>
    </aside>
    <main class="main">
      <header class="page-header"><div class="intro"><div class="crumbs"><span data-crumb-hh></span>${icon("chevron-right", 12)}<span class="here" data-crumb></span></div>
          <h1 class="page-title" data-title></h1><p class="page-sub" data-sub></p></div>
        <div class="controls">
          <label class="btn date-btn">${icon("calendar-days", 15)}<span data-date-label></span>${icon("chevron-down", 13)}<input type="date" data-date aria-label="Choose a date"></label>
          <button class="btn primary" data-log>${icon("plus", 15)}Log usage</button>
          <button class="btn" data-export>${icon("download", 15)}Export</button>
          <button class="btn square" data-bell aria-label="Notifications">${icon("bell", 17)}<span class="dot" data-dot hidden></span></button>
          <div class="panel" data-panel hidden></div></div></header>
      <section id="view" style="display:flex;flex-direction:column;gap:24px"></section></main></div>`;
  $("[data-switcher]").addEventListener("click", (e) => { e.stopPropagation(); toggleMenu("[data-switcher-menu]", renderSwitcherMenu); });
  $("[data-profile]").addEventListener("click", (e) => { e.stopPropagation(); toggleMenu("[data-profile-menu]"); });
  $("[data-install]").addEventListener("click", async () => { if (!installEvt) return; installEvt.prompt(); await installEvt.userChoice; installEvt = null; $("[data-install]").hidden = true; });
  if (installEvt) $("[data-install]").hidden = false;
  $("[data-signout]").addEventListener("click", async () => { try { await api.post("/api/auth/logout"); } catch { /* already invalid */ } session.clear(); state.user = null; renderAuth("login"); });
  $("[data-bell]").addEventListener("click", (e) => { e.stopPropagation(); const p = $("[data-panel]"); p.hidden = !p.hidden; if (!p.hidden) renderPanel(); });
  $("[data-panel]").addEventListener("click", (e) => e.stopPropagation());
  $("[data-log]").addEventListener("click", async () => (await import("./usage.js")).usageModal(ctx));
  $("[data-export]").addEventListener("click", async () => { await api.download(`/api/households/${state.hid}/export.csv`, "water-usage.csv"); toast("Usage exported as CSV"); });
  const dateInput = $("[data-date]");
  dateInput.max = todayISO();
  dateInput.addEventListener("click", () => dateInput.showPicker?.());
  dateInput.addEventListener("change", () => { state.asOf = dateInput.value && dateInput.value !== todayISO() ? dateInput.value : null; updateNavAndHeader(); renderView(); });
  document.addEventListener("click", closeMenus);
}

function toggleMenu(sel, fill) { const m = $(sel); const open = m.hidden; closeMenus(); if (open) { fill?.(m); m.hidden = false; } }
function closeMenus() { document.querySelectorAll(".menu, .panel").forEach((m) => { m.hidden = true; }); }

function renderSwitcherMenu(menu) {
  menu.innerHTML = `${state.households.map((h) => `<button data-pick="${h.id}" class="${h.id === state.hid ? "current" : ""}">${icon("house", 15)}${esc(h.name)}</button>`).join("")}<hr><button data-new>${icon("plus", 15)}Add household</button>`;
  menu.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => { selectHousehold(Number(b.dataset.pick)); }));
  $("[data-new]", menu).addEventListener("click", () => householdModal());
}

function householdModal() {
  openModal({
    title: "Add household", submitLabel: "Create household",
    body: `<div class="form-grid">${field("Name", "name", "", "required maxlength=60")}${field("City", "city", "", "required maxlength=60")}
      ${field("Address", "address", "", "maxlength=120")}${field("Members", "members", "4", "type=number min=1 max=30 required")}
      ${field("Daily limit (L)", "daily_limit_liters", "500", "type=number min=10 step=1 required", "The whole household, per day")}</div>`,
    onSubmit: async (v) => {
      const h = await api.post("/api/households", { name: v.name, city: v.city, address: v.address, members: Number(v.members), daily_limit_liters: Number(v.daily_limit_liters) });
      toast("Household created"); await reloadHouseholds(h.id);
    },
  });
}

function selectHousehold(id) {
  state.hid = id; state.asOf = null;
  try { localStorage.setItem("hydrohome.hid", String(id)); } catch { /* ignore */ }
  updateNavAndHeader(); refreshShell(); renderView();
}

async function reloadHouseholds(preferId) {
  state.households = await api.get("/api/households");
  let saved = null;
  try { saved = Number(localStorage.getItem("hydrohome.hid")); } catch { /* ignore */ }
  const wanted = [preferId, state.hid, saved].find((id) => state.households.some((h) => h.id === id));
  state.hid = wanted ?? state.households[0]?.id ?? null;
  if (state.hid === null) return renderEmpty();
  if (!$(".app")) renderShell();
  routeFromHash(); updateNavAndHeader(); refreshShell(); renderView();
}

async function renderEmpty() {
  const loose = await api.get("/api/households/unclaimed").catch(() => []);
  app.innerHTML = `<div class="auth"><div class="auth-card"><div class="brand">${icon("droplets", 28)}<span>${BRAND}</span></div>
    <div><h1>Let’s set up your home</h1><p class="muted" style="margin-top:6px">Create a household to start tracking water use.</p></div>
    <button class="btn primary" data-new style="padding:12px">${icon("plus", 15)}Create a household</button>
    ${loose.length ? `<div class="divider"></div><p class="muted">Or claim one made in the desktop app:</p>${loose.map((h) => `<button class="btn" data-claim="${h.id}">${esc(h.name)} · ${esc(h.city)}</button>`).join("")}` : ""}
    <p class="switch"><button data-out>Sign out</button></p></div></div>`;
  $("[data-new]").addEventListener("click", householdModal);
  document.querySelectorAll("[data-claim]").forEach((b) => b.addEventListener("click", async () => { await api.post(`/api/households/${b.dataset.claim}/claim`); await reloadHouseholds(Number(b.dataset.claim)); }));
  $("[data-out]").addEventListener("click", () => { session.clear(); state.user = null; renderAuth("login"); });
}

function routeFromHash() {
  const key = location.hash.replace(/^#\/?/, "").split(/[/?]/)[0];
  state.route = VIEWS[key] ? key : "overview";
}

function updateNavAndHeader() {
  const hh = currentHousehold(), meta = VIEWS[state.route].meta;
  if (!hh || !$(".app")) return;
  $("[data-hh-name]").textContent = hh.name;
  $("[data-hh-sub]").textContent = `${hh.members} member${hh.members === 1 ? "" : "s"} · ${hh.city}`;
  $("[data-role]").textContent = hh.role === "admin" ? "Home admin" : "Member";
  $("[data-crumb-hh]").textContent = hh.name;
  $("[data-crumb]").textContent = state.route === "overview" ? "Water overview" : meta.crumb;
  $("[data-title]").textContent = meta.title;
  $("[data-sub]").textContent = meta.sub;
  $("[data-date-label]").textContent = longDate(state.asOf || todayISO());
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === state.route));
  document.title = `${meta.crumb} · ${BRAND}`;
}

async function refreshShell() {
  if (!state.hid || !$(".app")) return;
  try {
    const [al, src] = await Promise.all([api.get(`/api/households/${state.hid}/alerts?status=all&limit=8`), api.get(`/api/households/${state.hid}/sources`)]);
    shellData = { counts: al.counts, recent: al.items.filter((a) => a.status !== "resolved"), sources: src, online: true };
  } catch (err) {
    if (err instanceof ApiError && err.status === 0) shellData.online = false;
  }
  notify.notifyNew(state.hid, shellData.recent).catch(() => {});
  if (!pushSynced) { pushSynced = true; notify.syncPush(); }
  const badge = $("[data-badge]"), n = shellData.counts.open_attention;
  badge.hidden = !n; badge.textContent = n;
  $("[data-dot]").hidden = !shellData.counts.unread;
  const on = shellData.sources.filter((s) => s.enabled).length;
  $("[data-status]").className = `status-card ${shellData.online ? "" : "offline"}`;
  $("[data-status]").innerHTML = shellData.online
    ? `<div class="row teal">${icon("wifi", 15)}<span>Home is connected</span></div><span class="detail">Main meter + ${on} source sensor${on === 1 ? "" : "s"}</span><a class="link" href="#/devices">${icon("arrow-up-right", 13)}Manage devices</a>`
    : `<div class="row">${icon("wifi", 15)}<span>Server not reachable</span></div><span class="detail">Check that run_api.py is still running.</span>`;
  if (!$("[data-panel]").hidden) renderPanel();
}

function renderPanel() {
  const items = shellData.recent;
  $("[data-panel]").innerHTML = `<h3>Notifications <button class="link-btn" data-readall>Mark all read</button></h3>
    ${items.length ? items.map((a) => `<div class="note-row ${a.is_read ? "" : "unread"}"><div><div class="t">${esc(a.title)}</div><div class="m">${esc(a.message)}</div><div class="m">${clock(a.detected_at)}</div></div></div>`).join("") : `<div class="empty">You’re all caught up.</div>`}
    ${notify.permission() === "granted" ? `<button class="btn small" data-test-push style="margin-top:8px">Send a test notification</button>` : ""}
    ${notify.supported() && notify.permission() !== "granted" ? `<button class="btn small" data-enable-push style="margin-top:8px">${notify.permission() === "denied" ? "Notifications blocked in browser settings" : "Turn on push notifications"}</button>` : ""}
    <a class="link-btn" href="#/alerts" style="margin-top:6px">See all alerts →</a>`;
  $("[data-enable-push]")?.addEventListener("click", async () => { const r = await notify.enable(); toast(r === "granted" ? "Notifications turned on" : "Notifications not allowed", r === "granted" ? "" : "warn"); renderPanel(); });
  $("[data-test-push]")?.addEventListener("click", async () => { await notify.syncPush(); const r = await notify.sendTest(); toast(r.sent ? "Test sent: it should pop up in a moment" : "No device registered yet. Try again in a few seconds.", r.sent ? "" : "warn"); });
  $("[data-readall]").addEventListener("click", async () => { await api.post(`/api/households/${state.hid}/alerts/mark-read`); await refreshShell(); });
}

// -------------------------------------------------------------------- views
async function renderView(quiet = false) {
  const id = ++renderId, root = $("#view");
  if (!root || !state.hid) return;
  if (!quiet) root.innerHTML = `<div class="loading">${icon("refresh-cw", 22, "spin")}</div>`;
  const staging = document.createElement("div");
  try {
    await VIEWS[state.route].show(staging, ctx);
    if (id !== renderId) return;                       // a newer render started: drop this one
    root.replaceChildren(...staging.childNodes);
    tickUpdated();
  } catch (err) {
    if (id !== renderId || quiet) return;
    const t = errorText(err);
    root.innerHTML = `<div class="card"><div class="empty"><b>Couldn’t load this page</b><span>${esc(t.message)}</span><button class="btn" data-retry>Try again</button></div></div>`;
    $("[data-retry]").addEventListener("click", () => renderView());
  }
  refreshShell();
}

function tickUpdated() {
  const el = $("[data-updated]");
  if (el && lastUpdated) el.textContent = `Updated ${timeAgo(lastUpdated)} · Readings refresh every 60 seconds`;
}

setInterval(tickUpdated, 15_000);
setInterval(() => {
  if (!state.user || !state.hid || document.hidden || document.querySelector(".backdrop")) return;
  if (VIEWS[state.route].meta.autoRefresh) renderView(true); else refreshShell();
}, REFRESH_MS);

// -------------------------------------------------------------------- start
async function start() {
  await reloadHouseholds();
}

(async function boot() {
  if (!session.token) return renderAuth("login");
  try { state.user = await api.get("/api/auth/me"); await start(); }
  catch (err) {
    if (err instanceof ApiError && err.status === 0) app.innerHTML = `<div class="auth"><div class="auth-card"><h1>Server not reachable</h1><p class="muted">Start it with <code>python run_api.py</code> and reload this page.</p></div></div>`;
    else renderAuth("login");
  }
})();
