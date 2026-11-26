import { Card } from "../ui/Card";
import { Bone, Line, times } from "./bones";

const COLUMNS = [
  ["Stream", ""], ["Length", ""], ["Clips", "text-right"], ["Ready", "text-right"],
  ["Approved", "text-right"], ["Size", "text-right"], ["Updated", ""], ["", ""],
] as const;

/** Mirrors the table on the Streams page. */
export function StreamTableSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b text-left text-xs text-muted-foreground">
          <tr>{COLUMNS.map(([name, align], i) => <th key={i} className={`px-4 py-3 font-medium ${align}`}>{name}</th>)}</tr>
        </thead>
        <tbody>
          {times(rows).map((r) => (
            <tr key={r} className="border-b last:border-0">
              <td className="max-w-80 px-4 py-3">
                <span className="font-medium"><Line className="w-48" /></span>
                <p className="text-xs"><Line className="w-24" /></p>
              </td>
              {COLUMNS.slice(1, -1).map(([name, align]) => (
                <td key={name} className={`px-4 py-3 whitespace-nowrap ${align}`}><Line className={name === "Updated" ? "w-24" : "w-8"} /></td>
              ))}
              <td className="px-4 py-3"><Bone className="ml-auto h-8 w-20" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
