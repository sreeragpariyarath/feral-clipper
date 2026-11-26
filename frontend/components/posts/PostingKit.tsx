"use client";

import { useState } from "react";
import { CalendarClock, Copy, Send } from "lucide-react";
import { usePostingKit } from "@/lib/queries";
import type { Clip, Platform } from "@/lib/types";
import { Button } from "../ui/Button";
import { Card, CardHeader } from "../ui/Card";
import { PostingKitSkeleton } from "../skeletons/ClipDetailSkeleton";
import { Tabs } from "../ui/Tabs";
import { useToast } from "../ui/Toast";
import { MarkPosted } from "./MarkPosted";

const LABEL: Record<Platform, string> = { youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram", other: "Other" };

/** Ready-to-paste text per platform, the next good posting times, and "mark as posted". */
export function PostingKit({ clip }: { clip: Clip }) {
  const { data: kit, isLoading } = usePostingKit(clip.id);
  const toast = useToast();
  const [platform, setPlatform] = useState<Platform>("youtube");

  if (isLoading) return <PostingKitSkeleton />;
  if (!kit) return null;
  const k = kit.platforms.find((p) => p.platform === platform) ?? kit.platforms[0];

  const copy = async (text: string, what: string) => {
    try { await navigator.clipboard.writeText(text); toast.ok(`${what} copied`); } catch (e) { toast.error(e); }
  };

  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2"><Send size={16} /> Posting kit</span>}
        subtitle={kit.campaign_name ? `Campaign: ${kit.campaign_name}` : "No campaign on this stream"} />
      <div className="grid gap-4 p-4">
        <Tabs<Platform> value={platform} onChange={setPlatform}
          tabs={kit.platforms.map((p) => ({ value: p.platform, label: LABEL[p.platform] }))} />

        {k.title && (
          <div className="grid gap-1">
            <div className="flex items-center justify-between text-sm font-medium">
              Title <Button size="sm" variant="ghost" onClick={() => copy(k.title, "Title")}><Copy size={14} /> Copy</Button>
            </div>
            <p className="rounded-lg bg-muted px-3 py-2 text-sm">{k.title}</p>
          </div>
        )}
        <div className="grid gap-1">
          <div className="flex items-center justify-between text-sm font-medium">
            {k.title ? "Description" : "Caption"}
            <Button size="sm" variant="ghost" onClick={() => copy(k.caption, "Caption")}><Copy size={14} /> Copy</Button>
          </div>
          <pre className="max-h-48 overflow-auto rounded-lg bg-muted px-3 py-2 font-sans text-sm whitespace-pre-wrap">{k.caption}</pre>
          <p className="text-xs text-muted-foreground">{k.limit_note}</p>
        </div>
        {platform === "youtube" && (
          <div className="grid gap-1">
            <div className="flex items-center justify-between text-sm font-medium">
              Tags <Button size="sm" variant="ghost" onClick={() => copy(k.hashtags.join(", "), "Tags")}><Copy size={14} /> Copy</Button>
            </div>
            <p className="text-sm text-muted-foreground">{k.hashtags.join(", ")}</p>
          </div>
        )}

        <div className="rounded-lg border p-3 text-sm">
          <p className="flex items-center gap-2 font-medium"><CalendarClock size={16} /> Next good times (your time)</p>
          <ul className="mt-1.5 flex flex-wrap gap-2">
            {kit.best_times_local.map((t) => (
              <li key={t} className="rounded-full bg-primary/10 px-2.5 py-0.5 text-primary">
                {new Date(t).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })}
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-xs text-muted-foreground">{kit.best_times_note}</p>
        </div>

        <MarkPosted clip={clip} platform={platform} title={k.title || clip.title} />
      </div>
    </Card>
  );
}
