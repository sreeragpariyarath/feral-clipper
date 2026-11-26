"use client";

import { DatabaseBackup } from "lucide-react";
import { useBackups, useMakeBackup } from "@/lib/queries";
import { localTime } from "@/lib/format";
import { Button } from "../ui/Button";
import { Card, CardHeader } from "../ui/Card";
import { useToast } from "../ui/Toast";
import { SettingRowsSkeleton } from "../skeletons/SettingsSkeleton";

/** Copy the database (jobs, clips, reviews, campaigns, posts) into backups/. Videos are not included. */
export function BackupCard() {
  const { data: list = [], isLoading } = useBackups();
  const make = useMakeBackup();
  const toast = useToast();

  return (
    <Card>
      <CardHeader title="Database backup" subtitle="Reviews, campaigns and posts; saved in the backups folder"
        action={
          <Button size="sm" variant="primary" loading={make.isPending}
            onClick={() => make.mutate(undefined, { onSuccess: (b) => toast.ok(`Saved ${b.name}`), onError: toast.error })}>
            <DatabaseBackup size={14} /> Back up now
          </Button>
        } />
      <ul className="grid gap-1.5 p-4 text-sm">
        {list.slice(0, 6).map((b) => (
          <li key={b.name} className="flex justify-between gap-3">
            <span className="truncate font-mono text-xs">{b.name}</span>
            <span className="shrink-0 text-muted-foreground">{b.size_mb} MB · {localTime(b.created_at)}</span>
          </li>
        ))}
        {isLoading && <li><SettingRowsSkeleton rows={1} className="grid" /></li>}
        {!isLoading && !list.length && <li className="text-muted-foreground">No backups yet.</li>}
      </ul>
    </Card>
  );
}
