"use client";

import Link from "next/link";
import { useMemo } from "react";
import { ExternalLink, Send, Trash2 } from "lucide-react";
import { StatTile } from "@/components/dashboard/StatTile";
import { ViewsInput } from "@/components/posts/ViewsInput";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorNote, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ago, localTime } from "@/lib/format";
import { useDeletePost, usePosts } from "@/lib/queries";
import type { Post } from "@/lib/types";

const money = (v: number) => v.toLocaleString(undefined, { style: "currency", currency: "USD" });

function totalsByCampaign(posts: Post[]) {
  const out = new Map<string, { views: number; usd: number; posts: number }>();
  for (const p of posts) {
    const key = p.campaign_name ?? "No campaign";
    const t = out.get(key) ?? { views: 0, usd: 0, posts: 0 };
    out.set(key, { views: t.views + p.views, usd: t.usd + (p.payout_usd ?? 0), posts: t.posts + 1 });
  }
  return [...out.entries()].sort((a, b) => b[1].usd - a[1].usd);
}

export default function PostedPage() {
  const { data: posts = [], isLoading, error } = usePosts();
  const remove = useDeletePost();
  const toast = useToast();
  const byCampaign = useMemo(() => totalsByCampaign(posts), [posts]);
  const views = posts.reduce((n, p) => n + p.views, 0);
  const usd = posts.reduce((n, p) => n + (p.payout_usd ?? 0), 0);

  return (
    <>
      <PageHeader title="Posted" subtitle="Where each clip went. Type in the views from each platform; payout uses the campaign's rate." />
      <ErrorNote error={error} />

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <StatTile label="Posts" value={posts.length} icon={<Send size={18} />} />
        <StatTile label="Views" value={views.toLocaleString()} icon={<Send size={18} />} />
        <StatTile label="Estimated payout" value={money(usd)} hint="before campaign minimums" icon={<Send size={18} />} />
      </div>

      {byCampaign.length > 1 && (
        <div className="mb-5 flex flex-wrap gap-2">
          {byCampaign.map(([name, t]) => (
            <Badge key={name} tone="brand">{name}: {t.views.toLocaleString()} views · {money(t.usd)}</Badge>
          ))}
        </div>
      )}

      {isLoading && <Skeleton className="h-40" />}
      {!isLoading && !posts.length && (
        <EmptyState icon={<Send />} title="Nothing posted yet">Open a clip, copy its posting kit, upload it, then press Mark as posted.</EmptyState>
      )}

      <div className="grid gap-2">
        {posts.map((p) => (
          <Card key={p.id} className="flex items-center gap-4 p-3">
            {p.thumb_url
              // eslint-disable-next-line @next/next/no-img-element
              ? <img src={p.thumb_url} alt="" className="h-16 w-9 shrink-0 rounded object-cover" />
              : <div className="h-16 w-9 shrink-0 rounded bg-muted" />}
            <div className="min-w-0 flex-1">
              <Link href={`/clips/${p.clip_id}`} className="line-clamp-1 font-medium hover:underline">{p.title || p.clip_title}</Link>
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge>{p.platform}</Badge>
                {p.campaign_name && <span>{p.campaign_name}</span>}
                <span>posted {localTime(p.posted_at)}</span>
                {p.views_at && <span>views updated {ago(p.views_at)}</span>}
                {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-primary hover:underline">open <ExternalLink size={12} /></a>}
              </p>
            </div>
            <ViewsInput post={p} />
            <span className="w-20 text-right text-sm font-semibold tabular-nums">{p.payout_usd == null ? "—" : money(p.payout_usd)}</span>
            <Button size="icon" variant="ghost" aria-label="Remove this record"
              onClick={() => confirm("Remove this post record? The clip and the real upload are not touched.") &&
                remove.mutate(p.id, { onSuccess: () => toast.ok("Record removed"), onError: toast.error })}>
              <Trash2 size={14} />
            </Button>
          </Card>
        ))}
      </div>
    </>
  );
}
