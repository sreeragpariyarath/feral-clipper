import { Film } from "lucide-react";
import { Button } from "../ui/Button";

type Props = {
  message: string;
  onClear: () => void;
};

/** Shown when no clip matches the filters, or when there is nothing to show. */
export function EmptyState({ message, onClear }: Props) {
  return (
    <div className="grid min-h-56 place-items-center rounded-2xl border border-dashed bg-muted/25 p-6 text-center">
      <div>
        <Film size={24} className="mx-auto mb-3 text-muted-foreground" aria-hidden="true" />
        <p className="font-semibold">{message || "No matching clips"}</p>
        {!message && (
          <Button variant="link" onClick={onClear}>
            Clear filters
          </Button>
        )}
      </div>
    </div>
  );
}
