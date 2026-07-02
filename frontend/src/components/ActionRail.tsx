"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { EpisodeSummary } from "@/lib/types";

function fmt(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export default function ActionRail({ episode, seriesTitle, onOpenComments }: {
  episode: EpisodeSummary;
  seriesTitle: string;
  onOpenComments: () => void;
}) {
  const router = useRouter();
  const [liked, setLiked] = useState(episode.liked_by_me);
  const [likeCount, setLikeCount] = useState(episode.like_count);
  const [pop, setPop] = useState(false);
  const [toast, setToast] = useState("");

  async function toggleLike() {
    try {
      const res = await apiFetch<{ liked: boolean; like_count: number }>(
        `/api/v1/episodes/${episode.id}/like`,
        { method: liked ? "DELETE" : "POST" });
      setLiked(res.liked);
      setLikeCount(res.like_count);
      if (res.liked) {
        setPop(true);
        setTimeout(() => setPop(false), 350);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push("/login");
    }
  }

  async function share() {
    const url = `${window.location.origin}/watch/${window.location.pathname.split("/")[2]}/${episode.episode_number}`;
    const data = { title: `${seriesTitle} — ${episode.title}`, url };
    if (navigator.share) {
      await navigator.share(data).catch(() => {});
    } else {
      await navigator.clipboard.writeText(url).catch(() => {});
      setToast("Link copied!");
      setTimeout(() => setToast(""), 1600);
    }
  }

  const btn = "flex flex-col items-center gap-1 text-white drop-shadow-md";
  return (
    <div className="absolute bottom-24 right-2 z-20 flex flex-col items-center gap-5">
      <button onClick={toggleLike} className={btn} aria-label="Like">
        <svg viewBox="0 0 24 24"
             className={`h-8 w-8 transition-transform duration-300 ${pop ? "scale-125" : ""} ${
               liked ? "fill-rose-500" : "fill-white/90"}`}>
          <path d="M12 21s-7.5-4.7-10-9C.6 9.3 2 5.5 5.5 5 7.7 4.7 9.5 6 12 8.5 14.5 6 16.3 4.7 18.5 5 22 5.5 23.4 9.3 22 12c-2.5 4.3-10 9-10 9Z" />
        </svg>
        <span className="text-xs font-semibold">{fmt(likeCount)}</span>
      </button>
      <button onClick={onOpenComments} className={btn} aria-label="Comments">
        <svg viewBox="0 0 24 24" className="h-8 w-8 fill-white/90">
          <path d="M12 3C6.5 3 2 6.9 2 11.7c0 2.7 1.4 5 3.7 6.6-.1 1-.6 2.4-1.6 3.7 2-.3 3.6-1 4.7-1.8 1 .3 2.1.4 3.2.4 5.5 0 10-3.9 10-8.9S17.5 3 12 3Z" />
        </svg>
        <span className="text-xs font-semibold">{fmt(episode.comment_count)}</span>
      </button>
      <button onClick={share} className={btn} aria-label="Share">
        <svg viewBox="0 0 24 24" className="h-8 w-8 fill-white/90">
          <path d="M14 9V5l8 7-8 7v-4.1c-5 0-8.5 1.6-11 5.1 1-5 4-10 11-11Z" />
        </svg>
        <span className="text-xs font-semibold">Share</span>
      </button>
      {toast && (
        <div className="absolute -left-24 bottom-0 whitespace-nowrap rounded-full bg-zinc-800/95 px-3 py-1.5 text-xs animate-fade-in">
          {toast}
        </div>
      )}
    </div>
  );
}
