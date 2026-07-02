import Link from "next/link";
import { notFound } from "next/navigation";
import EpisodeGrid from "@/components/EpisodeGrid";
import WatchlistButton from "@/components/WatchlistButton";
import { serverFetch } from "@/lib/api-server";
import type { SeriesDetail } from "@/lib/types";

export default async function SeriesPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const series = await serverFetch<SeriesDetail>(`/api/v1/series/${slug}`);
  if (!series) notFound();
  return (
    <div className="animate-fade-in pb-4">
      <div className="relative h-52 w-full overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={series.banner_url} alt={series.title} className="h-full w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 to-transparent" />
      </div>
      <div className="px-4">
        <h1 className="mt-3 text-2xl font-extrabold leading-tight">{series.title}</h1>
        <p className="mt-1 text-xs text-zinc-400">
          {series.genres.join(" · ")} · {series.episode_count} episodes · first {series.free_episode_count} free
        </p>
        <p className="mt-2 text-sm leading-relaxed text-zinc-300">{series.synopsis}</p>
        <div className="mt-4 flex gap-2">
          <Link href={`/watch/${series.slug}/1`}
                className="flex-1 rounded-lg bg-rose-600 py-2.5 text-center text-sm font-semibold active:bg-rose-500">
            ▶ Play Ep 1
          </Link>
          <WatchlistButton seriesId={series.id} />
        </div>
        <h2 className="mb-2 mt-6 text-base font-bold">Episodes</h2>
        <EpisodeGrid series={series} />
      </div>
    </div>
  );
}
