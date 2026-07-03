import Link from "next/link";
import { notFound } from "next/navigation";
import CastList from "@/components/CastList";
import { movieMeta } from "@/components/MovieCard";
import MovieRail from "@/components/MovieRail";
import StillsGallery from "@/components/StillsGallery";
import WatchlistButton from "@/components/WatchlistButton";
import { serverFetch } from "@/lib/api-server";
import type { MovieDetail } from "@/lib/types";

export default async function MoviePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const movie = await serverFetch<MovieDetail>(`/api/v1/movies/${slug}`);
  if (!movie) notFound();
  const meta = [
    movieMeta(movie),
    movie.maturity_rating || null,
    movie.genres.join(" · ") || null,
  ].filter(Boolean).join(" · ");
  return (
    <div className="animate-fade-in pb-4">
      <div className="relative w-full overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={movie.banner_url} alt={movie.title}
             className="aspect-video w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 to-transparent" />
      </div>
      <div className="px-4">
        <h1 className="mt-3 text-2xl font-extrabold leading-tight">{movie.title}</h1>
        <p className="mt-1 text-xs text-zinc-400">{meta}</p>
        <p className="mt-2 text-sm leading-relaxed text-zinc-300">{movie.synopsis}</p>
        <div className="mt-4 flex gap-2">
          {movie.episode ? (
            <Link href={`/movies/${movie.slug}/watch`}
                  className="flex-1 rounded-lg bg-rose-600 py-2.5 text-center text-sm font-semibold active:bg-rose-500">
              ▶ {movie.episode.is_free ? "Play" : "Play · Premium"}
            </Link>
          ) : (
            <span className="flex-1 rounded-lg bg-zinc-800 py-2.5 text-center text-sm font-semibold text-zinc-500">
              Coming soon
            </span>
          )}
          <WatchlistButton seriesId={movie.id} />
        </div>
        <CastList credits={movie.credits} />
        <StillsGallery stills={movie.stills} fallback={movie.banner_url} />
      </div>
      <MovieRail title="More Like This" movies={movie.related} />
    </div>
  );
}
