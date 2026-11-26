"use client";

import { useState, type FormEvent } from "react";
import { CheckCircle2 } from "lucide-react";
import { useCreatePost, usePosts } from "@/lib/queries";
import type { Clip, Platform } from "@/lib/types";
import { Button } from "../ui/Button";
import { Input } from "../ui/Field";
import { useToast } from "../ui/Toast";

/** After uploading by hand, record where the clip went (the link is optional). */
export function MarkPosted({ clip, platform, title }: { clip: Clip; platform: Platform; title: string }) {
  const create = useCreatePost();
  const { data: posts = [] } = usePosts(clip.id);
  const toast = useToast();
  const [url, setUrl] = useState("");
  const already = posts.filter((p) => p.platform === platform);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate({ clip_id: clip.id, platform, url, title }, {
      onSuccess: () => { setUrl(""); toast.ok("Saved. Add views later on the Posted page."); },
      onError: toast.error,
    });
  };

  return (
    <form onSubmit={submit} className="grid gap-2 border-t pt-4">
      {!!already.length && (
        <p className="flex items-center gap-1.5 text-sm text-emerald-600">
          <CheckCircle2 size={16} /> Posted here {already.length > 1 ? `${already.length} times` : "already"}
        </p>
      )}
      <div className="flex gap-2">
        <Input placeholder="Link to the post (optional)" value={url} onChange={(e) => setUrl(e.target.value)} type="url" />
        <Button type="submit" variant="primary" loading={create.isPending}>Mark as posted</Button>
      </div>
    </form>
  );
}
