"use client";

import { useState } from "react";
import { Sidebar } from "../components/layout/Sidebar";
import { PageHeader } from "../components/library/PageHeader";
import { StreamSelect } from "../components/library/StreamSelect";
import { StatusFilter } from "../components/library/StatusFilter";
import { EmptyState } from "../components/library/EmptyState";
import { ClipGrid } from "../components/library/ClipGrid";
import { useLibrary } from "../lib/useLibrary";

/** Home page: the clip library. The pieces live in components/, the data logic in lib/useLibrary.ts. */
export default function Library() {
  const [collapsed, setCollapsed] = useState(false);
  const library = useLibrary();

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />

      <main className="mx-auto min-w-0 w-full max-w-7xl p-6 md:p-10">
        <PageHeader search={library.search} onSearch={library.setSearch} />

        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <StreamSelect
            sessions={library.sessions}
            value={library.session}
            disabled={library.saving !== null}
            onChange={library.setSession}
          />
          <StatusFilter value={library.filter} onChange={library.setFilter} />
        </div>

        <p role="status" className={library.visible.length ? "mb-3 text-sm text-muted-foreground" : "sr-only"}>
          {library.message || library.visible.length + " clips"}
        </p>

        {!library.visible.length && <EmptyState message={library.message} onClear={library.clearFilters} />}

        <ClipGrid
          clips={library.visible}
          session={library.session}
          busy={library.saving !== null}
          onReview={library.review}
          onDelete={library.remove}
        />
      </main>
    </div>
  );
}
