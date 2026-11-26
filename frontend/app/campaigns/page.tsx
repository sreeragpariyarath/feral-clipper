"use client";

import { useState } from "react";
import { Megaphone, Pencil, Plus, Trash2 } from "lucide-react";
import { CampaignForm } from "@/components/campaigns/CampaignForm";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorNote } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { localTime } from "@/lib/format";
import { useCampaigns, useDeleteCampaign } from "@/lib/queries";

export default function CampaignsPage() {
  const { data: campaigns = [], error } = useCampaigns();
  const remove = useDeleteCampaign();
  const toast = useToast();
  const [editing, setEditing] = useState<number | "new" | null>(null);

  const ended = (iso: string | null) => !!iso && new Date(iso) < new Date();

  return (
    <>
      <PageHeader title="Campaigns" subtitle="Clipping deals: rules for the judge, payout, and end date."
        actions={editing === null && <Button variant="primary" onClick={() => setEditing("new")}><Plus size={16} /> Add campaign</Button>} />
      <ErrorNote error={error} />

      {editing === "new" && (
        <Card className="mb-4"><CardHeader title="New campaign" /><CampaignForm onDone={() => setEditing(null)} /></Card>
      )}

      <div className="grid gap-3">
        {campaigns.map((c) => editing === c.id ? (
          <Card key={c.id}><CardHeader title={`Edit ${c.name}`} /><CampaignForm campaign={c} onDone={() => setEditing(null)} /></Card>
        ) : (
          <Card key={c.id} className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">{c.name}</h2>
                  {ended(c.ends_at) ? <Badge tone="warning">ended</Badge> : c.active ? <Badge tone="success">active</Badge> : <Badge>paused</Badge>}
                </div>
                <p className="text-sm text-muted-foreground">
                  {c.streamer || "any streamer"} · ${c.payout_per_1k.toFixed(2)} per 1K views
                  {c.ends_at && ` · ends ${localTime(c.ends_at)}`}
                  {!!c.platforms.length && ` · ${c.platforms.join(", ")}`}
                </p>
                {c.brief && <p className="mt-2 line-clamp-2 text-sm">{c.brief}</p>}
              </div>
              <div className="flex gap-1.5">
                <Button size="icon" aria-label="Edit" onClick={() => setEditing(c.id)}><Pencil size={14} /></Button>
                <Button size="icon" variant="danger" aria-label="Delete" disabled={remove.isPending}
                  onClick={() => confirm(`Delete campaign “${c.name}”? This cannot be undone.`) &&
                    remove.mutate(c.id, { onSuccess: () => toast.ok("Campaign deleted"), onError: toast.error })}>
                  <Trash2 size={14} />
                </Button>
              </div>
            </div>
          </Card>
        ))}
        {!campaigns.length && editing === null && <EmptyState icon={<Megaphone />} title="No campaigns yet">Add the AsianJeff campaign to keep its rules here.</EmptyState>}
      </div>
    </>
  );
}
