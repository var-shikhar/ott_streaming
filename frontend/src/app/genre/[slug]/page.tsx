import { notFound } from "next/navigation";
import SeriesCard from "@/components/SeriesCard";
import { serverFetch } from "@/lib/api-server";
import type { GenreOut, SeriesSummary } from "@/lib/types";

export default async function GenrePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await serverFetch<{ genre: GenreOut; series: SeriesSummary[] }>(
    `/api/v1/genres/${slug}/series`);
  if (!data) notFound();
  return (
    <div className="px-4 py-4">
      <h1 className="text-xl font-bold">{data.genre.name}</h1>
      <div className="mt-4 grid grid-cols-3 gap-2.5">
        {data.series.map((s) => <SeriesCard key={s.id} series={s} />)}
      </div>
    </div>
  );
}
