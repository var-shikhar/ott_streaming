import { notFound } from "next/navigation";
import CastList from "@/components/CastList";
import { movieMeta } from "@/components/MovieCard";
import MoviePlayer from "@/components/MoviePlayer";
import MovieRail from "@/components/MovieRail";
import { serverFetch } from "@/lib/api-server";
import type { MovieDetail } from "@/lib/types";

export default async function MovieWatchPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const movie = await serverFetch<MovieDetail>(`/api/v1/movies/${slug}`);
  if (!movie || !movie.episode) notFound();
  const meta = [
    movieMeta(movie),
    movie.maturity_rating || null,
    movie.genres.join(" · ") || null,
  ].filter(Boolean).join(" · ");
  return (
    <div className="min-h-dvh bg-black">
      <MoviePlayer movie={movie} episode={movie.episode} />
      <div className="px-4 pb-6">
        <h1 className="mt-3 text-xl font-extrabold leading-tight">{movie.title}</h1>
        <p className="mt-1 text-xs text-zinc-400">{meta}</p>
        <p className="mt-2 text-sm leading-relaxed text-zinc-300">{movie.synopsis}</p>
        <CastList credits={movie.credits} />
      </div>
      <MovieRail title="More Like This" movies={movie.related} />
    </div>
  );
}
