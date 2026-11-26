"use client";

import { useEffect, useState } from "react";
import { useUpdatePost } from "@/lib/queries";
import type { Post } from "@/lib/types";
import { Input } from "../ui/Field";
import { useToast } from "../ui/Toast";

/** Views typed in by hand; saved when the field loses focus or Enter is pressed. */
export function ViewsInput({ post }: { post: Post }) {
  const update = useUpdatePost();
  const toast = useToast();
  const [value, setValue] = useState(String(post.views));
  useEffect(() => setValue(String(post.views)), [post.views]);

  const save = () => {
    const views = Math.max(0, Math.round(Number(value.replaceAll(",", "")) || 0));
    if (views === post.views) return setValue(String(post.views));
    update.mutate({ id: post.id, patch: { views } }, { onError: toast.error });
  };

  return (
    <div className="w-28 shrink-0">
      <Input aria-label="Views" inputMode="numeric" value={value} disabled={update.isPending}
        onChange={(e) => setValue(e.target.value)} onBlur={save}
        onKeyDown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()}
        className="text-right tabular-nums" />
    </div>
  );
}
