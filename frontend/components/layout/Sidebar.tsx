"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "../ui/cn";
import { ThemeToggle } from "./ThemeToggle";
import { NAV, isActive } from "./nav";

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const pathname = usePathname();
  return (
    <aside aria-label="Sidebar" className={cn(
      "sticky top-0 hidden h-dvh shrink-0 flex-col border-r bg-sidebar p-3 transition-[width] md:flex",
      collapsed ? "w-16" : "w-56",
    )}>
      <div className={cn("mb-6 flex items-center gap-2", collapsed && "justify-center")}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.png" alt="" width={36} height={36} className="size-9 object-contain" />
        {!collapsed && <span className="font-bold leading-tight">Feral<br /><span className="text-xs font-medium text-muted-foreground">Clipper</span></span>}
      </div>

      <nav aria-label="Main" className="grid gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link key={href} href={href} title={label} aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition",
                active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
                collapsed && "justify-center",
              )}>
              <Icon size={18} className="shrink-0" />
              {!collapsed && label}
            </Link>
          );
        })}
      </nav>

      <div className={cn("mt-auto flex items-center gap-1", collapsed ? "flex-col" : "justify-between")}>
        <ThemeToggle />
        <button onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-sidebar-accent">
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>
    </aside>
  );
}

/** Bottom tab bar for narrow screens. */
export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 flex justify-around border-t bg-sidebar/95 py-1 backdrop-blur md:hidden">
      {NAV.slice(0, 5).map(({ href, label, icon: Icon }) => (
        <Link key={href} href={href} aria-label={label}
          className={cn("grid place-items-center gap-0.5 px-2 py-1 text-[10px]", isActive(pathname, href) ? "text-primary" : "text-muted-foreground")}>
          <Icon size={18} />{label}
        </Link>
      ))}
    </nav>
  );
}
