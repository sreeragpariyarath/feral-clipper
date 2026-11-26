"use client";

import Link from "next/link";
import { HardDrive } from "lucide-react";
import { useHealth } from "@/lib/queries";

/** Shown on every page while the data disk is low; jobs refuse to start a step below 5 GB. */
export function DiskBanner() {
  const { data } = useHealth();
  if (!data?.low_disk) return null;
  return (
    <div role="status" className="mb-4 flex items-center gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm">
      <HardDrive size={16} className="shrink-0 text-amber-600" />
      <span className="flex-1">
        Disk is getting full: <b>{data.disk.free_gb} GB</b> free. A 10-hour stream needs about 15-25 GB.
      </span>
      <Link href="/streams" className="font-medium text-primary hover:underline">Free space</Link>
    </div>
  );
}
