"use client";

import { RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorNote } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { localTime, streamName } from "@/lib/format";
import { useClips, useRestoreClip } from "@/lib/queries";
import { PAGES } from "@/lib/pages";
import { TrashListSkeleton } from "@/components/skeletons/cards";

export default function TrashPage() {
  const { data: clips = [], isLoading, error } = useClips({ deleted: true });
  const restore = useRestoreClip();
  const toast = useToast();

  return (
    <>
      <PageHeader {...PAGES.trash} />
      <ErrorNote error={error} />
      {isLoading && <TrashListSkeleton />}
      {!isLoading && !clips.length && <EmptyState icon={<Trash2 />} title="Trash is empty" />}
      <div className="grid gap-2">
        {clips.map((c) => (
          <Card key={c.id} className="flex items-center gap-4 p-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{c.title || `Clip ${c.clip_no}`}</p>
              <p className="truncate text-xs text-muted-foreground capitalize">{streamName(c.stream_id)} · #{c.clip_no} · deleted {localTime(c.updated_at)}</p>
            </div>
            <Button size="sm" disabled={restore.isPending}
              onClick={() => restore.mutate(c.id, { onSuccess: () => toast.ok("Restored"), onError: toast.error })}>
              <RotateCcw size={14} /> Restore
            </Button>
          </Card>
        ))}
      </div>
    </>
  );
}
