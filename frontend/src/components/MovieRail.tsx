import MovieCard from "@/components/MovieCard";
import type { SeriesSummary } from "@/lib/types";

export default function MovieRail({ title, movies }: { title: string; movies: SeriesSummary[] }) {
  if (!movies.length) return null;
  return (
    <section className="mt-6">
      <h2 className="mb-2 px-4 text-base font-bold">{title}</h2>
      <div className="flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-none">
        {movies.map((m) => <MovieCard key={m.id} movie={m} />)}
      </div>
    </section>
  );
}
