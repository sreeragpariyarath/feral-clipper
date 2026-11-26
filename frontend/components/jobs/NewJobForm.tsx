"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { FileVideo, Link2, Rocket } from "lucide-react";
import { useCreateJob, useHealth } from "@/lib/queries";
import type { JobKind } from "@/lib/types";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Field, Input, Select } from "../ui/Field";
import { ErrorNote } from "../ui/States";
import { Tabs } from "../ui/Tabs";

type Source = "url" | "file";

const KINDS: { value: JobKind; label: string; help: string }[] = [
  { value: "render", label: "Full run: find, judge and render clips", help: "All 12 steps. Uses the Claude key." },
  { value: "monitor", label: "Find moments only (no Claude, no render)", help: "Steps 1–8: download, transcribe, score sheet." },
  { value: "download", label: "Download only", help: "Video and audio, nothing else." },
];

export function NewJobForm() {
  const router = useRouter();
  const create = useCreateJob();
  const { data: health } = useHealth();
  const [source, setSource] = useState<Source>("url");
  const [value, setValue] = useState("");
  const [kind, setKind] = useState<JobKind>("render");
  const [top, setTop] = useState(10);

  const needsKey = kind === "render" && health && !health.keys.anthropic;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const body = source === "url" ? { url: value.trim() } : { path: value.trim().replace(/^"|"$/g, "") };
    create.mutate({ kind, top, ...body }, { onSuccess: (job) => router.push(`/jobs/${job.id}`) });
  };

  return (
    <Card className="p-6">
      <form onSubmit={submit} className="grid gap-5">
        <Tabs<Source>
          value={source}
          onChange={(s) => { setSource(s); setValue(""); }}
          tabs={[{ value: "url", label: "Twitch VOD link" }, { value: "file", label: "Video file on this PC" }]}
        />

        <Field
          label={source === "url" ? "VOD link" : "File path"}
          hint={source === "url" ? "Like https://www.twitch.tv/videos/1234567890" : "Full path, e.g. D:\\streams\\vod.mp4 (quotes are fine)"}
        >
          <div className="relative">
            {source === "url"
              ? <Link2 size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground" />
              : <FileVideo size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground" />}
            <Input required autoFocus value={value} onChange={(e) => setValue(e.target.value)} className="pl-9"
              placeholder={source === "url" ? "https://www.twitch.tv/videos/…" : "C:\\videos\\stream.mp4"} />
          </div>
        </Field>

        <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
          <Field label="What to do" hint={KINDS.find((k) => k.value === kind)?.help}>
            <Select value={kind} onChange={(e) => setKind(e.target.value as JobKind)}>
              {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </Select>
          </Field>
          <Field label="Clips to make" hint="1–30">
            <Input type="number" min={1} max={30} value={top} onChange={(e) => setTop(Number(e.target.value) || 1)} />
          </Field>
        </div>

        {needsKey && <ErrorNote error="Full run needs ANTHROPIC_API_KEY in .env. Pick “Find moments only” or add the key and restart the API." />}
        <ErrorNote error={create.error} />

        <div className="flex justify-end">
          <Button type="submit" variant="primary" loading={create.isPending} disabled={!value.trim() || !!needsKey}>
            <Rocket size={16} /> Start
          </Button>
        </div>
      </form>
    </Card>
  );
}
