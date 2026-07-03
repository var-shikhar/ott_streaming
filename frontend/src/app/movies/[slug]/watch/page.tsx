import { notFound } from "next/navigation";
import MoviePlayer from "@/components/MoviePlayer";
import { serverFetch } from "@/lib/api-server";
import type { MovieDetail } from "@/lib/types";

export default async function MovieWatchPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const movie = await serverFetch<MovieDetail>(`/api/v1/movies/${slug}`);
  if (!movie || !movie.episode) notFound();
  return <MoviePlayer movie={movie} episode={movie.episode} />;
}
