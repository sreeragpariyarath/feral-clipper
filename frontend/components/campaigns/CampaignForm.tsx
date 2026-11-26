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
  logo_on: true, logo_width: 420, logo_y: 28, hashtags: "",
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
        <Field label="Logo file path" hint="PNG / WEBP / JPG on this PC; drawn on top of every clip">
          <Input value={form.logo_path} placeholder="C:\campaigns\logo.png" onChange={(e) => set("logo_path", e.target.value)} />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input type="checkbox" checked={form.logo_on} onChange={(e) => set("logo_on", e.target.checked)} /> Show logo on clips
        </label>
        <Field label="Logo width (px of 1080)">
          <Input type="number" min={100} max={1080} value={form.logo_width} disabled={!form.logo_on}
            onChange={(e) => set("logo_width", Number(e.target.value))} />
        </Field>
        <Field label="Logo from top (px of 1920)">
          <Input type="number" min={0} max={1800} value={form.logo_y} disabled={!form.logo_on}
            onChange={(e) => set("logo_y", Number(e.target.value))} />
        </Field>
      </div>
      <Field label="Brief" hint="The judge checks clips against these rules">
        <Textarea value={form.brief} onChange={(e) => set("brief", e.target.value)} />
      </Field>
      <Field label="Required caption text" hint="Copied word for word into every posting kit">
        <Input value={form.caption} onChange={(e) => set("caption", e.target.value)} />
      </Field>
      <Field label="Hashtags" hint="e.g. #asianjeff #clipping (added first, before the GTA tags)">
        <Input value={form.hashtags} onChange={(e) => set("hashtags", e.target.value)} />
      </Field>
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
