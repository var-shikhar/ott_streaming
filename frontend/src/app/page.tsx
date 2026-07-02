import Link from "next/link";
import Hero from "@/components/Hero";
import Rail from "@/components/Rail";
import { serverFetch } from "@/lib/api-server";
import type { HomeData } from "@/lib/types";

export default async function HomePage() {
  const data = await serverFetch<HomeData>("/api/v1/home");
  if (!data) {
    return <div className="p-10 text-center text-sm text-zinc-400">
      Could not reach the API. Is the backend running on port 8000?
    </div>;
  }
  return (
    <div className="pb-4">
      <Hero items={data.featured} />
      {data.continue_watching.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-2 px-4 text-base font-bold">Continue Watching</h2>
          <div className="flex gap-3 overflow-x-auto px-4 pb-2">
            {data.continue_watching.map((c) => (
              <Link key={c.episode_id} href={`/watch/${c.series.slug}/${c.episode_number}`}
                    className="w-28 shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={c.series.poster_url} alt={c.series.title}
                     className="aspect-[9/16] w-full rounded-lg object-cover ring-1 ring-zinc-800" />
                <p className="mt-1.5 line-clamp-1 text-xs font-medium">{c.series.title}</p>
                <p className="text-[10px] text-rose-400">Resume Ep {c.episode_number}</p>
              </Link>
            ))}
          </div>
        </section>
      )}
      <Rail title="Trending Now" series={data.trending} />
      <Rail title="New Releases" series={data.new_releases} />
      {data.genre_rails.map((rail) => (
        <Rail key={rail.genre.slug} title={rail.genre.name} series={rail.series} />
      ))}
    </div>
  );
}
