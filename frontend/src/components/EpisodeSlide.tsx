"use client";

import Hls from "hls.js";
import { useCallback, useEffect, useRef, useState } from "react";
import ActionRail from "@/components/ActionRail";
import CommentsSheet from "@/components/CommentsSheet";
import Paywall from "@/components/Paywall";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { EpisodeSummary, PlaybackInfo, SeriesDetail } from "@/lib/types";

export default function EpisodeSlide({ episode, series, active, muted, onToggleMute, onEnded }: {
  episode: EpisodeSummary;
  series: SeriesDetail;
  active: boolean;
  muted: boolean;
  onToggleMute: () => void;
  onEnded: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const loadedRef = useRef(false);
  const lastSaved = useRef(0);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "locked" | "error">("idle");
  const [youtubeId, setYoutubeId] = useState("");
  const [paused, setPaused] = useState(false);
  const [autoMuted, setAutoMuted] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);

  const saveProgress = useCallback((position: number, completed: boolean) => {
    apiFetch(`/api/v1/progress/${episode.id}`, {
      method: "PUT",
      body: JSON.stringify({ position_seconds: Math.floor(position), completed }),
    }).catch(() => {}); // guests get a 401 — progress just isn't saved
  }, [episode.id]);

  // load the stream only when the slide is actually active — neighbors just
  // show their poster, so at most one video decodes at a time
  useEffect(() => {
    if (!active || loadedRef.current || episode.locked) {
      if (episode.locked) setState("locked");
      return;
    }
    loadedRef.current = true;
    setState("loading");
    let cancelled = false;
    apiFetch<PlaybackInfo>(`/api/v1/episodes/${episode.id}/playback`)
      .then((playback) => {
        if (cancelled) return;
        if (playback.type === "youtube" && playback.youtube_id) {
          setYoutubeId(playback.youtube_id);
          setState("ready");
          return;
        }
        const video = videoRef.current;
        if (!video) return;
        if (playback.type === "mp4") {
          video.src = playback.url;
        } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = playback.url;
        } else if (Hls.isSupported()) {
          const hls = new Hls({
            capLevelToPlayerSize: true,
            xhrSetup: (xhr) => { xhr.withCredentials = true; },
          });
          hlsRef.current = hls;
          hls.loadSource(playback.url);
          hls.attachMedia(video);
          hls.on(Hls.Events.ERROR, (_evt, data) => {
            if (data.fatal) setState("error");
          });
        } else {
          setState("error");
          return;
        }
        if (playback.resume_position > 0) {
          video.addEventListener("loadedmetadata", () => {
            if (playback.resume_position < video.duration - 2) {
              video.currentTime = playback.resume_position;
            }
          }, { once: true });
        }
        setState("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.code === "subscription_required") setState("locked");
        else setState("error");
      });
    return () => { cancelled = true; };
  }, [active, episode.id, episode.locked]);

  // play/pause with visibility; handle autoplay-with-sound rejection
  useEffect(() => {
    if (youtubeId) return; // YouTube iframe mounts/unmounts with `active` instead
    const video = videoRef.current;
    if (!video || state !== "ready") return;
    if (active) {
      video.muted = muted;
      video.play().then(() => setAutoMuted(false)).catch(() => {
        video.muted = true;
        setAutoMuted(true);
        video.play().catch(() => {});
      });
      setPaused(false);
    } else {
      video.pause();
      if (video.currentTime > 0) saveProgress(video.currentTime, false);
    }
  }, [active, state, muted, saveProgress]);

  // teardown
  useEffect(() => () => { hlsRef.current?.destroy(); }, []);

  function togglePlay() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => {});
      setPaused(false);
    } else {
      video.pause();
      setPaused(true);
      saveProgress(video.currentTime, false);
    }
  }

  function unmute() {
    const video = videoRef.current;
    if (video) video.muted = false;
    setAutoMuted(false);
    if (muted) onToggleMute();
  }

  function onTimeUpdate() {
    const video = videoRef.current;
    if (!video) return;
    if (video.currentTime - lastSaved.current >= 5) {
      lastSaved.current = video.currentTime;
      saveProgress(video.currentTime, false);
    }
  }

  if (episode.locked || state === "locked") {
    return <Paywall seriesSlug={series.slug} poster={series.poster_url} />;
  }

  if (youtubeId) {
    return (
      <div className="relative h-full w-full bg-black">
        {active ? (
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1&playsinline=1&rel=0`}
            title={episode.title}
            allow="autoplay; encrypted-media; picture-in-picture"
            allowFullScreen
            className="h-full w-full"
          />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={episode.thumbnail_url || series.poster_url} alt={episode.title}
               className="h-full w-full object-contain" />
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/80 via-black/30 to-transparent px-4 pb-5 pt-16">
          <p className="text-sm font-bold drop-shadow">{series.title}</p>
          <p className="mt-0.5 text-xs text-zinc-300 drop-shadow">
            Ep {episode.episode_number} · {episode.title}
          </p>
        </div>
        <ActionRail episode={episode} seriesTitle={series.title}
                    onOpenComments={() => setCommentsOpen(true)} />
        <CommentsSheet episodeId={episode.id} open={commentsOpen}
                       onClose={() => setCommentsOpen(false)} />
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <video ref={videoRef} playsInline loop={false}
             poster={episode.thumbnail_url || series.poster_url}
             onClick={togglePlay}
             onTimeUpdate={onTimeUpdate}
             onEnded={() => { saveProgress(videoRef.current?.duration ?? 0, true); onEnded(); }}
             className="h-full w-full object-contain" />

      {state === "loading" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-600 border-t-rose-500" />
        </div>
      )}
      {state === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-zinc-400">
          Playback failed.
          <button className="underline" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}
      {paused && state === "ready" && (
        <button onClick={togglePlay} aria-label="Play"
                className="absolute inset-0 z-10 flex items-center justify-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-black/50 text-3xl backdrop-blur-sm animate-fade-in">
            ▶
          </span>
        </button>
      )}
      {autoMuted && state === "ready" && (
        <button onClick={unmute}
                className="absolute left-3 top-12 z-20 rounded-full bg-black/60 px-3 py-1.5 text-xs font-semibold backdrop-blur animate-fade-in">
          🔇 Tap for sound
        </button>
      )}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/80 via-black/30 to-transparent px-4 pb-5 pt-16">
        <p className="text-sm font-bold drop-shadow">{series.title}</p>
        <p className="mt-0.5 text-xs text-zinc-300 drop-shadow">
          Ep {episode.episode_number} · {episode.title}
        </p>
      </div>

      <ActionRail episode={episode} seriesTitle={series.title}
                  onOpenComments={() => setCommentsOpen(true)} />
      <CommentsSheet episodeId={episode.id} open={commentsOpen}
                     onClose={() => setCommentsOpen(false)} />
    </div>
  );
}
