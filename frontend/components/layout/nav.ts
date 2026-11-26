import { Clapperboard, Film, Gauge, ListChecks, Megaphone, Plus, Send, Settings, Trash2 } from "lucide-react";

export const NAV = [
  { href: "/", label: "Dashboard", icon: Gauge },
  { href: "/new", label: "New job", icon: Plus },
  { href: "/jobs", label: "Jobs", icon: ListChecks },
  { href: "/clips", label: "Clips", icon: Clapperboard },
  { href: "/streams", label: "Streams", icon: Film },
  { href: "/posted", label: "Posted", icon: Send },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/trash", label: "Trash", icon: Trash2 },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export const isActive = (pathname: string, href: string) =>
  href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
