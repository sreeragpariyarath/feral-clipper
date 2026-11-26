"use client";

import Link from "next/link";
import { Film } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorNote, Skeleton } from "@/components/ui/States";
import { clock, localTime, streamName } from "@/lib/format";
import { useStreams } from "@/lib/queries";

export default function StreamsPage() {
  const { data: streams = [], isLoading, error } = useStreams();
  const total = streams.reduce((n, s) => n + s.size_gb, 0);

  return (
    <>
      <PageHeader title="Streams" subtitle={`Every downloaded stream and the clips made from it · ${total.toFixed(1)} GB on disk`} />
      <ErrorNote error={error} />
      {isLoading && <Skeleton className="h-48" />}
      {!isLoading && !streams.length && <EmptyState icon={<Film />} title="No streams yet" />}
      {!!streams.length && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Stream</th>
                <th className="px-4 py-3 font-medium">Length</th>
                <th className="px-4 py-3 text-right font-medium">Clips</th>
                <th className="px-4 py-3 text-right font-medium">Ready</th>
                <th className="px-4 py-3 text-right font-medium">Approved</th>
                <th className="px-4 py-3 text-right font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {streams.map((s) => (
                <tr key={s.id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="max-w-80 px-4 py-3">
                    <Link href={`/clips?stream=${encodeURIComponent(s.id)}`} className="font-medium hover:underline">{s.title || streamName(s.id)}</Link>
                    <p className="truncate text-xs text-muted-foreground">{s.channel || s.id}</p>
                  </td>
                  <td className="px-4 py-3 tabular-nums">{s.duration_s ? clock(s.duration_s) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.clips}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.ready}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.approved}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.size_gb.toFixed(1)} GB</td>
                  <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">{localTime(s.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
