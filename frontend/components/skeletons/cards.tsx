import type { ReactNode } from "react";
import { Card } from "../ui/Card";
import { Bone, Line, times } from "./bones";

/** Mirrors StatTile. The label and icon are known before the data, so they are shown. */
export function StatTileSkeleton({ label, icon, hint = true }: { label: string; icon: ReactNode; hint?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border bg-card p-4">
      <div className="min-w-0">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-bold"><Line className="w-14" /></p>
        {hint && <p className="mt-0.5 truncate text-xs"><Line className="w-24" /></p>}
      </div>
      <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">{icon}</div>
    </div>
  );
}

/** Mirrors ClipCard. */
export function ClipCardSkeleton() {
  return (
    <article className="overflow-hidden rounded-xl border bg-card">
      <div className="aspect-[9/16] max-h-80 w-full animate-pulse bg-muted" />
      <div className="grid gap-2 p-3">
        <div className="min-h-10 text-sm font-semibold leading-snug">
          <div><Line className="w-full" /></div>
          <div><Line className="w-2/3" /></div>
        </div>
        <div className="flex items-center justify-between text-xs">
          <Line className="w-8" /><Bone className="h-5 w-16 rounded-full" />
        </div>
        <div className="flex gap-1.5"><Bone className="h-8 w-[6.25rem]" /><Bone className="h-8 w-[5.25rem]" /></div>
      </div>
    </article>
  );
}

type GridProps = { count?: number; className?: string };

export const ClipGridSkeleton = ({ count = 8, className = "grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" }: GridProps) => (
  <div className={className}>{times(count).map((i) => <ClipCardSkeleton key={i} />)}</div>
);

/** Mirrors JobCard. */
export function JobCardSkeleton() {
  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card p-4">
      <Bone className="size-10 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-semibold"><Line className="w-36" /></p>
          <Bone className="h-5 w-12 rounded-full" />
        </div>
        <p className="mt-0.5 truncate text-sm"><Line className="w-48" /></p>
      </div>
      <Bone className="size-[18px] shrink-0" />
    </div>
  );
}

export const JobListSkeleton = ({ count = 3 }: { count?: number }) => (
  <div className="grid gap-2">{times(count).map((i) => <JobCardSkeleton key={i} />)}</div>
);

/** Mirrors a row on the Trash page. */
export const TrashListSkeleton = ({ count = 3 }: { count?: number }) => (
  <div className="grid gap-2">
    {times(count).map((i) => (
      <Card key={i} className="flex items-center gap-4 p-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium"><Line className="w-64" /></p>
          <p className="text-xs"><Line className="w-48" /></p>
        </div>
        <Bone className="h-8 w-24" />
      </Card>
    ))}
  </div>
);

/** Mirrors a row on the Posted page. */
export const PostListSkeleton = ({ count = 3 }: { count?: number }) => (
  <div className="grid gap-2">
    {times(count).map((i) => (
      <Card key={i} className="flex items-center gap-4 p-3">
        <Bone className="h-16 w-9 shrink-0 rounded" />
        <div className="min-w-0 flex-1">
          <p className="font-medium"><Line className="w-64" /></p>
          <div className="flex items-center gap-2 text-xs"><Bone className="h-5 w-16 rounded-full" /><Line className="w-32" /></div>
        </div>
        <Bone className="h-[38px] w-28 shrink-0" />
        <span className="w-20 text-right text-sm"><Line className="w-12" /></span>
        <Bone className="size-9 shrink-0" />
      </Card>
    ))}
  </div>
);

/** Mirrors a campaign card. */
export const CampaignListSkeleton = ({ count = 2 }: { count?: number }) => (
  <div className="grid gap-3">
    {times(count).map((i) => (
      <Card key={i} className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold"><Line className="w-40" /></h2>
              <Bone className="h-5 w-14 rounded-full" />
            </div>
            <p className="text-sm"><Line className="w-72" /></p>
            <p className="mt-2 text-sm"><Line className="w-96" /></p>
          </div>
          <div className="flex gap-1.5"><Bone className="size-9" /><Bone className="size-9" /></div>
        </div>
      </Card>
    ))}
  </div>
);
