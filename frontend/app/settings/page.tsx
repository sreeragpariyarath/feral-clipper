"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { BackupCard } from "@/components/settings/BackupCard";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useHealth, useSettings } from "@/lib/queries";

const KEY_NAMES: Record<string, string> = { anthropic: "ANTHROPIC_API_KEY (Claude judge)", gemini: "GEMINI_API_KEY (later)" };

export default function SettingsPage() {
  const { data: settings } = useSettings();
  const { data: health } = useHealth();

  return (
    <>
      <PageHeader title="Settings" subtitle="Keys live in .env next to the app. Their values never reach the browser." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="API keys" subtitle="Edit .env, then restart the API window" />
          <ul className="grid gap-3 p-4 text-sm">
            {Object.entries(settings?.keys ?? {}).map(([k, set]) => (
              <li key={k} className="flex items-center justify-between gap-3">
                <span>{KEY_NAMES[k] ?? k}</span>
                {set
                  ? <span className="flex items-center gap-1 text-emerald-600"><CheckCircle2 size={16} /> set</span>
                  : <span className="flex items-center gap-1 text-muted-foreground"><XCircle size={16} /> missing</span>}
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="This PC" />
          <dl className="grid gap-3 p-4 text-sm">
            <div className="flex justify-between"><dt className="text-muted-foreground">Free disk</dt><dd>{health ? `${health.disk.free_gb} of ${health.disk.total_gb} GB` : "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-muted-foreground">Jobs queued</dt><dd>{health?.queued_jobs ?? "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-muted-foreground">Pipeline settings</dt><dd><code>config.json</code></dd></div>
          </dl>
        </Card>
        <BackupCard />
      </div>
    </>
  );
}
