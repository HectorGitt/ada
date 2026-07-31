// Web Push enrollment from the browser side: register the service worker, ask permission,
// subscribe with our VAPID key, and hand the subscription to the backend. Every step is
// capability-guarded so this is a no-op on browsers (or contexts) without push.

import { api } from "@/lib/api";

export function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.register("/sw.js");
}

/** Current permission + whether this browser already has a live subscription. */
export async function pushState(): Promise<{ permission: NotificationPermission; enabled: boolean }> {
  if (!pushSupported()) return { permission: "denied", enabled: false };
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  return { permission: Notification.permission, enabled: !!sub };
}

/** Turn browser notifications on. Returns false if the key is unset, unsupported, or the
 *  user denied permission. Safe to call repeatedly. */
export async function enablePush(): Promise<boolean> {
  if (!pushSupported()) return false;
  const { key } = await api.getVapidKey();
  if (!key) return false;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return false;

  const reg = await registration();
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    });
  }
  await api.pushSubscribe(sub.toJSON() as PushSubscriptionJSON);
  return true;
}

/** Turn browser notifications off for this browser, both locally and on the server. */
export async function disablePush(): Promise<void> {
  if (!pushSupported()) return;
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  if (sub) {
    await api.pushUnsubscribe(sub.endpoint).catch(() => {});
    await sub.unsubscribe().catch(() => {});
  }
}
