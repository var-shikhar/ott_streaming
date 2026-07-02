"use client";

import Hls from "hls.js";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import Paywall from "@/components/Paywall";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { PlaybackInfo, SeriesDetail } from "@/lib/types";

export default function Player({ series, episodeNumber }: {
  series: SeriesDetail; episodeNumber: number;
}) {
  const episode = series.episodes.find((e) => e.episode_number === episodeNumber);
  const videoRef = useRef<HTMLVideoElement>(null);
  const lastSaved = useRef(0);
  const router = useRouter();
  const [state, setState] = useState<"loading" | "playing" | "locked" | "error">("loading");

  const hasNext = series.episodes.some((e) => e.episode_number === episodeNumber + 1);
  const hasPrev = episodeNumber > 1;

  const saveProgress = useCallback((position: number, completed: boolean) => {
    if (!episode) return;
    apiFetch(`/api/v1/progress/${episode.id}`, {
      method: "PUT",
      body: JSON.stringify({ position_seconds: Math.floor(position), completed }),
    }).catch(() => {}); // guests get a 401 — fine, progress just isn't saved
  }, [episode]);

  useEffect(() => {
    if (!episode) { setState("error"); return; }
    let hls: Hls | null = null;
    let cancelled = false;
    setState("loading");
    apiFetch<PlaybackInfo>(`/api/v1/episodes/${episode.id}/playback`)
      .then((playback) => {
        if (cancelled) return;
        const video = videoRef.current;
        if (!video) return;
        if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = playback.url;
        } else if (Hls.isSupported()) {
          hls = new Hls({ xhrSetup: (xhr) => { xhr.withCredentials = true; } });
          hls.loadSource(playback.url);
          hls.attachMedia(video);
          hls.on(Hls.Events.ERROR, (_evt, data) => {
            if (data.fatal) setState("error");
          });
        } else {
          setState("error");
          return;
        }
        video.addEventListener("loadedmetadata", () => {
          if (playback.resume_position > 0 && playback.resume_position < video.duration - 2) {
            video.currentTime = playback.resume_position;
          }
          video.play().catch(() => {});
        }, { once: true });
        setState("playing");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.code === "subscription_required") setState("locked");
        else setState("error");
      });
    return () => {
      cancelled = true;
      const video = videoRef.current;
      if (video && video.currentTime > 0) saveProgress(video.currentTime, false);
      hls?.destroy();
    };
  }, [episode, saveProgress]);

  function onTimeUpdate() {
    const video = videoRef.current;
    if (!video) return;
    if (video.currentTime - lastSaved.current >= 5) {
      lastSaved.current = video.currentTime;
      saveProgress(video.currentTime, false);
    }
  }

  function onEnded() {
    const video = videoRef.current;
    if (video) saveProgress(video.duration, true);
    if (hasNext) router.push(`/watch/${series.slug}/${episodeNumber + 1}`);
    else router.push(`/series/${series.slug}`);
  }

  return (
    <div className="flex h-[calc(100dvh-3rem)] flex-col bg-black">
      <div className="flex items-center justify-between px-3 py-2 text-sm">
        <Link href={`/series/${series.slug}`} className="text-zinc-400 active:text-white">
          ← {series.title}
        </Link>
        <span className="text-xs text-zinc-500">
          Ep {episodeNumber} / {series.episode_count}
        </span>
      </div>
      <div className="relative min-h-0 flex-1">
        {state === "locked" && <Paywall seriesSlug={series.slug} poster={series.poster_url} />}
        {state === "error" && (
          <div className="flex h-full items-center justify-center text-sm text-zinc-400">
            Playback failed.
            <button className="ml-2 underline" onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}
        {(state === "playing" || state === "loading") && (
          <video ref={videoRef} controls playsInline
                 onTimeUpdate={onTimeUpdate} onEnded={onEnded}
                 className="h-full w-full object-contain" />
        )}
      </div>
      <div className="flex items-center justify-between px-3 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        <button disabled={!hasPrev}
                onClick={() => router.push(`/watch/${series.slug}/${episodeNumber - 1}`)}
                className="rounded-lg bg-zinc-800 px-4 py-2 text-sm disabled:opacity-40 active:bg-zinc-700">
          ← Prev
        </button>
        <span className="max-w-[40%] truncate text-xs text-zinc-400">{episode?.title}</span>
        <button disabled={!hasNext}
                onClick={() => router.push(`/watch/${series.slug}/${episodeNumber + 1}`)}
                className="rounded-lg bg-zinc-800 px-4 py-2 text-sm disabled:opacity-40 active:bg-zinc-700">
          Next →
        </button>
      </div>
    </div>
  );
}
