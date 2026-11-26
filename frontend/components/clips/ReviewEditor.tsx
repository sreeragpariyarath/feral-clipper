"use client";

import { useEffect, useState } from "react";
import { Copy, Save } from "lucide-react";
import { usePatchClip } from "@/lib/queries";
import type { Clip } from "@/lib/types";
import { Button } from "../ui/Button";
import { Card, CardHeader } from "../ui/Card";
import { Field, Input, Textarea } from "../ui/Field";
import { useToast } from "../ui/Toast";

/** Edit the post title and caption; copy them to the clipboard for uploading. */
export function ReviewEditor({ clip }: { clip: Clip }) {
  const patch = usePatchClip();
  const toast = useToast();
  const [title, setTitle] = useState(clip.title);
  const [caption, setCaption] = useState(clip.caption);

  useEffect(() => { setTitle(clip.title); setCaption(clip.caption); }, [clip.id, clip.title, clip.caption]);

  const dirty = title !== clip.title || caption !== clip.caption;
  const copy = async (text: string, what: string) => {
    try { await navigator.clipboard.writeText(text); toast.ok(`${what} copied`); } catch (e) { toast.error(e); }
  };

  return (
    <Card>
      <CardHeader title="Post text" action={
        <Button size="sm" variant="primary" disabled={!dirty} loading={patch.isPending}
          onClick={() => patch.mutate({ id: clip.id, patch: { title, caption } }, { onSuccess: () => toast.ok("Saved"), onError: toast.error })}>
          <Save size={14} /> Save
        </Button>
      } />
      <div className="grid gap-4 p-4">
        <Field label="Title" hint={`${title.length} / 100 characters (YouTube Shorts limit)`}>
          <div className="flex gap-2">
            <Input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
            <Button size="icon" aria-label="Copy title" onClick={() => copy(title, "Title")}><Copy size={14} /></Button>
          </div>
        </Field>
        <Field label="Caption and hashtags">
          <div className="flex gap-2">
            <Textarea value={caption} maxLength={2200} onChange={(e) => setCaption(e.target.value)} />
            <Button size="icon" aria-label="Copy caption" onClick={() => copy(caption, "Caption")}><Copy size={14} /></Button>
          </div>
        </Field>
      </div>
    </Card>
  );
}
