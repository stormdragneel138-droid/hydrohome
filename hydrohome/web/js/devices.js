// Devices: water sources (sensors) and the main-meter readings recorded by the desktop app.
import { api } from "./api.js";
import { icon } from "./icons.js";
import { confirmDialog, esc, fmt, longDate, openModal, toast, todayISO } from "./ui.js";

export const meta = { title: "Devices", sub: "The sources your water is tracked by, and your main meter.", crumb: "Devices", autoRefresh: false };

function sourceModal(ctx, s = null) {
  openModal({
    title: s ? "Edit source" : "Add water source", submitLabel: s ? "Save changes" : "Add source",
    body: `<div class="form-grid"><div class="field"><label for="f-name">Name</label><input id="f-name" name="name" maxlength="40" required value="${esc(s?.name || "")}" placeholder="Pool"></div>
      <div class="field"><label for="f-color">Chart colour</label><input id="f-color" name="color" type="color" value="${esc(s?.color || "#267e78")}"></div></div>`,
    onSubmit: async (v) => {
      if (s) await api.put(`/api/sources/${s.id}`, { name: v.name, color: v.color });
      else await api.post(`/api/households/${ctx.state.hid}/sources`, { name: v.name, color: v.color });
      toast(s ? "Source updated" : "Source added"); ctx.reload(); ctx.refreshShell();
    },
  });
}

function readingModal(ctx, r = null) {
  openModal({
    title: r ? "Edit meter reading" : "Add meter reading", submitLabel: "Save reading",
    body: `<div class="form-grid"><div class="field"><label for="f-date">Date</label><input id="f-date" name="reading_date" type="date" max="${todayISO()}" required value="${r?.reading_date || todayISO()}"></div>
      <div class="field"><label for="f-m3">Meter reading (m³)</label><input id="f-m3" name="meter_reading" type="number" step="0.001" min="0" required value="${r?.meter_reading ?? ""}"><span class="hint">Cumulative value; it can never go down.</span></div>
      <div class="field wide"><label for="f-n">Notes</label><input id="f-n" name="notes" maxlength="200" value="${esc(r?.notes || "")}"></div></div>`,
    onSubmit: async (v) => {
      const body = { reading_date: v.reading_date, meter_reading: Number(v.meter_reading), notes: v.notes };
      if (r) await api.put(`/api/meter-readings/${r.id}`, body);
      else await api.post(`/api/households/${ctx.state.hid}/meter-readings`, body);
      toast("Meter reading saved"); ctx.reload();
    },
  });
}

export async function show(root, ctx) {
  const hid = ctx.state.hid;
  const [sources, readings] = await Promise.all([api.get(`/api/households/${hid}/sources`), api.get(`/api/households/${hid}/meter-readings`)]);
  const active = sources.filter((s) => s.enabled).length;
  const srcRows = sources.map((s) => `<div class="list-row"><span class="swatch" style="background:${esc(s.color)}"></span>
      <div class="body"><div class="t">${esc(s.name)}</div><div class="m">${fmt(s.today_liters)} L today · ${s.enabled ? "connected" : "disabled"}</div></div>
      <button class="icon-btn" data-edit="${s.id}" title="Edit">${icon("pencil", 14)}</button>
      <button class="icon-btn" data-del="${s.id}" title="Delete">${icon("trash-2", 14)}</button>
      <button class="toggle ${s.enabled ? "on" : ""}" data-toggle="${s.id}" role="switch" aria-checked="${s.enabled}" aria-label="Turn ${esc(s.name)} on or off"></button></div>`).join("");
  const readRows = readings.length ? readings.map((r) => `<tr><td>${esc(longDate(r.reading_date))}</td><td class="num"><b>${fmt(r.meter_reading, 3)} m³</b></td>
      <td class="num">${r.used_m3 === null ? "—" : fmt(r.used_m3, 3) + " m³"}</td><td class="muted">${esc(r.status)}</td>
      <td><div class="actions"><button class="icon-btn" data-redit="${r.id}">${icon("pencil", 14)}</button><button class="icon-btn" data-rdel="${r.id}">${icon("trash-2", 14)}</button></div></td></tr>`).join("")
    : `<tr><td colspan="5"><div class="empty">No meter readings yet.</div></td></tr>`;
  root.innerHTML = `<div class="half" style="align-items:start">
    <div class="card"><div class="card-head"><div><h2>Water sources</h2><p class="sub">${active} of ${sources.length} connected · main meter + ${active} source sensors</p></div>
      <button class="btn primary small" data-add>${icon("plus", 14)}Add source</button></div>${srcRows}</div>
    <div class="card"><div class="card-head"><div><h2>Main meter readings</h2><p class="sub">Shared with the desktop app</p></div><button class="btn small" data-radd>${icon("plus", 14)}Add reading</button></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th class="num">Meter</th><th class="num">Used</th><th>Status</th><th></th></tr></thead><tbody>${readRows}</tbody></table></div></div></div>`;
  root.querySelector("[data-add]").addEventListener("click", () => sourceModal(ctx));
  root.querySelector("[data-radd]").addEventListener("click", () => readingModal(ctx));
  root.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => sourceModal(ctx, sources.find((s) => s.id === Number(b.dataset.edit)))));
  root.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
    const s = sources.find((x) => x.id === Number(b.dataset.toggle));
    await api.put(`/api/sources/${s.id}`, { enabled: !s.enabled }); ctx.reload(); ctx.refreshShell();
  }));
  root.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    const s = sources.find((x) => x.id === Number(b.dataset.del));
    if (!(await confirmDialog("Delete source?", `“${s.name}” will be removed. Sources with usage entries can only be disabled.`))) return;
    await api.del(`/api/sources/${s.id}`); toast("Source deleted"); ctx.reload(); ctx.refreshShell();
  }));
  root.querySelectorAll("[data-redit]").forEach((b) => b.addEventListener("click", () => readingModal(ctx, readings.find((r) => r.id === Number(b.dataset.redit)))));
  root.querySelectorAll("[data-rdel]").forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDialog("Delete reading?", "This meter reading will be removed."))) return;
    await api.del(`/api/meter-readings/${b.dataset.rdel}`); ctx.reload();
  }));
}
