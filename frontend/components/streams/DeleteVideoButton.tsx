"use client";

import { Trash2 } from "lucide-react";
import { useDeleteStreamVideo } from "@/lib/queries";
import type { Stream } from "@/lib/types";
import { Button } from "../ui/Button";
import { useToast } from "../ui/Toast";

/** Permanently delete a stream's downloaded video to free space. Clips stay. Asks first. */
export function DeleteVideoButton({ stream }: { stream: Stream }) {
  const del = useDeleteStreamVideo();
  const toast = useToast();
  if (!stream.video_file || stream.id.startsWith("local-")) return null;   // never offer to delete your own files

  const onClick = () => {
    const ok = confirm(
      `Permanently delete the downloaded video of "${stream.title || stream.id}"?\n\n` +
      "This cannot be undone. Your clips, transcript and score sheet are kept, " +
      "but making new clips from this stream will need the video downloaded again.");
    if (ok) del.mutate(stream.id, { onSuccess: (r) => toast.ok(`Deleted, ${r.freed_gb} GB freed`), onError: toast.error });
  };

  return (
    <Button size="sm" variant="danger" loading={del.isPending} onClick={onClick} title="Delete the source video (clips stay)">
      <Trash2 size={14} /> Video
    </Button>
  );
}
