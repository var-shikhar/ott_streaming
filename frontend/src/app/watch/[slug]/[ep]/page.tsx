import { notFound } from "next/navigation";
import Player from "@/components/Player";
import { serverFetch } from "@/lib/api-server";
import type { SeriesDetail } from "@/lib/types";

export default async function WatchPage({ params }: {
  params: Promise<{ slug: string; ep: string }>;
}) {
  const { slug, ep } = await params;
  const episodeNumber = Number(ep);
  const series = await serverFetch<SeriesDetail>(`/api/v1/series/${slug}`);
  if (!series || !Number.isInteger(episodeNumber) || episodeNumber < 1) notFound();
  if (!series.episodes.some((e) => e.episode_number === episodeNumber)) notFound();
  return <Player series={series} episodeNumber={episodeNumber} />;
}
