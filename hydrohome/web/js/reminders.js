// Reminders view + the add/edit schedule dialog (also opened from the Overview card).
import { api } from "./api.js";
import { icon } from "./icons.js";
import { confirmDialog, esc, openModal, toast } from "./ui.js";

export const meta = { title: "Reminders", sub: "Gentle nudges that turn water saving into a habit.", crumb: "Reminders" };

const DAYS = [["mon", "Mon"], ["tue", "Tue"], ["wed", "Wed"], ["thu", "Thu"], ["fri", "Fri"], ["sat", "Sat"], ["sun", "Sun"]];
const ICON = { "Usage Check-in": "moon", "Garden Watering": "sprout", "Leak Check": "droplet", "Meter Reading": "chart-column" };

export async function scheduleModal(ctx, existing = null) {
  const opts = await api.get("/api/reminder-options");
  const picked = !existing || existing.days === "daily" ? DAYS.map((d) => d[0]) : existing.days.split(",");
  const select = (name, list, value) => `<select id="f-${name}" name="${name}">${list.map((o) => `<option ${o === value ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
  const { form } = openModal({
    title: existing ? "Edit reminder" : "Add reminder",
    submitLabel: existing ? "Save changes" : "Add reminder",
    extra: existing ? `<button type="button" class="btn danger" data-delete style="margin-right:auto">Delete</button>` : "",
    body: `<div class="form-grid">
      <div class="field wide"><label for="f-title">Title</label><input id="f-title" name="title" maxlength="80" required value="${esc(existing?.title || "")}" placeholder="Evening usage check-in"></div>
      <div class="field"><label for="f-reminder_type">Type</label>${select("reminder_type", opts.types, existing?.reminder_type || "Usage Check-in")}</div>
      <div class="field"><label for="f-time_of_day">Time</label><input id="f-time_of_day" name="time_of_day" type="time" required value="${esc(existing?.time_of_day || "20:00")}"></div>
      <div class="field wide"><label>Repeat on</label><div class="days">${DAYS.map(([v, l]) => `<label class="${picked.includes(v) ? "on" : ""}"><input type="checkbox" name="day_${v}" ${picked.includes(v) ? "checked" : ""}>${l}</label>`).join("")}</div></div>
      <div class="field"><label for="f-channel">Delivery</label>${select("channel", opts.channels, existing?.channel || "Push notification")}</div>
      <div class="field"><label for="f-enabled">Status</label><select id="f-enabled" name="enabled"><option value="true" ${existing?.enabled === false ? "" : "selected"}>On</option><option value="false" ${existing?.enabled === false ? "selected" : ""}>Off</option></select></div>
      <div class="field wide"><label for="f-notes">Message (optional)</label><input id="f-notes" name="notes" maxlength="200" value="${esc(existing?.notes || "")}" placeholder="Shown in the notification"></div></div>`,
    onSubmit: async (v) => {
      const days = DAYS.map(([d]) => d).filter((d) => v[`day_${d}`]);
      const body = { title: v.title, reminder_type: v.reminder_type, time_of_day: v.time_of_day, channel: v.channel,
        notes: v.notes, enabled: v.enabled === "true", days: days.length === 7 ? "daily" : days };
      if (!days.length) { const { ApiError } = await import("./api.js"); throw new ApiError(422, { error: { message: "Choose at least one day." } }); }
      if (existing) await api.put(`/api/schedules/${existing.id}`, body);
      else await api.post(`/api/households/${ctx.state.hid}/schedules`, body);
      toast(existing ? "Reminder updated" : "Reminder added");
      ctx.reload();
    },
  });
  form.querySelectorAll(".days input").forEach((i) => i.addEventListener("change", () => i.parentElement.classList.toggle("on", i.checked)));
  const del = form.querySelector("[data-delete]");
  if (del) del.addEventListener("click", async () => {
    if (!(await confirmDialog("Delete reminder?", `“${existing.title}” will stop sending notifications.`))) return;
    await api.del(`/api/schedules/${existing.id}`);
    document.querySelector(".backdrop")?.remove();
    toast("Reminder deleted"); ctx.reload();
  });
}

export async function show(root, ctx) {
  const [items, upcoming] = await Promise.all([
    api.get(`/api/households/${ctx.state.hid}/schedules`),
    api.get(`/api/households/${ctx.state.hid}/schedules/upcoming`),
  ]);
  const rows = items.length ? items.map((s) => `<div class="list-row">
      <div class="sched-icon">${icon(ICON[s.reminder_type] || "bell", 16)}</div>
      <div class="body"><div class="t">${esc(s.title)}</div>
        <div class="m">${esc(s.description)}${s.next_run ? ` · next ${esc(s.next_run)}` : ""}${s.notes ? `<br>${esc(s.notes)}` : ""}</div></div>
      <button class="icon-btn" data-edit="${s.id}" title="Edit">${icon("pencil", 14)}</button>
      <button class="toggle ${s.enabled ? "on" : ""}" data-toggle="${s.id}" role="switch" aria-checked="${s.enabled}" aria-label="Turn ${esc(s.title)} on or off"></button></div>`).join("")
    : `<div class="empty">No reminders yet. Add one to get a nudge at the right time.</div>`;
  root.innerHTML = `<div class="two-col">
    <div class="card"><div class="card-head"><h2>Your reminders</h2><button class="btn primary small" data-add>${icon("plus", 14)}Add reminder</button></div>${rows}</div>
    <div class="card"><div class="card-head"><h2>Coming up</h2></div>
      ${upcoming.length ? upcoming.map((u) => `<div class="list-row"><div class="body"><div class="t">${esc(u.title)}</div><div class="m">${esc(u.when)} · ${esc(u.channel)}</div></div></div>`).join("") : `<div class="empty">Nothing scheduled.</div>`}
      <button class="btn" data-check style="margin-top:auto">${icon("refresh-cw", 14)}Check for due reminders now</button>
      <p class="foot-note">The server checks every 30 seconds by itself. Quiet hours are respected.</p></div></div>`;
  root.querySelector("[data-add]").addEventListener("click", () => scheduleModal(ctx));
  root.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => scheduleModal(ctx, items.find((s) => s.id === Number(b.dataset.edit)))));
  root.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
    const s = items.find((x) => x.id === Number(b.dataset.toggle));
    await api.put(`/api/schedules/${s.id}`, { enabled: !s.enabled });
    toast(s.enabled ? "Reminder turned off" : "Reminder turned on"); ctx.reload();
  }));
  root.querySelector("[data-check]").addEventListener("click", async () => {
    const r = await api.post(`/api/households/${ctx.state.hid}/schedules/check-due`);
    toast(r.fired.length ? `${r.fired.length} reminder(s) sent: ${r.fired.map((f) => f.title).join(", ")}` : "No reminders are due right now");
    ctx.refreshShell();
  });
}
