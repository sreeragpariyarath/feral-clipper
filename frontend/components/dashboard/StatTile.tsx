import Link from "next/link";
import type { ReactNode } from "react";

export function StatTile({ label, value, hint, icon, href }: {
  label: string; value: ReactNode; hint?: ReactNode; icon: ReactNode; href?: string;
}) {
  const body = (
    <div className="flex items-start justify-between gap-3 rounded-xl border bg-card p-4 transition hover:border-primary/40">
      <div className="min-w-0">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
        {hint && <p className="mt-0.5 truncate text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">{icon}</div>
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}
