"use client";

import Link from "next/link";
import { LayoutGrid, Plus, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "../ui/Button";

type Props = {
  collapsed: boolean;
  onToggle: () => void;
};

export function Sidebar({ collapsed, onToggle }: Props) {
  return (
    <aside aria-label="Sidebar" className={"sticky top-0 flex h-dvh shrink-0 flex-col gap-4 border-r bg-sidebar p-2 sm:p-3 " + (collapsed ? "w-14 sm:w-16" : "w-14 sm:w-56")}>
      <div className="flex flex-col items-center gap-2 sm:items-start">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.png" alt="Feral Streams" width={44} height={44} className="size-9 object-contain sm:size-11" />
        <Button
          variant="ghost"
          aria-expanded={!collapsed}
          aria-controls="sidebar-navigation"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={onToggle}
          className="hidden sm:block"
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </Button>
      </div>

      <nav id="sidebar-navigation" aria-label="Main navigation">
        <Link
          href="/"
          aria-current="page"
          aria-label="Library"
          title="Library"
          className="flex items-center gap-3 rounded-xl bg-sidebar-accent p-2.5 font-semibold text-sidebar-accent-foreground"
        >
          <LayoutGrid size={18} className="shrink-0" />
          {!collapsed && <span className="hidden sm:inline">Library</span>}
        </Link>
        <Link
          href="/jobs"
          aria-label="New stream"
          title="New stream"
          className="mt-1 flex items-center gap-3 rounded-xl p-2.5 font-semibold hover:bg-sidebar-accent"
        >
          <Plus size={18} className="shrink-0" />
          {!collapsed && <span className="hidden sm:inline">New stream</span>}
        </Link>
      </nav>
    </aside>
  );
}
