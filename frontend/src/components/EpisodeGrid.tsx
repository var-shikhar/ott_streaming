import Link from "next/link";
import FallbackImage from "@/components/FallbackImage";
import type { SeriesDetail } from "@/lib/types";

export default function EpisodeGrid({ series }: { series: SeriesDetail }) {
  return (
    <div className="grid grid-cols-3 gap-2.5">
      {series.episodes.map((e) => (
        <Link key={e.id} href={`/watch/${series.slug}/${e.episode_number}`}
              className="group relative">
          <FallbackImage src={e.thumbnail_url} fallback={series.poster_url} alt={e.title}
               className={`aspect-[9/16] w-full rounded-md object-cover ring-1 ring-zinc-800 ${e.locked ? "opacity-50" : ""}`} />
          <span className="absolute left-1.5 top-1.5 rounded bg-zinc-950/80 px-1.5 py-0.5 text-[10px] font-semibold">
            {e.episode_number}
          </span>
          {e.locked && (
            <span className="absolute inset-0 flex items-center justify-center text-xl">🔒</span>
          )}
        </Link>
      ))}
    </div>
  );
}
