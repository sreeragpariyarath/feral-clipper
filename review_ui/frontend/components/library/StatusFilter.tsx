import type { FilterValue } from "../../lib/types";

const OPTIONS: { value: FilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: "To review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

type Props = {
  value: FilterValue;
  onChange: (value: FilterValue) => void;
};

export function StatusFilter({ value, onChange }: Props) {
  return (
    <div aria-label="Review status" role="group" className="flex flex-wrap gap-1 rounded-xl bg-muted p-1">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={
            "rounded-lg px-3 py-1.5 text-xs font-medium " +
            (value === option.value ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
