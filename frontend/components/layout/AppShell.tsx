"use client";

import { useEffect, useState, type ReactNode } from "react";
import { PanelRightOpen } from "lucide-react";
import { useLiveEvents } from "@/lib/useLiveEvents";
import { usePendingPath } from "@/lib/usePendingPath";
import { PageSkeleton } from "../skeletons/PageSkeleton";
import { ActivityPanel } from "./ActivityPanel";
import { DiskBanner } from "./DiskBanner";
import { MobileNav, Sidebar } from "./Sidebar";

function useStoredFlag(key: string, initial: boolean): [boolean, (v: boolean) => void] {
  const [value, setValue] = useState(initial);
  useEffect(() => {
    try { const v = localStorage.getItem(key); if (v !== null) setValue(v === "1"); } catch { /* ignore */ }
  }, [key]);
  const set = (v: boolean) => {
    setValue(v);
    try { localStorage.setItem(key, v ? "1" : "0"); } catch { /* ignore */ }
  };
  return [value, set];
}

/** Sidebar on the left, page in the middle, live activity on the right. */
export function AppShell({ children }: { children: ReactNode }) {
  const live = useLiveEvents();
  const pending = usePendingPath();
  const [collapsed, setCollapsed] = useStoredFlag("feral-sidebar-collapsed", false);
  const [activity, setActivity] = useStoredFlag("feral-activity-open", true);

  return (
    <div className="flex min-h-dvh bg-canvas">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} pending={pending} />
      <main className="relative min-w-0 flex-1 px-4 pt-6 pb-24 sm:px-8 md:pb-10">
        {!activity && (
          <button onClick={() => setActivity(true)} aria-label="Show activity"
            className="absolute top-4 right-4 hidden rounded-lg border bg-card p-2 text-muted-foreground hover:text-foreground xl:block">
            <PanelRightOpen size={16} />
          </button>
        )}
        <div className="mx-auto max-w-6xl animate-rise">
          <DiskBanner />
          {pending && <PageSkeleton path={pending} />}
          <div hidden={!!pending}>{children}</div>
        </div>
      </main>
      {activity && <ActivityPanel live={live} onClose={() => setActivity(false)} />}
      <MobileNav pending={pending} />
    </div>
  );
}
