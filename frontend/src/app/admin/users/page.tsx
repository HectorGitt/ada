"use client";

import { Loader2, Search, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button, Card, Input, StatusBadge } from "@/components/ui";
import { ApiError, api, type AdminUserDetail, type AdminUserRow } from "@/lib/api";

const GRANT_TIERS = ["pro", "premium", "growth", "scale"];

export default function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<AdminUserRow[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback((query: string) => {
    setRows(null);
    api.admin.users(query).then(setRows).catch(() => setRows([]));
  }, []);

  useEffect(() => {
    load("");
  }, [load]);

  return (
    <>
      <h1 className="display mb-4 text-3xl">Users.</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          load(q);
        }}
        className="mb-4 flex gap-2"
      >
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            placeholder="Search email or company…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="!pl-9"
          />
        </div>
        <Button type="submit">Search</Button>
      </form>

      {rows === null ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="size-4 animate-spin" /> Loading…
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">No users found.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((u) => (
            <div key={u.id}>
              <div
                onClick={() => setSelected(selected === u.id ? null : u.id)}
                className="cursor-pointer"
              >
              <Card className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 transition-colors hover:border-ink/20">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{u.email}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {u.account_type}
                    {u.company ? ` · ${u.company}` : ""} ·{" "}
                    {new Date(u.created_at).toLocaleDateString()}
                  </p>
                </div>
                {u.subscription?.tier && u.subscription.tier !== "free" ? (
                  <StatusBadge tone={u.subscription.status === "active" ? "success" : "warn"}>
                    {u.subscription.tier}
                  </StatusBadge>
                ) : (
                  <StatusBadge tone="neutral">free</StatusBadge>
                )}
              </Card>
              </div>
              {selected === u.id && <UserDetail id={u.id} onChanged={() => load(q)} />}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function UserDetail({ id, onChanged }: { id: string; onChanged: () => void }) {
  const router = useRouter();
  const [d, setD] = useState<AdminUserDetail | null>(null);
  const [tier, setTier] = useState("premium");
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const reload = useCallback(() => {
    api.admin.user(id).then(setD).catch(() => setD(null));
  }, [id]);
  useEffect(reload, [reload]);

  const act = async (label: string, fn: () => Promise<unknown>, note: string) => {
    setBusy(label);
    setMsg("");
    try {
      await fn();
      setMsg(note);
      reload();
      onChanged();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusy("");
    }
  };

  if (!d) return <Card className="mt-1 p-4 text-sm text-muted">Loading…</Card>;

  return (
    <Card className="mt-1 space-y-4 border-accent/30 p-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1 text-sm">
          <p className="text-muted">
            Entitlement: <span className="font-medium text-ink">{d.entitlement.tier}</span>
            {d.entitlement.can_apply && " · apply"}
            {d.entitlement.can_voice && " · voice"}
          </p>
          <p className="text-muted">
            Runs {d.counts.runs} · Applications {d.counts.applications}
          </p>
          {d.profile && (
            <p className="text-muted">
              {d.profile.full_name ?? "—"} · {d.profile.identity_verified ? "ID verified" : "ID unverified"}
              {d.profile.discoverable ? " · discoverable" : ""}
            </p>
          )}
          {d.credential && (
            <p className="text-muted">
              Credential: {d.credential.skill} — {d.credential.score} ({d.credential.verdict})
            </p>
          )}
          {d.is_admin && (
            <p className="flex items-center gap-1.5 font-medium text-danger">
              <ShieldAlert className="size-4" /> Admin account
            </p>
          )}
        </div>

        {/* Grant a plan */}
        <div className="rounded-xl bg-surface-2 p-3">
          <p className="text-xs font-medium">Comp a plan</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <select
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs"
            >
              {GRANT_TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="w-20 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs"
            />
            <span className="text-xs text-muted">days</span>
            <Button
              loading={busy === "grant"}
              onClick={() => act("grant", () => api.admin.grant(id, tier, "monthly", days), `Granted ${tier}.`)}
              className="!px-3 !py-1.5 text-xs"
            >
              Grant
            </Button>
            <button
              onClick={() => act("revoke", () => api.admin.revoke(id), "Plan revoked.")}
              disabled={busy === "revoke"}
              className="text-xs text-muted underline-offset-2 hover:underline disabled:opacity-50"
            >
              revoke
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
        <Button
          variant="secondary"
          onClick={() =>
            act(
              "type",
              () =>
                api.admin.setAccountType(
                  id,
                  d.account_type === "candidate" ? "employer" : "candidate",
                ),
              "Account type changed.",
            )
          }
          loading={busy === "type"}
          className="!py-1.5 text-xs"
        >
          Make {d.account_type === "candidate" ? "employer" : "candidate"}
        </Button>

        <Button
          variant="secondary"
          onClick={async () => {
            if (!confirm(`Impersonate ${d.email}? This browser will become their session.`)) return;
            try {
              await api.admin.impersonate(id);
              router.push("/app");
            } catch {
              setMsg("Impersonation failed.");
            }
          }}
          className="!py-1.5 text-xs"
        >
          Impersonate
        </Button>

        {!d.is_admin && (
          <Button
            variant="danger"
            onClick={() => {
              if (!confirm(`Permanently delete ${d.email} and all their data?`)) return;
              void act("delete", () => api.admin.deleteUser(id), "User deleted.");
            }}
            loading={busy === "delete"}
            className="!py-1.5 text-xs"
          >
            Delete
          </Button>
        )}

        {msg && <span className="text-xs text-muted">{msg}</span>}
      </div>
    </Card>
  );
}
