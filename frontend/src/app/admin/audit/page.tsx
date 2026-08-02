"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/ui";
import { api, type AdminAudit } from "@/lib/api";

export default function AdminAuditPage() {
  const [rows, setRows] = useState<AdminAudit[] | null>(null);

  useEffect(() => {
    api.admin.audit().then(setRows).catch(() => setRows([]));
  }, []);

  return (
    <>
      <h1 className="display mb-1 text-3xl">Audit log.</h1>
      <p className="mb-5 text-sm text-muted">Every privileged admin action, newest first.</p>

      {rows === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">No admin actions recorded yet.</p>
      ) : (
        <div className="space-y-1.5">
          {rows.map((a) => (
            <Card key={a.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
              <div className="min-w-0">
                <p className="text-sm">
                  <span className="font-medium">{a.admin_email}</span>{" "}
                  <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-muted">
                    {a.action}
                  </span>
                  {a.target_user_id && (
                    <span className="text-xs text-muted"> → {a.target_user_id.slice(0, 8)}</span>
                  )}
                </p>
                {a.detail && (
                  <p className="mt-0.5 truncate font-mono text-[11px] text-muted">
                    {JSON.stringify(a.detail)}
                  </p>
                )}
              </div>
              <span className="shrink-0 text-xs text-muted">
                {new Date(a.created_at).toLocaleString()}
              </span>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
