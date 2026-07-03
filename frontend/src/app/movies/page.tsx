import Link from "next/link";
import MovieHero from "@/components/MovieHero";
import MovieRail from "@/components/MovieRail";
import { serverFetch } from "@/lib/api-server";
import type { HomeData } from "@/lib/types";

export default async function MoviesHomePage() {
  const data = await serverFetch<HomeData>("/api/v1/movies/home");
  if (!data) {
    return <div className="p-10 text-center text-sm text-zinc-400">
      Could not reach the API. Is the backend running on port 8000?
    </div>;
  }
  return (
    <div className="animate-fade-in pb-4">
      <MovieHero items={data.featured} />
      {data.continue_watching.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-2 px-4 text-base font-bold">Continue Watching</h2>
          <div className="flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-none">
            {data.continue_watching.map((c) => (
              <Link key={c.episode_id} href={`/movies/${c.series.slug}/watch`}
                    className="w-40 shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={c.series.banner_url} alt={c.series.title}
                     className="aspect-video w-full rounded-lg object-cover ring-1 ring-zinc-800" />
                <p className="mt-1.5 line-clamp-1 text-xs font-medium">{c.series.title}</p>
                <p className="text-[10px] text-rose-400">Resume</p>
              </Link>
            ))}
          </div>
        </section>
      )}
      <MovieRail title="Trending Now" movies={data.trending} />
      <MovieRail title="New Releases" movies={data.new_releases} />
      {data.genre_rails.map((rail) => (
        <MovieRail key={rail.genre.slug} title={rail.genre.name} movies={rail.series} />
      ))}
    </div>
  );
}
