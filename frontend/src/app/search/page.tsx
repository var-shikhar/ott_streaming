"use client";

import { useEffect, useState } from "react";
import SeriesCard from "@/components/SeriesCard";
import { apiFetch } from "@/lib/api-client";
import type { SeriesSummary } from "@/lib/types";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SeriesSummary[]>([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    const query = q.trim();
    if (!query) { setResults([]); setSearched(false); return; }
    const t = setTimeout(() => {
      apiFetch<SeriesSummary[]>(`/api/v1/search?q=${encodeURIComponent(query)}`)
        .then((r) => { setResults(r); setSearched(true); })
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="px-4 py-4">
      <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
             placeholder="Search series..."
             className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-rose-500" />
      <div className="mt-4 grid grid-cols-3 gap-2.5">
        {results.map((s) => <SeriesCard key={s.id} series={s} />)}
      </div>
      {searched && results.length === 0 && (
        <p className="mt-6 text-sm text-zinc-400">No results for &quot;{q}&quot;</p>
      )}
    </div>
  );
}
