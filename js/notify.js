import { api } from "./api.js";

// Browser notifications for new alerts. Works while the dashboard is open (or in the background tab/PWA).
const KEY = (hid) => `hydrohome.seenAlerts.${hid}`;
let reg = null;

export const supported = () => "Notification" in window;
export const permission = () => (supported() ? Notification.permission : "unsupported");

export async function enable() {
  if (!supported()) return "unsupported";
  const result = await Notification.requestPermission();
  await ensureWorker();
  if (result === "granted") await syncPush();
  return result;
}

const toKey = (b64) => {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};
const sameKey = (buf, key) => buf && buf.byteLength === key.length && new Uint8Array(buf).every((v, i) => v === key[i]);

// Registers this browser for real push (works when the dashboard is closed). Safe to call often.
export async function syncPush() {
  if (permission() !== "granted" || !("PushManager" in window)) return false;
  try {
    const worker = await ensureWorker();
    if (!worker) return false;
    await navigator.serviceWorker.ready;
    const { public_key } = await api.get("/api/push/key");
    const key = toKey(public_key);
    let sub = await worker.pushManager.getSubscription();
    if (sub && !sameKey(sub.options.applicationServerKey, key)) { await sub.unsubscribe(); sub = null; }  // server keys changed
    if (!sub) sub = await worker.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    const j = sub.toJSON();
    await api.post("/api/push/subscribe", { endpoint: j.endpoint, keys: j.keys });
    return true;
  } catch { return false; }
}

export async function sendTest() { return api.post("/api/push/test"); }

async function ensureWorker() {
  if (reg || !("serviceWorker" in navigator)) return reg;
  try { reg = await navigator.serviceWorker.register("/sw.js"); } catch { reg = null; }
  return reg;
}

function readSeen(hid) { try { return JSON.parse(localStorage.getItem(KEY(hid)) || "null"); } catch { return null; } }
function writeSeen(hid, ids) { try { localStorage.setItem(KEY(hid), JSON.stringify(ids.slice(-200))); } catch { /* storage blocked */ } }

async function show(a) {
  const options = { body: a.message, tag: `alert-${a.id}`, icon: "/icons/icon-192.png", requireInteraction: a.severity === "critical" };
  const worker = await ensureWorker();
  if (worker && worker.showNotification) { await worker.showNotification(a.title, options); return; }
  new Notification(a.title, options);
}

// Call after every alert refresh. The first call only records existing alerts (no flood of old ones).
export async function notifyNew(hid, alerts) {
  const open = alerts.filter((a) => a.status === "open");
  const seen = readSeen(hid);
  const ids = open.map((a) => a.id);
  if (seen === null) { writeSeen(hid, ids); return; }
  const fresh = open.filter((a) => !seen.includes(a.id));
  if (fresh.length) writeSeen(hid, [...seen, ...ids.filter((i) => !seen.includes(i))]);
  if (permission() !== "granted") return;
  for (const a of fresh.slice(0, 3)) await show(a);
}
