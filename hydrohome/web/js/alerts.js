// Alerts view: every high-usage alert and reminder notification, with actions.
import { api } from "./api.js";
import { icon } from "./icons.js";
import { clock, confirmDialog, esc, fmt, longDate, openModal, toast } from "./ui.js";

export const meta = { title: "Alerts", sub: "Unusual water use, limit warnings and reminder notifications.", crumb: "Alerts", autoRefresh: true };
const view = { status: "active" };
const TABS = [["active", "Open"], ["all", "All"], ["dismissed", "Dismissed"], ["resolved", "Resolved"]];

const sev = (a) => a.severity === "critical" ? "crit" : a.severity === "warning" ? "warn" : "info";
const kindName = { limit_exceeded: "Limit exceeded", near_limit: "Near limit", high_source: "High source", high_total: "High total", continuous_flow: "Continuous flow", reminder: "Reminder" };

export async function show(root, ctx) {
  const hid = ctx.state.hid;
  const data = await api.get(`/api/households/${hid}/alerts?status=${view.status}&limit=100`);
  const rows = data.items.length ? data.items.map((a) => `<div class="list-row">
      <div class="sched-icon" style="${a.severity === "info" ? "" : "background:var(--warn-bg);color:var(--warn)"}">${icon(a.kind === "reminder" ? "bell" : a.kind === "continuous_flow" ? "droplet" : "triangle-alert", 17)}</div>
      <div class="body"><div class="t">${esc(a.title)}</div><div class="m">${esc(a.message)}</div>
        <div class="m"><span class="chip ${sev(a)}">${esc(kindName[a.kind] || a.kind)}</span> <span class="chip info">${esc(a.status)}</span>
        ${esc(longDate(a.usage_date))} · ${clock(a.detected_at)}${a.liters ? ` · ${fmt(a.liters)} L` : ""}</div></div>
      <div class="actions" style="display:flex;gap:6px">
        ${a.status === "open" ? `<button class="btn small" data-set="${a.id}:acknowledged">Mark checked</button><button class="btn small" data-set="${a.id}:dismissed">Dismiss</button>` : `<button class="btn small" data-set="${a.id}:open">Reopen</button>`}
        <button class="icon-btn" data-del="${a.id}" title="Delete">${icon("trash-2", 14)}</button></div></div>`).join("")
    : `<div class="empty">${icon("circle-check", 28)}<b>Nothing here</b><span>No alerts match this filter.</span></div>`;
  root.innerHTML = `<div class="card"><div class="card-head"><div class="tabs">${TABS.map(([v, l]) => `<button class="${view.status === v ? "on" : ""}" data-tab="${v}">${l}</button>`).join("")}</div>
      <div style="display:flex;gap:8px"><button class="btn small" data-flow>${icon("droplet", 14)}Report running water</button><button class="btn small" data-scan>${icon("refresh-cw", 14)}Scan today</button>
      <button class="btn small" data-read>${icon("check", 14)}Mark all read</button></div></div>${rows}</div>`;
  root.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { view.status = b.dataset.tab; ctx.reload(); }));
  root.querySelectorAll("[data-set]").forEach((b) => b.addEventListener("click", async () => {
    const [id, status] = b.dataset.set.split(":");
    await api.put(`/api/alerts/${id}`, { status }); ctx.reload(); ctx.refreshShell();
  }));
  root.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDialog("Delete alert?", "It will be removed from the history."))) return;
    await api.del(`/api/alerts/${b.dataset.del}`); ctx.reload(); ctx.refreshShell();
  }));
  root.querySelector("[data-read]").addEventListener("click", async () => { await api.post(`/api/households/${hid}/alerts/mark-read`); toast("All marked as read"); ctx.reload(); ctx.refreshShell(); });
  root.querySelector("[data-scan]").addEventListener("click", async () => {
    const r = await api.post(`/api/households/${hid}/alerts/scan${ctx.state.asOf ? `?date=${ctx.state.asOf}` : ""}`);
    toast(r.alerts.length ? `${r.alerts.length} alert(s) active for ${r.date}` : "Nothing unusual found", r.alerts.length ? "warn" : "");
    ctx.reload(); ctx.refreshShell();
  });
  root.querySelector("[data-flow]").addEventListener("click", () => openModal({
    title: "Report running water", submitLabel: "Check for a leak",
    body: `<p class="muted">Enter what your main meter shows. Water that runs for 20+ minutes raises an alert.</p><div class="form-grid">
      <div class="field"><label for="f-flow">Flow (L/min)</label><input id="f-flow" name="flow_lpm" type="number" min="0.1" step="0.1" value="1.8" required></div>
      <div class="field"><label for="f-min">Running for (minutes)</label><input id="f-min" name="minutes" type="number" min="1" step="1" value="25" required></div></div>`,
    onSubmit: async (v) => {
      const r = await api.post(`/api/households/${hid}/flow-events`, { flow_lpm: Number(v.flow_lpm), minutes: Number(v.minutes) });
      toast(r.detected ? "Continuous flow alert raised" : "That looks normal: no alert needed");
      ctx.reload(); ctx.refreshShell();
    },
  }));
}
