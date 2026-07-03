import Link from "next/link";
import type { SeriesSummary } from "@/lib/types";

export function movieMeta(m: SeriesSummary): string {
  const mins = m.duration_seconds > 0 ? Math.max(1, Math.round(m.duration_seconds / 60)) : 0;
  return [m.release_year ? String(m.release_year) : null, mins ? `${mins}m` : null]
    .filter(Boolean).join(" · ");
}

export default function MovieCard({ movie }: { movie: SeriesSummary }) {
  return (
    <Link href={`/movies/${movie.slug}`}
          className="group w-40 shrink-0 transition-transform duration-200 active:scale-95"
          title={movie.title}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={movie.banner_url} alt={movie.title} loading="lazy"
           className="aspect-video w-full rounded-lg object-cover ring-1 ring-zinc-800 transition duration-200 group-hover:ring-rose-500/70 group-active:ring-rose-500" />
      <p className="mt-1.5 line-clamp-1 text-xs font-medium">{movie.title}</p>
      <p className="text-[10px] text-zinc-500">{movieMeta(movie)}</p>
    </Link>
  );
}
