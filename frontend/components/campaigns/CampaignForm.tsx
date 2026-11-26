"use client";

import { useState, type FormEvent } from "react";
import { useSaveCampaign } from "@/lib/queries";
import type { Campaign, CampaignIn } from "@/lib/types";
import { Button } from "../ui/Button";
import { Field, Input, Textarea } from "../ui/Field";
import { ErrorNote } from "../ui/States";
import { useToast } from "../ui/Toast";

const EMPTY: CampaignIn = {
  name: "", streamer: "", active: true, brief: "", caption: "", logo_path: "", payout_per_1k: 0, platforms: [], ends_at: null,
};

/** `datetime-local` wants "YYYY-MM-DDTHH:mm" in local time. */
const toLocalInput = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export function CampaignForm({ campaign, onDone }: { campaign?: Campaign; onDone: () => void }) {
  const save = useSaveCampaign();
  const toast = useToast();
  const [form, setForm] = useState<CampaignIn>(campaign ? { ...campaign } : EMPTY);
  const set = <K extends keyof CampaignIn>(k: K, v: CampaignIn[K]) => setForm((f) => ({ ...f, [k]: v }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({ id: campaign?.id, body: form }, { onSuccess: () => { toast.ok("Campaign saved"); onDone(); } });
  };

  return (
    <form onSubmit={submit} className="grid gap-4 p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name"><Input required value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
        <Field label="Streamer"><Input value={form.streamer} onChange={(e) => set("streamer", e.target.value)} /></Field>
        <Field label="Payout per 1,000 views ($)">
          <Input type="number" step="0.01" min={0} value={form.payout_per_1k} onChange={(e) => set("payout_per_1k", Number(e.target.value))} />
        </Field>
        <Field label="Ends (your local time)">
          <Input type="datetime-local" value={toLocalInput(form.ends_at)} onChange={(e) => set("ends_at", e.target.value || null)} />
        </Field>
        <Field label="Platforms" hint="Comma separated">
          <Input value={form.platforms.join(", ")} onChange={(e) => set("platforms", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} />
        </Field>
        <Field label="Logo file path" hint="Overlay image for this campaign">
          <Input value={form.logo_path} onChange={(e) => set("logo_path", e.target.value)} />
        </Field>
      </div>
      <Field label="Brief" hint="The judge checks clips against these rules">
        <Textarea value={form.brief} onChange={(e) => set("brief", e.target.value)} />
      </Field>
      <Field label="Required caption text"><Input value={form.caption} onChange={(e) => set("caption", e.target.value)} /></Field>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.active} onChange={(e) => set("active", e.target.checked)} /> Active
      </label>
      <ErrorNote error={save.error} />
      <div className="flex justify-end gap-2">
        <Button onClick={onDone}>Cancel</Button>
        <Button type="submit" variant="primary" loading={save.isPending}>Save</Button>
      </div>
    </form>
  );
}
