"use client";

import { useEffect, useState } from "react";

import { EmployerShell } from "@/components/hire/shell";
import { Button, Card, Input, Label, PageHeader, Textarea } from "@/components/ui";
import { api, type CompanyProfile } from "@/lib/api";

const EMPTY: CompanyProfile = {
  name: "", website: "", industry: "", size: "", location: "",
  about: "", logo_url: "", contact_name: "", contact_title: "",
};

const SIZES = ["1–10", "11–50", "51–200", "201–500", "500+"];

export default function CompanyPage() {
  return (
    <EmployerShell>
      <CompanyForm />
    </EmployerShell>
  );
}

function CompanyForm() {
  const [c, setC] = useState<CompanyProfile>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getCompany()
      .then((existing) => existing && setC({ ...EMPTY, ...existing }))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const set = (k: keyof CompanyProfile) => (e: { target: { value: string } }) =>
    setC((cur) => ({ ...cur, [k]: e.target.value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.putCompany(c);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Company."
        subtitle="What candidates see when you reach out. A real profile makes intros land."
      />
      {loaded && c.name && (
        <p className="mb-4 text-sm text-muted">
          This profile is shown on your public company page, linked from every intro you send.
        </p>
      )}
      <Card className="max-w-2xl p-6">
        <form onSubmit={save} className="space-y-4">
          <div>
            <Label htmlFor="name">Company name</Label>
            <Input id="name" required value={c.name} onChange={set("name")} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="industry">Industry</Label>
              <Input id="industry" placeholder="Fintech" value={c.industry ?? ""} onChange={set("industry")} />
            </div>
            <div>
              <Label htmlFor="size">Team size</Label>
              <select
                id="size"
                value={c.size ?? ""}
                onChange={set("size")}
                className="w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm"
              >
                <option value="">Select…</option>
                {SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="website">Website</Label>
              <Input id="website" placeholder="https://…" value={c.website ?? ""} onChange={set("website")} />
            </div>
            <div>
              <Label htmlFor="location">Location</Label>
              <Input id="location" placeholder="Lagos, Nigeria" value={c.location ?? ""} onChange={set("location")} />
            </div>
          </div>
          <div>
            <Label htmlFor="logo">Logo URL</Label>
            <Input id="logo" placeholder="https://…/logo.png" value={c.logo_url ?? ""} onChange={set("logo_url")} />
          </div>
          <div>
            <Label htmlFor="about">About</Label>
            <Textarea id="about" rows={4} placeholder="What you do and why someone would want to work with you." value={c.about ?? ""} onChange={set("about")} />
          </div>
          <div className="grid gap-4 border-t border-line pt-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="cn">Your name (the recruiter)</Label>
              <Input id="cn" placeholder="Ada R." value={c.contact_name ?? ""} onChange={set("contact_name")} />
            </div>
            <div>
              <Label htmlFor="ct">Your title</Label>
              <Input id="ct" placeholder="Head of Talent" value={c.contact_title ?? ""} onChange={set("contact_title")} />
            </div>
          </div>
          <Button type="submit" loading={saving}>{saved ? "Saved ✓" : "Save company profile"}</Button>
        </form>
      </Card>
    </>
  );
}
