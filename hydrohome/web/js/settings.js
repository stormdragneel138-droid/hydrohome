// Settings: household details, consumption limits, notifications, account.
import { api } from "./api.js";
import { esc, errorText, field, openModal, confirmDialog, toast } from "./ui.js";

export const meta = { title: "Settings", sub: "Limits, notifications and your account.", crumb: "Settings", autoRefresh: false };

function saveForm(form, action, okText) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector("[type=submit]"), err = form.querySelector(".form-error");
    btn.disabled = true; err.hidden = true;
    try { await action(Object.fromEntries(new FormData(form)), form); toast(okText); }
    catch (ex) { const t = errorText(ex); err.innerHTML = esc(t.message) + (t.details.length ? `<ul>${t.details.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : ""); err.hidden = false; }
    finally { btn.disabled = false; }
  });
}
const errBox = `<div class="form-error" hidden></div>`;
const save = `<div><button class="btn primary" type="submit">Save changes</button></div>`;

export async function show(root, ctx) {
  const hid = ctx.state.hid;
  const [hh, notif, loose] = await Promise.all([api.get(`/api/households/${hid}`), api.get(`/api/households/${hid}/notification-settings`), api.get("/api/households/unclaimed")]);
  const l = hh.limits;
  root.innerHTML = `<div class="half" style="align-items:start">
    <div style="display:flex;flex-direction:column;gap:24px">
      <form class="card" novalidate data-f="household"><h2>Household</h2>${errBox}<div class="form-grid">
        ${field("Name", "name", hh.name, "required maxlength=60")}${field("City", "city", hh.city, "required maxlength=60")}
        ${field("Address", "address", hh.address, "maxlength=120")}${field("Members", "members", hh.members, "type=number min=1 max=30 required")}</div>${save}</form>
      <form class="card" novalidate data-f="limits"><h2>Limits &amp; cost</h2>${errBox}<div class="form-grid">
        ${field("Daily limit (L)", "daily_limit_liters", l.daily_limit_liters, "type=number min=10 step=1 required", "Whole household, per day")}
        ${field("Weekly limit (L)", "weekly_limit_liters", l.weekly_limit_liters, "type=number min=10 step=1 required")}
        ${field("Alert at (% of daily limit)", "alert_threshold_pct", l.alert_threshold_pct, "type=number min=50 max=100 required", "Warn when usage reaches this share")}
        ${field("Unusual-use multiplier", "spike_multiplier", l.spike_multiplier, "type=number min=1.1 max=10 step=0.1 required", "1.5 = flag use 50% above usual")}
        ${field("Water rate (per 1,000 L)", "rate_per_1000_l", l.rate_per_1000_l, "type=number min=0 step=0.01 required")}${field("Currency symbol", "currency", l.currency, "maxlength=3 required")}</div>${save}</form></div>
    <div style="display:flex;flex-direction:column;gap:24px">
      <form class="card" novalidate data-f="notif"><h2>Notifications</h2>${errBox}<div class="form-grid">
        <div class="field"><label><input type="checkbox" name="push_enabled" ${notif.push_enabled ? "checked" : ""}> Push notifications</label></div>
        <div class="field"><label><input type="checkbox" name="email_enabled" ${notif.email_enabled ? "checked" : ""}> Email notifications</label></div>
        ${field("Quiet hours start", "quiet_start", notif.quiet_start, "type=time required")}${field("Quiet hours end", "quiet_end", notif.quiet_end, "type=time required")}</div>
        <p class="foot-note">Reminders are held back during quiet hours and sent when they end.</p>${save}</form>
      <form class="card" novalidate data-f="account"><h2>Account</h2>${errBox}${field("Your name", "name", ctx.state.user.name, "required maxlength=60")}
        <p class="foot-note">${esc(ctx.state.user.email)}</p><div style="display:flex;gap:10px"><button class="btn primary" type="submit">Save name</button><button class="btn" type="button" data-pw>Change password</button></div></form>
      ${loose.length ? `<div class="card"><h2>Households from the desktop app</h2><p class="foot-note">These have no owner yet. Claim one to manage it here.</p>
        ${loose.map((h) => `<div class="list-row"><div class="body"><div class="t">${esc(h.name)}</div><div class="m">${esc(h.city)} · ${h.members} members</div></div><button class="btn small" data-claim="${h.id}">Claim</button></div>`).join("")}</div>` : ""}
      <div class="card"><h2>Danger zone</h2><p class="foot-note">Deleting a household removes its usage, alerts and reminders for good.</p>
        <div><button class="btn danger" data-delete>Delete “${esc(hh.name)}”</button></div></div></div></div>`;
  const f = (n) => root.querySelector(`[data-f=${n}]`);
  saveForm(f("household"), async (v) => { await api.put(`/api/households/${hid}`, { name: v.name, city: v.city, address: v.address, members: Number(v.members) }); ctx.refreshShell(true); }, "Household saved");
  saveForm(f("limits"), (v) => api.put(`/api/households/${hid}/limits`, { daily_limit_liters: Number(v.daily_limit_liters), weekly_limit_liters: Number(v.weekly_limit_liters), alert_threshold_pct: Number(v.alert_threshold_pct), spike_multiplier: Number(v.spike_multiplier), rate_per_1000_l: Number(v.rate_per_1000_l), currency: v.currency }), "Limits saved");
  saveForm(f("notif"), (v) => api.put(`/api/households/${hid}/notification-settings`, { push_enabled: "push_enabled" in v, email_enabled: "email_enabled" in v, quiet_start: v.quiet_start, quiet_end: v.quiet_end }), "Notification settings saved");
  saveForm(f("account"), async (v) => { ctx.state.user = await api.put("/api/auth/me", { name: v.name }); ctx.refreshShell(); }, "Name updated");
  root.querySelector("[data-pw]").addEventListener("click", () => openModal({
    title: "Change password", submitLabel: "Change password",
    body: `<div class="form-grid"><div class="field wide"><label for="f-cp">Current password</label><input id="f-cp" name="current_password" type="password" autocomplete="current-password" required></div>
      <div class="field wide"><label for="f-np">New password</label><input id="f-np" name="new_password" type="password" minlength="8" autocomplete="new-password" required><span class="hint">At least 8 characters.</span></div></div>`,
    onSubmit: async (v) => { await api.put("/api/auth/password", v); toast("Password changed"); },
  }));
  root.querySelectorAll("[data-claim]").forEach((b) => b.addEventListener("click", async () => {
    await api.post(`/api/households/${b.dataset.claim}/claim`); toast("Household claimed"); await ctx.reloadHouseholds(Number(b.dataset.claim));
  }));
  root.querySelector("[data-delete]").addEventListener("click", async () => {
    if (!(await confirmDialog("Delete this household?", `“${hh.name}” and everything recorded for it will be permanently deleted.`))) return;
    await api.del(`/api/households/${hid}`); toast("Household deleted"); await ctx.reloadHouseholds();
  });
}
