# Feral Clipper — frontend

Next.js 15 + React 19 + Tailwind 4 + TanStack Query. Talks only to the local API (`backend/`, port 8766).

```
pnpm install
pnpm dev          # http://127.0.0.1:3107
pnpm typecheck
pnpm build
```

`start_all.bat` in the repo root starts the API, the worker and this frontend together.

- `/api/v1/*` and `/media/*` are proxied to the API (`next.config.ts`; set `GTA_REVIEW_ORIGIN` if it runs elsewhere).
- Live updates come from one Server-Sent Events connection straight to the API (`lib/useLiveEvents.ts`;
  set `NEXT_PUBLIC_API_ORIGIN` if it runs elsewhere). The dev proxy buffers streams, so it is not used for events.

## Layout

| Folder | What is in it |
|---|---|
| `app/` | One folder per page: dashboard, new job, jobs, clips, streams, posted, campaigns, trash, settings |
| `components/ui/` | Design-system pieces: Button, Card, Badge, Progress, Tabs, Field, Toast, States |
| `components/layout/` | App shell: sidebar, activity panel, theme toggle, disk banner |
| `components/<area>/` | Pieces for one area: `jobs`, `clips`, `posts`, `campaigns`, `streams`, `settings`, `dashboard` |
| `lib/` | `api.ts` (typed client), `queries.ts` (query keys and hooks), `types.ts`, `useLiveEvents.ts`, `format.ts` |
