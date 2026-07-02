import Link from "next/link";
import type { SeriesSummary } from "@/lib/types";

export default function SeriesCard({ series }: { series: SeriesSummary }) {
  return (
    <Link href={`/series/${series.slug}`}
          className="group w-28 shrink-0" title={series.title}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={series.poster_url} alt={series.title}
           className="aspect-[9/16] w-full rounded-lg object-cover ring-1 ring-zinc-800 transition active:ring-rose-500" />
      <p className="mt-1.5 line-clamp-1 text-xs font-medium">{series.title}</p>
      <p className="text-[10px] text-zinc-500">{series.episode_count} eps</p>
    </Link>
  );
}
