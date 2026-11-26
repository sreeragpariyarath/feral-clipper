"use client";

import type { ComponentType } from "react";
import { Clapperboard, Coins, HardDrive, ListChecks, Plus, Send } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PAGES } from "@/lib/pages";
import { keys } from "@/lib/queries";
import type { Clip } from "@/lib/types";
import { ClipFilters } from "../clips/ClipFilters";
import { Button } from "../ui/Button";
import { Card, CardHeader } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";
import { Tabs } from "../ui/Tabs";
import { EmptySkeleton } from "./bones";
import {
  CampaignListSkeleton, ClipGridSkeleton, JobListSkeleton, PostListSkeleton, StatTileSkeleton, TrashListSkeleton,
} from "./cards";
import { ClipDetailSkeleton } from "./ClipDetailSkeleton";
import { JobDetailSkeleton } from "./JobDetailSkeleton";
import { NewJobSkeleton } from "./NewJobSkeleton";
import { SettingsSkeleton } from "./SettingsSkeleton";
import { StreamTableSkeleton } from "./StreamTableSkeleton";

const none = () => {};

/** How many rows a list had the last time it was loaded (undefined if it never was). */
function useKnownCount<T = unknown>(key: readonly unknown[], filter?: (row: T) => boolean): number | undefined {
  const rows = useQueryClient().getQueryData<T[]>(key);
  return filter ? rows?.filter(filter).length : rows?.length;
}

const waitingForReview = (c: Clip) => c.has_video && c.decision === "pending";
const headerButton = (label: string) => <Button variant="primary" disabled><Plus size={16} /> {label}</Button>;

function Dashboard() {
  const waiting = useKnownCount(keys.clips({}), waitingForReview);
  const jobs = useKnownCount(keys.jobs);
  return (
    <>
      <PageHeader {...PAGES.dashboard} actions={headerButton("New job")} />
      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTileSkeleton label="Waiting for review" icon={<Clapperboard size={18} />} />
        <StatTileSkeleton label="Jobs running" icon={<ListChecks size={18} />} />
        <StatTileSkeleton label="Claude spend (est.)" icon={<Coins size={18} />} />
        <StatTileSkeleton label="Free disk" icon={<HardDrive size={18} />} />
      </div>
      <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Best clips to review</h2>
            <span className="text-sm text-primary">All clips</span>
          </div>
          {waiting === 0
            ? <EmptySkeleton hint />
            : <ClipGridSkeleton count={Math.min(waiting ?? 3, 6)} className="grid grid-cols-2 gap-4 sm:grid-cols-3" />}
        </section>
        <Card className="h-fit">
          <CardHeader title="Recent jobs" action={<span className="text-sm text-primary">All</span>} />
          <div className="grid gap-2 p-3">
            {jobs === 0
              ? <p className="p-2 text-sm text-muted-foreground">No jobs yet.</p>
              : <JobListSkeleton count={Math.min(jobs ?? 3, 5)} />}
          </div>
        </Card>
      </div>
    </>
  );
}

function Clips() {
  const count = useKnownCount(keys.clips({}), waitingForReview);
  return (
    <>
      <PageHeader {...PAGES.clips} />
      <div inert><ClipFilters stream="" onStream={none} view="ready" onView={none} sort="score" onSort={none} /></div>
      {count === 0 ? <EmptySkeleton hint /> : <ClipGridSkeleton count={count ?? 8} />}
    </>
  );
}

function Jobs() {
  const count = useKnownCount(keys.jobs);
  return (
    <>
      <PageHeader {...PAGES.jobs} actions={headerButton("New job")} />
      <div className="mb-4" inert>
        <Tabs value="all" onChange={none} tabs={["All", "Active", "Done", "Failed"].map((l) => ({ value: l.toLowerCase(), label: l }))} />
      </div>
      {count === 0 ? <EmptySkeleton /> : <JobListSkeleton count={count ?? 4} />}
    </>
  );
}

function Streams() {
  const count = useKnownCount(keys.streams);
  return (
    <>
      <PageHeader {...PAGES.streams} />
      {count === 0 ? <EmptySkeleton /> : <StreamTableSkeleton rows={count ?? 3} />}
    </>
  );
}

function Posted() {
  const count = useKnownCount([...keys.posts, "all"]);
  return (
    <>
      <PageHeader {...PAGES.posted} />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <StatTileSkeleton label="Posts" icon={<Send size={18} />} hint={false} />
        <StatTileSkeleton label="Views" icon={<Send size={18} />} hint={false} />
        <StatTileSkeleton label="Estimated payout" icon={<Send size={18} />} />
      </div>
      {count === 0 ? <EmptySkeleton hint /> : <PostListSkeleton count={count ?? 3} />}
    </>
  );
}

function Campaigns() {
  const count = useKnownCount(keys.campaigns);
  return (
    <>
      <PageHeader {...PAGES.campaigns} actions={headerButton("Add campaign")} />
      {count === 0 ? <EmptySkeleton hint /> : <CampaignListSkeleton count={count ?? 2} />}
    </>
  );
}

function Trash() {
  const count = useKnownCount(keys.clips({ deleted: true }));
  return (
    <>
      <PageHeader {...PAGES.trash} />
      {count === 0 ? <EmptySkeleton /> : <TrashListSkeleton count={count ?? 3} />}
    </>
  );
}

const NewJob = () => (
  <div className="max-w-2xl">
    <PageHeader {...PAGES.newJob} />
    <NewJobSkeleton />
  </div>
);

const Settings = () => (
  <>
    <PageHeader {...PAGES.settings} />
    <SettingsSkeleton />
  </>
);

const BY_PATH: Record<string, ComponentType> = {
  "/": Dashboard, "/new": NewJob, "/jobs": Jobs, "/clips": Clips, "/streams": Streams,
  "/posted": Posted, "/campaigns": Campaigns, "/trash": Trash, "/settings": Settings,
};

/** The placeholder of the page being opened, built from the same layout as the page itself. */
export function PageSkeleton({ path }: { path: string }) {
  const Page = BY_PATH[path]
    ?? (path.startsWith("/clips/") ? ClipDetailSkeleton : path.startsWith("/jobs/") ? JobDetailSkeleton : null);
  return <div role="status" aria-label="Loading page">{Page && <Page />}</div>;
}
