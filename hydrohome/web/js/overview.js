// Overview: the screen from the Figma file. Every number below comes from GET /api/households/{id}/dashboard.
import { api, qs } from "./api.js";
import { barChart, donut, sourceBars } from "./charts.js";
import { icon } from "./icons.js";
import { clock, esc, fmt, hourLabel, longDate, money, openModal, toast, weekday } from "./ui.js";
import { scheduleModal } from "./reminders.js";

export const meta = {
  title: "A little awareness. A lot saved.",
  sub: "Keep your household’s water use flowing in the right direction.",
  crumb: "Water overview",
  autoRefresh: true,
};

const ui = { period: "week", sourcePeriod: "today" };
const SCHEDULE_ICON = { "Usage Check-in": "moon", "Garden Watering": "sprout", "Leak Check": "droplet", "Meter Reading": "chart-column" };
const ACTION_LABEL = { high_source: (a) => `Check ${(a.source_name || "it").toLowerCase()}`, limit_exceeded: () => "Review usage", near_limit: () => "Review usage", high_total: () => "Review usage", continuous_flow: () => "Investigate flow" };
const PERIOD_NOUN = { today: "liters today", week: "liters this week", month: "liters this month" };

function todayCard(d) {
  const t = d.today, over = t.status === "Over limit", near = t.status === "Near limit";
  const left = over ? `${fmt(t.liters - t.limit)} L over today’s limit` : `${fmt(t.remaining)} L left for today`;
  return `<div class="card today ${over ? "over" : near ? "near" : ""}">
    <div class="top"><span>Today’s consumption</span><span class="pill"><i></i>${esc(t.status)}</span></div>
    <div class="amount"><p><span class="n">${fmt(t.liters)}</span><span class="u"> L</span><span class="t"> / ${fmt(t.limit)} L target</span></p><span class="p">${t.percent}%</span></div>
    <div><div class="progress"><div style="width:${Math.min(100, t.percent)}%"></div></div>
      <div class="foot"><span class="${over || near ? "" : "good"}">${left}</span><button data-act="edit-target">Edit target ↗</button></div></div></div>`;
}

function yesterdayCard(d) {
  const y = d.yesterday, pct = y.change_percent;
  if (pct === null) {
    return `<div class="card metric"><div class="label"><span>Compared with yesterday</span>${icon("trending-down", 16)}</div>
      <p class="big">—</p><div class="ctx"><span class="muted">No usage was recorded yesterday</span></div></div>`;
  }
  const down = pct <= 0;
  return `<div class="card metric"><div class="label"><span>Compared with yesterday</span>${icon(down ? "trending-down" : "trending-up", 16)}</div>
    <p class="big">${fmt(Math.abs(pct))}<small> % ${down ? "less" : "more"}</small></p>
    <div class="ctx"><span class="${down ? "good" : "bad"}">${down ? "↓" : "↑"} ${fmt(Math.abs(y.difference))} L</span><span class="muted">vs. yesterday’s total</span></div></div>`;
}

function weekCard(d) {
  const w = d.week, pct = w.change_percent;
  const first = weekday(w.start), last = weekday(w.end);
  const span = w.days_elapsed > 1 ? `${first}–${last}` : first;
  const ctx = pct === null ? `<span class="muted">No data for last week yet</span>`
    : `<span class="${pct <= 0 ? "good" : "bad"}">${pct <= 0 ? "↓" : "↑"} ${fmt(Math.abs(pct))}%</span><span class="muted">vs. last ${span}</span>`;
  return `<div class="card metric"><div class="label"><span>This week so far</span>${icon("chart-column", 16)}</div>
    <p class="big">${fmt(w.liters)}<small> L</small></p><div class="ctx">${ctx}</div></div>`;
}

function costCard(d) {
  return `<div class="card metric"><div class="label"><span>Estimated cost today</span>${icon("wallet", 16)}</div>
    <p class="big">${money(d.cost.today, d.cost.currency)}</p>
    <div class="ctx"><span class="good">${money(d.cost.rate_per_1000_l, d.cost.currency)} / 1,000 L</span><span class="muted">local rate</span></div></div>`;
}

function chartCard(d) {
  const c = d.chart;
  const seg = ["day", "week", "month"].map((p) => `<button class="${ui.period === p ? "on" : ""}" data-period="${p}">${p[0].toUpperCase() + p.slice(1)}</button>`).join("");
  const title = { day: "A day in water", week: "A week in water", month: "A month in water" }[ui.period];
  const trend = c.change_percent !== null && c.change_percent > 0.5 ? "trending-up" : "trending-down";
  const body = c.mode === "sources" ? sourceBars(c.bars) : barChart(c);
  return `<div class="card" style="gap:18px;min-height:348px"><div class="card-head">
      <div><h2>${title}</h2><p class="sub">${esc(c.subtitle)}</p></div><div class="seg">${seg}</div></div>
    ${body}<div class="insight">${icon(trend, 15)}<span>${esc(c.insight)}</span></div></div>`;
}

function alertsCard(d) {
  const items = d.alerts.items, n = d.alerts.open_count;
  const [hero, ...rest] = items;
  const heroHtml = hero ? `<div class="alert-hero ${hero.severity}">
      <div class="ttl">${icon("triangle-alert", 17)}<span>${esc(hero.title)}</span></div><p>${esc(hero.message)}</p>
      <div class="actions"><button class="btn primary small" data-ack="${hero.id}">${icon("arrow-up-right", 15)}${esc((ACTION_LABEL[hero.kind] || (() => "Mark as checked"))(hero))}</button>
        <span class="when">Detected ${clock(hero.detected_at)}</span></div></div>` : "";
  const restHtml = rest.map((a) => `<div class="alert-minor">
      <div class="ttl">${icon(a.kind === "continuous_flow" ? "droplet" : "triangle-alert", 16)}<span>${esc(a.title)}</span></div><p>${esc(a.message)}</p>
      <div class="row"><a class="go" href="#/alerts">${a.kind === "continuous_flow" ? "Investigate flow →" : "See details →"}</a>
        <button class="dismiss" data-dismiss="${a.id}">Dismiss</button></div></div>`).join("");
  const none = `<div class="empty">${icon("circle-check", 28)}<b>All clear</b><span>No unusual water use right now.</span></div>`;
  const nf = d.notifications;
  const channels = [nf.push_enabled && "Push", nf.email_enabled && "email"].filter(Boolean).join(" + ");
  return `<div class="card alerts-card" style="min-height:348px"><div class="card-head"><h2>Needs your attention</h2>
      <span class="open-pill ${n ? "" : "none"}">${n ? `${n} open` : "None open"}</span></div>
    ${items.length ? heroHtml + restHtml : none}
    <div class="alert-foot"><span>${channels ? `${channels} notifications on` : "Notifications are off"}</span>
      <a href="#/settings" class="icon-btn" title="Notification settings">${icon("settings-2", 13)}</a></div></div>`;
}

function sourcesCard(d) {
  const s = d.sources, items = s.items, maxPct = Math.max(...items.map((i) => i.percent), 1);
  const opts = [["today", "Today"], ["week", "This week"], ["month", "This month"]]
    .map(([v, l]) => `<option value="${v}" ${s.period === v ? "selected" : ""}>${l}</option>`).join("");
  const legend = items.length ? items.map((i) => `<div class="src"><div class="line">
      <span class="dot" style="background:${esc(i.color)}"></span><span class="nm">${esc(i.name)}</span>
      ${i.flagged ? icon("triangle-alert", 12, "warn-ic") : ""}<span class="l">${fmt(i.liters)} L</span><span class="pc">${i.percent}%</span></div>
      <div class="track"><div class="fill" style="width:${(i.percent / maxPct) * 85}%;background:${esc(i.color)}"></div></div></div>`).join("")
    : `<div class="empty">Nothing recorded for this period.<br>Use “Log usage” to add your first entry.</div>`;
  return `<div class="card" style="gap:22px;min-height:316px"><div class="card-head"><h2>Where your water goes</h2>
      <label class="select-link"><select data-source-period aria-label="Period">${opts}</select>${icon("chevron-down", 13)}</label></div>
    <div class="sources"><div class="donut-wrap">${donut(items, s.total_liters, PERIOD_NOUN[s.period])}<span>${s.connected} connected sources</span></div>
      <div class="legend">${legend}</div></div><p class="foot-note">${esc(s.note)}</p></div>`;
}

function remindersCard(d, user) {
  const r = d.reminders, rows = r.items.slice(0, 3);
  const list = rows.length ? rows.map((s) => `<div class="sched-row ${s.enabled ? "" : "off"}">
      <div class="sched-icon">${icon(SCHEDULE_ICON[s.reminder_type] || "bell", 16)}</div>
      <div class="body"><span class="t">${esc(s.title)}</span><span class="m">${esc(s.description)}</span></div>
      <button class="icon-btn" data-edit="${s.id}" title="Edit reminder">${icon("pencil", 13)}</button>
      <button class="toggle ${s.enabled ? "on" : ""}" data-toggle="${s.id}" role="switch" aria-checked="${s.enabled}" aria-label="Turn ${esc(s.title)} on or off"></button></div>`).join("")
    : `<div class="empty">No reminders yet.<br>Add one to build a saving habit.</div>`;
  const next = r.next;
  const nextBox = next ? `<button class="next-box" data-next>${icon("clock-3", 17)}<span class="col"><span class="cap">NEXT REMINDER</span>
      <span class="line"><span>${esc(next.when)}</span><span class="m">${esc(next.description.split(" · ")[0].replace("Every day", "Daily"))}</span>${icon("chevron-down", 12)}</span></span></button>
      <div class="next-list" data-next-list hidden>${r.upcoming.map((u) => `<div><span>${esc(u.title)}</span><span class="muted">${esc(u.when)}</span></div>`).join("")}</div>` : "";
  const quiet = `Quiet hours ${hourLabel(d.notifications.quiet_start)}–${hourLabel(d.notifications.quiet_end)}`;
  const first = (user.name || "your").split(" ")[0];
  return `<div class="card" style="min-height:316px"><div class="card-head"><h2>Make saving a habit</h2>
      <button class="link-btn" data-add-reminder>${icon("plus", 14)}Add reminder</button></div>
    <div class="sched">${list}</div>${r.items.length > 3 ? `<a class="link-btn" href="#/reminders">See all ${r.items.length} reminders →</a>` : ""}
    ${nextBox}<div class="delivery">${icon("smartphone", 12)}<span>Reminders are sent to ${esc(first)}’s phone · ${quiet}</span></div></div>`;
}

function tipBanner(d) {
  const t = d.tip;
  return `<div class="tip"><div class="ico">${icon("sprout", 27)}</div>
    <div class="body"><span class="eyebrow">${esc(t.eyebrow)}</span><span class="head">${esc(t.title)}</span><span class="text">${esc(t.text)}</span></div>
    <div class="save"><b>${esc(t.savings)}</b><span>${esc(t.savings_label)}</span></div>
    <button class="btn" data-tips>${icon("arrow-up-right", 15)}Explore saving tips</button></div>`;
}

export async function show(root, ctx) {
  const { state, reload } = ctx;
  const d = await api.get(`/api/households/${state.hid}/dashboard${qs({ period: ui.period, source_period: ui.sourcePeriod, date: state.asOf })}`);
  ctx.setUpdated(new Date(d.generated_at.replace(" ", "T")));
  root.innerHTML = `
    <div class="snapshot">${todayCard(d)}${yesterdayCard(d)}${weekCard(d)}${costCard(d)}</div>
    <div class="two-col">${chartCard(d)}${alertsCard(d)}</div>
    <div class="half">${sourcesCard(d)}${remindersCard(d, state.user)}</div>
    ${tipBanner(d)}
    <div class="footer-info"><span data-updated>Updated just now · Readings refresh every 60 seconds</span>
      <span>All usage in liters (L) · Showing ${esc(longDate(d.date))}</span></div>`;

  root.querySelectorAll("[data-period]").forEach((b) => b.addEventListener("click", () => { ui.period = b.dataset.period; reload(); }));
  root.querySelector("[data-source-period]").addEventListener("change", (e) => { ui.sourcePeriod = e.target.value; reload(); });
  root.querySelector("[data-act=edit-target]").addEventListener("click", () => editTarget(d, reload));
  root.querySelectorAll("[data-ack]").forEach((b) => b.addEventListener("click", async () => {
    await api.put(`/api/alerts/${b.dataset.ack}`, { status: "acknowledged" });
    toast("Marked as checked"); reload();
  }));
  root.querySelectorAll("[data-dismiss]").forEach((b) => b.addEventListener("click", async () => {
    await api.put(`/api/alerts/${b.dataset.dismiss}`, { status: "dismissed" });
    toast("Alert dismissed"); reload();
  }));
  root.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
    const row = d.reminders.items.find((s) => s.id === Number(b.dataset.toggle));
    await api.put(`/api/schedules/${row.id}`, { enabled: !row.enabled });
    toast(row.enabled ? "Reminder turned off" : "Reminder turned on"); reload();
  }));
  root.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () =>
    scheduleModal(ctx, d.reminders.items.find((s) => s.id === Number(b.dataset.edit)))));
  root.querySelector("[data-add-reminder]").addEventListener("click", () => scheduleModal(ctx));
  const nextBtn = root.querySelector("[data-next]");
  if (nextBtn) nextBtn.addEventListener("click", () => root.querySelector("[data-next-list]").toggleAttribute("hidden"));
  root.querySelector("[data-tips]").addEventListener("click", () => openModal({
    title: "Ways to save water", cancelLabel: "Close",
    body: `<ul class="tips">${d.all_tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`,
  }));
}

function editTarget(d, reload) {
  const l = d.limits;
  openModal({
    title: "Edit daily target",
    body: `<div class="form-grid">
      <div class="field"><label for="f-daily">Daily limit (L)</label><input id="f-daily" name="daily_limit_liters" type="number" min="10" step="1" value="${l.daily_limit_liters}" required><span class="hint">The whole household, per day.</span></div>
      <div class="field"><label for="f-weekly">Weekly limit (L)</label><input id="f-weekly" name="weekly_limit_liters" type="number" min="10" step="1" value="${l.weekly_limit_liters}" required></div></div>`,
    onSubmit: async (v) => {
      await api.put(`/api/households/${d.household.id}/limits`, { daily_limit_liters: Number(v.daily_limit_liters), weekly_limit_liters: Number(v.weekly_limit_liters) });
      toast("Target updated"); reload();
    },
  });
}
