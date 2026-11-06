// Usage insights: totals, averages, daily chart, day-by-day history and every entry (edit / delete).
import { api, qs } from "./api.js";
import { barChart } from "./charts.js";
import { icon } from "./icons.js";
import { confirmDialog, esc, fmt, iso, longDate, openModal, shortDate, toast, todayISO, weekday } from "./ui.js";

export const meta = { title: "Usage insights", sub: "Totals, averages and every entry you have recorded.", crumb: "Usage insights" };
const filters = { start: "", end: "", source_id: "", offset: 0 };
const PAGE = 10;

/** Dialog for recording (or editing) one usage entry. Used by the header button too. */
export async function usageModal(ctx, entry = null) {
  const sources = (await api.get(`/api/households/${ctx.state.hid}/sources`)).filter((s) => s.enabled || s.id === entry?.source_id);
  if (!sources.length) { toast("Add a water source first (Devices)", "warn"); return; }
  openModal({
    title: entry ? "Edit usage" : "Log water use",
    submitLabel: entry ? "Save changes" : "Save usage",
    body: `<div class="form-grid">
      <div class="field"><label for="f-usage_date">Date</label><input id="f-usage_date" name="usage_date" type="date" max="${todayISO()}" value="${entry?.usage_date || ctx.state.asOf || todayISO()}" required></div>
      <div class="field"><label for="f-liters">Liters</label><input id="f-liters" name="liters" type="number" min="0" step="0.1" value="${entry ? entry.liters : ""}" placeholder="e.g. 138" required></div>
      <div class="field wide"><label for="f-source_id">Where was it used?</label><select id="f-source_id" name="source_id">${sources.map((s) => `<option value="${s.id}" ${entry?.source_id === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></div>
      <div class="field wide"><label for="f-notes">Notes (optional)</label><input id="f-notes" name="notes" maxlength="200" value="${esc(entry?.notes || "")}"></div></div>`,
    onSubmit: async (v) => {
      const body = { usage_date: v.usage_date, liters: Number(v.liters), source_id: Number(v.source_id), notes: v.notes };
      if (v.liters === "") { const { ApiError } = await import("./api.js"); throw new ApiError(422, { error: { message: "Enter how many liters were used." } }); }
      const res = entry ? await api.put(`/api/usage/${entry.id}`, body) : await api.post(`/api/households/${ctx.state.hid}/usage`, body);
      const alerts = res.alerts_triggered || [];
      toast(alerts.length ? `Saved. Heads up: ${alerts[0].title}` : entry ? "Usage updated" : "Usage recorded", alerts.length ? "warn" : "");
      ctx.reload();
    },
  });
}

const chip = (status) => `<span class="chip ${status === "Over limit" ? "crit" : status === "Near limit" ? "warn" : "ok"}">${esc(status)}</span>`;

export async function show(root, ctx) {
  const hid = ctx.state.hid, end = ctx.state.asOf || todayISO();
  const startDate = new Date(end + "T00:00:00"); startDate.setDate(startDate.getDate() - 29);
  const [summary, daily, history, sources, entries, limits] = await Promise.all([
    api.get(`/api/households/${hid}/usage/summary${qs({ date: ctx.state.asOf })}`),
    api.get(`/api/households/${hid}/usage/daily${qs({ start: iso(startDate), end })}`),
    api.get(`/api/households/${hid}/history${qs({ days: 14, end })}`),
    api.get(`/api/households/${hid}/sources`),
    api.get(`/api/households/${hid}/usage${qs({ start: filters.start, end: filters.end, source_id: filters.source_id, limit: PAGE, offset: filters.offset })}`),
    api.get(`/api/households/${hid}/limits`),
  ]);
  const a = summary.averages;
  const stat = (label, value, hint) => `<div class="card metric"><div class="label"><span>${label}</span></div><p class="big">${value}<small> L</small></p><div class="ctx"><span class="muted">${hint}</span></div></div>`;
  const bars = daily.days.map((d) => ({ date: d.date, label: d.date === end ? "Today" : String(Number(d.date.slice(8))), liters: d.liters, is_today: d.date === end }));
  const histRows = history.days.length ? history.days.map((d) => `<tr><td>${esc(weekday(d.date))}, ${esc(shortDate(d.date))}</td><td class="num"><b>${fmt(d.liters)} L</b></td><td>${chip(d.status)}</td>
      <td class="muted">${d.by_source.slice(0, 3).map((s) => `${esc(s.source)} ${fmt(s.liters)}`).join(" · ")}</td></tr>`).join("")
    : `<tr><td colspan="4"><div class="empty">No usage recorded in the last 14 days.</div></td></tr>`;
  const rows = entries.items.length ? entries.items.map((e) => `<tr><td>${esc(longDate(e.usage_date))}</td>
      <td><span class="chip"><i style="background:${esc(e.source_color)}"></i>${esc(e.source_name)}</span></td><td class="num"><b>${fmt(e.liters, 1)} L</b></td>
      <td class="muted">${esc(e.notes)}</td><td><div class="actions"><button class="icon-btn" data-edit="${e.id}" title="Edit">${icon("pencil", 14)}</button>
      <button class="icon-btn" data-del="${e.id}" title="Delete">${icon("trash-2", 14)}</button></div></td></tr>`).join("")
    : `<tr><td colspan="5"><div class="empty">No entries match. Use “Log usage” to add one.</div></td></tr>`;
  const from = entries.total ? filters.offset + 1 : 0, to = Math.min(filters.offset + PAGE, entries.total);
  root.innerHTML = `
    <div class="stats">${stat("Today", fmt(summary.today.liters), `${summary.today.percent}% of ${fmt(summary.today.limit)} L`)}
      ${stat("Daily average · 7 days", fmt(a.daily_7d), `${a.days_with_data_7d} days with data`)}
      ${stat("Daily average · 30 days", fmt(a.daily_30d), `≈ ${fmt(a.weekly_equivalent)} L per week`)}
      ${stat("Per person · 7 days", fmt(a.per_person_daily_7d, 1), `limit ${fmt(limits.daily_limit_liters)} L per day`)}</div>
    <div class="card"><div class="card-head"><div><h2>Last 30 days</h2><p class="sub">Daily household usage against your ${fmt(limits.daily_limit_liters)} L limit</p></div></div>
      ${barChart({ bars, target: limits.daily_limit_liters })}</div>
    <div class="card"><div class="card-head"><h2>Day by day</h2><span class="sub">Last 14 days</span></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>Day</th><th class="num">Total</th><th>Status</th><th>Biggest sources</th></tr></thead><tbody>${histRows}</tbody></table></div></div>
    <div class="card"><div class="card-head"><h2>All entries</h2><button class="btn primary small" data-log>${icon("plus", 14)}Log usage</button></div>
      <form class="toolbar" data-filter>
        <div class="field"><label for="f-from">From</label><input id="f-from" type="date" name="start" value="${filters.start}"></div>
        <div class="field"><label for="f-to">To</label><input id="f-to" type="date" name="end" value="${filters.end}"></div>
        <div class="field"><label for="f-src">Source</label><select id="f-src" name="source_id"><option value="">All sources</option>${sources.map((s) => `<option value="${s.id}" ${String(s.id) === String(filters.source_id) ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></div>
        <button class="btn" type="submit">Filter</button><button class="btn" type="button" data-clear>Clear</button></form>
      <div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Source</th><th class="num">Liters</th><th>Notes</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="pager"><span>${from}–${to} of ${entries.total}</span><span><button class="btn small" data-page="-1" ${filters.offset === 0 ? "disabled" : ""}>Previous</button>
        <button class="btn small" data-page="1" ${to >= entries.total ? "disabled" : ""}>Next</button></span></div></div>`;

  root.querySelector("[data-log]").addEventListener("click", () => usageModal(ctx));
  root.querySelector("[data-filter]").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    Object.assign(filters, { start: f.get("start"), end: f.get("end"), source_id: f.get("source_id"), offset: 0 });
    ctx.reload();
  });
  root.querySelector("[data-clear]").addEventListener("click", () => { Object.assign(filters, { start: "", end: "", source_id: "", offset: 0 }); ctx.reload(); });
  root.querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", () => { filters.offset = Math.max(0, filters.offset + Number(b.dataset.page) * PAGE); ctx.reload(); }));
  root.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => usageModal(ctx, entries.items.find((e) => e.id === Number(b.dataset.edit)))));
  root.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    const e = entries.items.find((x) => x.id === Number(b.dataset.del));
    if (!(await confirmDialog("Delete this entry?", `${fmt(e.liters, 1)} L of ${e.source_name.toLowerCase()} on ${longDate(e.usage_date)} will be removed.`))) return;
    await api.del(`/api/usage/${e.id}`);
    toast("Entry deleted"); ctx.reload();
  }));
}
