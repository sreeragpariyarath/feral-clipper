import type { Session } from "../../lib/types";

type Props = {
  sessions: Session[];
  value: string;
  disabled: boolean;
  onChange: (id: string) => void;
};

export function StreamSelect({ sessions, value, disabled, onChange }: Props) {
  return (
    <label className="grid min-w-0 max-w-full gap-1.5 text-xs font-semibold text-muted-foreground">
      Stream
      <select
        value={value}
        disabled={disabled || !sessions.length}
        onChange={(event) => onChange(event.target.value)}
        className="w-full max-w-md rounded-lg border bg-background px-3 py-2 text-sm font-medium text-foreground"
      >
        {sessions.map((item) => (
          <option key={item.id} value={item.id}>
            {item.title} · {item.clips} clips
          </option>
        ))}
      </select>
    </label>
  );
}
