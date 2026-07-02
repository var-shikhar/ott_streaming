import Link from "next/link";
import { redirect } from "next/navigation";
import SeriesCard from "@/components/SeriesCard";
import { serverFetch } from "@/lib/api-server";
import type { SeriesSummary, User } from "@/lib/types";

export default async function MyListPage() {
  const user = await serverFetch<User>("/api/v1/auth/me");
  if (!user) redirect("/login?next=/my-list");
  const items = (await serverFetch<SeriesSummary[]>("/api/v1/watchlist")) ?? [];
  return (
    <div className="px-4 py-4">
      <h1 className="text-xl font-bold">My List</h1>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-zinc-400">
          Your list is empty. <Link href="/" className="text-rose-400">Find something to watch</Link>
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-3 gap-2.5">
          {items.map((s) => <SeriesCard key={s.id} series={s} />)}
        </div>
      )}
    </div>
  );
}
