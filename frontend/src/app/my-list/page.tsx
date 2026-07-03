import Link from "next/link";
import { redirect } from "next/navigation";
import MovieCard from "@/components/MovieCard";
import SeriesCard from "@/components/SeriesCard";
import { serverFetch } from "@/lib/api-server";
import type { SeriesSummary, User } from "@/lib/types";

export default async function MyListPage() {
  const user = await serverFetch<User>("/api/v1/auth/me");
  if (!user) redirect("/login?next=/my-list");
  const items = (await serverFetch<SeriesSummary[]>("/api/v1/watchlist")) ?? [];
  const seriesItems = items.filter((s) => s.content_type !== "movie");
  const movieItems = items.filter((s) => s.content_type === "movie");
  return (
    <div className="px-4 py-4">
      <h1 className="text-xl font-bold">My List</h1>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-zinc-400">
          Your list is empty. <Link href="/" className="text-rose-400">Find something to watch</Link>
        </p>
      ) : (
        <>
          {seriesItems.length > 0 && (
            <>
              <h2 className="mt-4 text-sm font-bold text-zinc-300">Series</h2>
              <div className="mt-2 grid grid-cols-3 gap-2.5">
                {seriesItems.map((s) => <SeriesCard key={s.id} series={s} />)}
              </div>
            </>
          )}
          {movieItems.length > 0 && (
            <>
              <h2 className="mt-4 text-sm font-bold text-zinc-300">Movies</h2>
              <div className="mt-2 grid grid-cols-2 gap-2.5">
                {movieItems.map((m) => <MovieCard key={m.id} movie={m} />)}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
