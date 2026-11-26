import { Search } from "lucide-react";

type Props = {
  search: string;
  onSearch: (value: string) => void;
};

export function PageHeader({ search, onSearch }: Props) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b pb-5">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Clip library</h1>
      <label className="flex w-full items-center gap-2 rounded-xl border bg-background px-3 sm:w-64">
        <Search size={16} className="shrink-0 text-muted-foreground" />
        <input
          type="search"
          aria-label="Search by title"
          placeholder="Search clips"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          className="min-w-0 w-full bg-transparent py-2.5 text-sm outline-none"
        />
      </label>
    </header>
  );
}
