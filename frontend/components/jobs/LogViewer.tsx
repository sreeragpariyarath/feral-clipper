"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Terminal } from "lucide-react";
import { cn } from "../ui/cn";

/** Collapsible tail of the job log; sticks to the bottom while new lines arrive. */
export function LogViewer({ lines }: { lines: string[] }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const el = box.current;
    if (open && el) el.scrollTop = el.scrollHeight;
  }, [lines, open]);

  return (
    <div className="rounded-xl border bg-card">
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold">
        <span className="flex items-center gap-2"><Terminal size={16} /> Log <span className="font-normal text-muted-foreground">({lines.length} lines)</span></span>
        <ChevronDown size={16} className={cn("transition", open && "rotate-180")} />
      </button>
      {open && (
        <pre ref={box} className="max-h-96 overflow-auto border-t bg-zinc-950 p-4 font-mono text-xs leading-relaxed text-zinc-200">
          {lines.length ? lines.join("\n") : "No output yet."}
        </pre>
      )}
    </div>
  );
}
