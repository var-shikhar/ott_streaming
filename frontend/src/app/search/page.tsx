"use client";

import { useEffect, useState } from "react";
import MovieCard from "@/components/MovieCard";
import SeriesCard from "@/components/SeriesCard";
import { apiFetch } from "@/lib/api-client";
import type { SeriesSummary } from "@/lib/types";

const FILTERS = [
  { value: "", label: "All" },
  { value: "series", label: "Series" },
  { value: "movie", label: "Movies" },
] as const;

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [type, setType] = useState<"" | "series" | "movie">("");
  const [results, setResults] = useState<SeriesSummary[]>([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    const query = q.trim();
    if (!query) { setResults([]); setSearched(false); return; }
    const t = setTimeout(() => {
      const typeParam = type ? `&content_type=${type}` : "";
      apiFetch<SeriesSummary[]>(`/api/v1/search?q=${encodeURIComponent(query)}${typeParam}`)
        .then((r) => { setResults(r); setSearched(true); })
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(t);
  }, [q, type]);

  const seriesResults = results.filter((s) => s.content_type !== "movie");
  const movieResults = results.filter((s) => s.content_type === "movie");

  return (
    <div className="px-4 py-4">
      <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
             placeholder="Search series & films..."
             className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-rose-500" />
      <div className="mt-3 flex gap-2">
        {FILTERS.map((f) => (
          <button key={f.value} onClick={() => setType(f.value)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    type === f.value ? "bg-rose-600 text-white"
                                     : "bg-zinc-800 text-zinc-400 active:text-white"}`}>
            {f.label}
          </button>
        ))}
      </div>
      {seriesResults.length > 0 && (
        <div className="mt-4 grid grid-cols-3 gap-2.5">
          {seriesResults.map((s) => <SeriesCard key={s.id} series={s} />)}
        </div>
      )}
      {movieResults.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2.5">
          {movieResults.map((m) => <MovieCard key={m.id} movie={m} />)}
        </div>
      )}
      {searched && results.length === 0 && (
        <p className="mt-6 text-sm text-zinc-400">No results for &quot;{q}&quot;</p>
      )}
    </div>
  );
}
