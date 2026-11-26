/** Small display helpers. Times are shown in the browser's local time zone. */

export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

export function localTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return `${Math.floor(diff / 86400)} d ago`;
}

export function duration(from: string | null, to: string | null): string {
  if (!from) return "";
  const end = to ? new Date(to).getTime() : Date.now();
  return clock((end - new Date(from).getTime()) / 1000);
}

export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}`);

export function streamName(id: string): string {
  if (id.startsWith("twitchvod-v")) return "Twitch VOD " + id.slice(11);
  if (id.startsWith("local-")) return id.slice(6).replace(/-[0-9a-f]{6}$/, "").replaceAll("-", " ");
  return id;
}
