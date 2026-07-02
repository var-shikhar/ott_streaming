"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { SeriesSummary } from "@/lib/types";

export default function WatchlistButton({ seriesId }: { seriesId: string }) {
  const [inList, setInList] = useState<boolean | null>(null);
  const router = useRouter();

  useEffect(() => {
    apiFetch<SeriesSummary[]>("/api/v1/watchlist")
      .then((items) => setInList(items.some((s) => s.id === seriesId)))
      .catch(() => setInList(false));
  }, [seriesId]);

  async function toggle() {
    try {
      if (inList) {
        await apiFetch(`/api/v1/watchlist/${seriesId}`, { method: "DELETE" });
        setInList(false);
      } else {
        await apiFetch("/api/v1/watchlist", {
          method: "POST", body: JSON.stringify({ series_id: seriesId }),
        });
        setInList(true);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push("/login");
    }
  }

  return (
    <button onClick={toggle}
            className="flex-1 rounded-lg bg-zinc-800 py-2.5 text-sm font-semibold active:bg-zinc-700">
      {inList ? "✓ In My List" : "+ My List"}
    </button>
  );
}
