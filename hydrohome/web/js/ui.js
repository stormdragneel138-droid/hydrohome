// Small helpers shared by every view: escaping, formatting, toasts and modal dialogs.
import { ApiError } from "./api.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const fmt = (n, digits = 0) => Number(n ?? 0).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
export const money = (n, cur = "$") => `${cur}${Number(n ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const todayISO = () => iso(new Date());
const parse = (s) => { const [y, m, d] = s.slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); };
export const longDate = (s) => parse(s).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
export const shortDate = (s) => parse(s).toLocaleDateString("en-US", { month: "short", day: "numeric" });
export const weekday = (s) => parse(s).toLocaleDateString("en-US", { weekday: "short" });

export function clock(datetimeText) {            // "2026-11-05 12:42:10" -> "12:42 PM"
  const [h, m] = datetimeText.slice(11, 16).split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}
export function hourLabel(hhmm) {                // "22:00" -> "10 PM", "06:30" -> "6:30 AM"
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}${m ? ":" + String(m).padStart(2, "0") : ""} ${h < 12 ? "AM" : "PM"}`;
}
export function timeAgo(date) {
  const s = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  return m < 60 ? `${m} min ago` : `${Math.round(m / 60)} h ago`;
}

export function toast(message, kind = "") {
  let box = document.querySelector(".toasts");
  if (!box) { box = document.createElement("div"); box.className = "toasts"; document.body.append(box); }
  const el = Object.assign(document.createElement("div"), { className: `toast ${kind}`, textContent: message });
  box.append(el);
  setTimeout(() => el.remove(), 4200);
}

export function errorText(err) {
  if (err instanceof ApiError) return { message: err.message, details: err.details.length > 1 ? err.details : [] };
  console.error(err);
  return { message: "Something went wrong. Please try again.", details: [] };
}

/** Read a <form> into a plain object (checkboxes become booleans, numbers stay strings). */
export function formValues(form) {
  const out = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    out[el.name] = el.type === "checkbox" ? el.checked : el.value;
  }
  return out;
}

/** Open a modal form. onSubmit(values, form) may throw ApiError: the message is shown inside the dialog. */
export function openModal({ title, body, submitLabel = "Save", cancelLabel = "Cancel", onSubmit, danger = false, extra = "" }) {
  const backdrop = document.createElement("div");
  backdrop.className = "backdrop";
  backdrop.innerHTML = `
    <form class="modal" novalidate>
      <h2>${esc(title)}</h2>
      <div class="form-error" hidden></div>
      ${body}
      <div class="btns">${extra}<button type="button" class="btn" data-close>${esc(cancelLabel)}</button>
        ${onSubmit ? `<button type="submit" class="btn ${danger ? "danger" : "primary"}">${esc(submitLabel)}</button>` : ""}</div>
    </form>`;
  const form = backdrop.querySelector("form");
  const errorBox = backdrop.querySelector(".form-error");
  const close = () => { backdrop.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  backdrop.addEventListener("mousedown", (e) => { if (e.target === backdrop) close(); });
  backdrop.querySelector("[data-close]").addEventListener("click", close);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!onSubmit) return close();
    const submit = form.querySelector("[type=submit]");
    submit.disabled = true;
    errorBox.hidden = true;
    try {
      await onSubmit(formValues(form), form, close);
      close();
    } catch (err) {
      const { message, details } = errorText(err);
      errorBox.innerHTML = esc(message) + (details.length ? `<ul>${details.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : "");
      errorBox.hidden = false;
      submit.disabled = false;
    }
  });
  document.body.append(backdrop);
  const first = form.querySelector("input:not([type=hidden]), select, textarea");
  if (first) first.focus();
  return { close, form };
}

export function confirmDialog(title, message, label = "Delete") {
  return new Promise((resolve) => {
    let answered = false;
    const { close } = openModal({
      title, body: `<p>${esc(message)}</p>`, submitLabel: label, danger: true,
      onSubmit: async () => { answered = true; resolve(true); },
    });
    const watch = setInterval(() => {
      if (!document.querySelector(".backdrop")) { clearInterval(watch); if (!answered) resolve(false); }
    }, 150);
    void close;
  });
}

export const field = (label, name, value = "", attrs = "", hint = "") =>
  `<div class="field"><label for="f-${name}">${esc(label)}</label><input id="f-${name}" name="${name}" value="${esc(value)}" ${attrs}>${hint ? `<span class="hint">${esc(hint)}</span>` : ""}</div>`;
