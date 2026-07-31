"use client";

import { Bell, Loader2, Mail, MessageCircle, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui";
import { api, type NotificationPrefs } from "@/lib/api";
import { disablePush, enablePush, pushState, pushSupported } from "@/lib/push";

const ROWS: { key: keyof NotificationPrefs; icon: React.ReactNode; label: string; hint: string }[] = [
  { key: "email", icon: <Mail className="size-4" />, label: "Email", hint: "Intros, run updates, and account emails" },
  { key: "whatsapp", icon: <MessageCircle className="size-4" />, label: "WhatsApp", hint: "The same alerts on WhatsApp (needs a phone number)" },
  { key: "digest", icon: <Sparkles className="size-4" />, label: "Weekly roles digest", hint: "Ada's fresh best-fit roles, once a week" },
];

export function NotificationPreferences() {
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [saving, setSaving] = useState<string>("");
  const [push, setPush] = useState<boolean | null>(null); // null until known; hidden if unsupported
  const [pushBusy, setPushBusy] = useState(false);

  useEffect(() => {
    api.getNotificationPrefs().then(setPrefs).catch(() => setPrefs(null));
    if (pushSupported()) pushState().then((s) => setPush(s.enabled)).catch(() => setPush(false));
  }, []);

  const togglePush = async () => {
    setPushBusy(true);
    try {
      if (push) {
        await disablePush();
        setPush(false);
      } else {
        setPush(await enablePush()); // stays false if permission denied / key unset
      }
    } finally {
      setPushBusy(false);
    }
  };

  const toggle = async (key: keyof NotificationPrefs) => {
    if (!prefs) return;
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    setSaving(key);
    try {
      await api.setNotificationPrefs(next);
    } catch {
      setPrefs(prefs); // revert
    } finally {
      setSaving("");
    }
  };

  if (prefs === null) return null;

  return (
    <Card className="mb-6 p-6">
      <p className="font-medium">Notifications</p>
      <p className="mt-1 text-xs text-muted">
        The in-app bell always stays on — these control the email and WhatsApp channels.
      </p>
      <div className="mt-4 divide-y divide-line">
        {ROWS.map((row) => (
          <div key={row.key} className="flex items-center gap-3 py-3">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted">
              {row.icon}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">{row.label}</span>
              <span className="block text-xs text-muted">{row.hint}</span>
            </span>
            {saving === row.key && <Loader2 className="size-4 animate-spin text-muted" />}
            <button
              role="switch"
              aria-checked={prefs[row.key]}
              aria-label={`Toggle ${row.label}`}
              onClick={() => toggle(row.key)}
              className={`relative h-6 w-10 shrink-0 rounded-full transition-colors ${
                prefs[row.key] ? "bg-success" : "bg-line"
              }`}
            >
              <span
                className={`absolute top-0.5 size-5 rounded-full bg-surface shadow-sm transition-all ${
                  prefs[row.key] ? "left-[1.15rem]" : "left-0.5"
                }`}
              />
            </button>
          </div>
        ))}

        {push !== null && (
          <div className="flex items-center gap-3 py-3">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted">
              <Bell className="size-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">Browser notifications</span>
              <span className="block text-xs text-muted">
                Push alerts to this device, even with Ada closed
              </span>
            </span>
            {pushBusy && <Loader2 className="size-4 animate-spin text-muted" />}
            <button
              role="switch"
              aria-checked={push}
              aria-label="Toggle browser notifications"
              disabled={pushBusy}
              onClick={togglePush}
              className={`relative h-6 w-10 shrink-0 rounded-full transition-colors disabled:opacity-60 ${
                push ? "bg-success" : "bg-line"
              }`}
            >
              <span
                className={`absolute top-0.5 size-5 rounded-full bg-surface shadow-sm transition-all ${
                  push ? "left-[1.15rem]" : "left-0.5"
                }`}
              />
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}
