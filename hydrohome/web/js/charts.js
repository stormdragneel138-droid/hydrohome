// Charts drawn with plain HTML/SVG so no chart library is needed. They show whatever the API returns.
import { esc, fmt } from "./ui.js";

/** Daily bars (week / month). chart = dashboard.chart from the API. */
export function barChart(chart) {
  const bars = chart.bars;
  const target = chart.target || 500;
  const max = Math.max(target, ...bars.map((b) => b.liters));
  const scale = Math.min(110 / target, 134 / max);           // 500 L = 110 px, like the Figma file
  const base = 34;                                           // room for the day labels under the bars
  const level = (liters) => base + liters * scale;
  const half = Math.round(target / 2 / 10) * 10;
  const grid = (liters, label, cls = "") =>
    `<div class="grid ${cls}" style="bottom:${level(liters)}px"><b>${label}</b></div>`;
  const cols = bars.map((b) => {
    const h = Math.max(0, b.liters * scale);
    return `<div class="col ${b.is_today ? "is-today" : ""}" title="${esc(b.date)}: ${fmt(b.liters)} L">
      ${b.liters > 0 ? `<span class="val" style="bottom:${level(b.liters) + 3}px">${fmt(b.liters)}</span>` : ""}
      <div class="bar" style="height:${h}px"></div><span class="lab">${esc(b.label)}</span></div>`;
  }).join("");
  return `<div class="chart ${bars.length > 8 ? "dense" : ""}" role="img" aria-label="Daily water use">
    ${grid(0, "0 L")}${grid(half, fmt(half))}${grid(target, fmt(target), "target")}
    <span class="target-label" style="bottom:${level(target) + 3}px">${fmt(target)} L target</span>
    <div class="plot">${cols}</div></div>`;
}

/** Horizontal bars by source (the "Day" view). */
export function sourceBars(bars) {
  if (!bars.length) return `<div class="empty">No water recorded for this day yet.</div>`;
  const max = Math.max(...bars.map((b) => b.liters), 1);
  return `<div class="chart hbars">${bars.map((b) => `
    <div class="hbar"><span>${esc(b.label)}</span>
      <div class="track"><div class="fill" style="width:${(b.liters / max) * 100}%;background:${esc(b.color || "#267e78")}"></div></div>
      <b>${fmt(b.liters)} L</b></div>`).join("")}</div>`;
}

/** Ring chart of the sources. items = [{name, color, liters, percent}] */
export function donut(items, total, caption) {
  const R = 66, C = 2 * Math.PI * R, GAP = items.length > 1 ? 3 : 0;
  let offset = 0;
  const rings = items.filter((i) => i.liters > 0).map((i) => {
    const len = Math.max((i.liters / total) * C - GAP, 0.5);
    const seg = `<circle cx="78" cy="78" r="${R}" fill="none" stroke="${esc(i.color)}" stroke-width="24" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-offset}"><title>${esc(i.name)}: ${fmt(i.liters)} L</title></circle>`;
    offset += (i.liters / total) * C;
    return seg;
  }).join("");
  return `<div class="donut"><svg width="156" height="156" viewBox="0 0 156 156">
      <circle cx="78" cy="78" r="${R}" fill="none" stroke="#eceee6" stroke-width="24"/>${total > 0 ? rings : ""}</svg>
    <div class="center"><b>${fmt(total)}</b><span>${esc(caption)}</span></div></div>`;
}
