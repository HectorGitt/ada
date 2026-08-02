"use client";

import { Megaphone } from "lucide-react";
import { useState } from "react";

import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { api } from "@/lib/api";

export default function AdminBroadcastPage() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [link, setLink] = useState("");
  const [segment, setSegment] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirm("Send this announcement to every user in the segment?")) return;
    setBusy(true);
    setResult("");
    try {
      const { recipients } = await api.admin.broadcast(
        title.trim(),
        body.trim(),
        link.trim() || null,
        segment || null,
      );
      setResult(`Queued to ${recipients} user${recipients === 1 ? "" : "s"}.`);
      setTitle("");
      setBody("");
      setLink("");
    } catch {
      setResult("Couldn't send.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1 className="display mb-1 text-3xl">Broadcast.</h1>
      <p className="mb-5 text-sm text-muted">
        Sends an in-app notification (plus email/WhatsApp per each user&apos;s preferences) to a
        segment.
      </p>

      <Card className="max-w-xl p-6">
        <form onSubmit={send} className="space-y-4">
          <div>
            <Label htmlFor="seg">Audience</Label>
            <select
              id="seg"
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              className="w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm"
            >
              <option value="">Everyone</option>
              <option value="candidate">Candidates only</option>
              <option value="employer">Employers only</option>
            </select>
          </div>
          <div>
            <Label htmlFor="t">Title</Label>
            <Input id="t" required value={title} onChange={(e) => setTitle(e.target.value)} maxLength={160} />
          </div>
          <div>
            <Label htmlFor="b">Message</Label>
            <Textarea id="b" required rows={4} value={body} onChange={(e) => setBody(e.target.value)} maxLength={1000} />
          </div>
          <div>
            <Label htmlFor="l">Link (optional)</Label>
            <Input id="l" placeholder="/app/new" value={link} onChange={(e) => setLink(e.target.value)} />
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" loading={busy}>
              <Megaphone className="size-4" /> Send broadcast
            </Button>
            {result && <span className="text-sm text-muted">{result}</span>}
          </div>
        </form>
      </Card>
    </>
  );
}
