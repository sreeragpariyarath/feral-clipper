"use client";

import { useState } from "react";
import { startJob, type Job, type JobMode } from "../../lib/jobs";
import { Button } from "../ui/Button";

const MODE_HELP: Record<JobMode, string> = {
  download: "Download the video and audio only.",
  monitor: "Download, then find the best moments and save a score sheet. No rendering.",
  render: "Download, find moments, and render the top clips. Needs the API key in .env.",
};

type Props = {
  onStarted: (job: Job) => void;
};

export function NewStreamForm({ onStarted }: Props) {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<JobMode>("monitor");
  const [top, setTop] = useState(10);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const job = await startJob(url.trim(), mode, top);
      onStarted(job);
      setUrl("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the job");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid max-w-2xl gap-4 rounded-2xl border bg-card p-5">
      <label className="grid gap-1.5 text-sm font-medium">
        Twitch VOD link
        <input
          type="url"
          required
          placeholder="https://www.twitch.tv/videos/2934513082"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="rounded-lg border bg-background px-3 py-2 text-sm font-normal outline-none"
        />
      </label>

      <div className="grid gap-2 text-sm font-medium">
        What to do
        <div role="group" aria-label="Job type" className="flex flex-wrap gap-1 rounded-xl bg-muted p-1">
          {(["download", "monitor", "render"] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => setMode(value)}
              className={
                "rounded-lg px-3 py-1.5 text-xs font-medium capitalize " +
                (mode === value ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")
              }
            >
              {value}
            </button>
          ))}
        </div>
        <span className="text-xs font-normal text-muted-foreground">{MODE_HELP[mode]}</span>
      </div>

      <label className="grid w-40 gap-1.5 text-sm font-medium">
        Top moments
        <input
          type="number"
          min={1}
          max={30}
          value={top}
          onChange={(e) => setTop(Number(e.target.value))}
          className="rounded-lg border bg-background px-3 py-2 text-sm font-normal outline-none"
        />
      </label>

      {error && <p role="alert" className="text-sm text-red-500">{error}</p>}

      <div>
        <Button type="submit" disabled={busy || !url.trim()} className="bg-primary px-4 py-2 font-semibold text-primary-foreground">
          {busy ? "Starting…" : "Start"}
        </Button>
      </div>
    </form>
  );
}
