"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Paywall from "@/components/Paywall";
import { apiFetch } from "@/lib/api-client";
import { isLoggedIn } from "@/lib/session";
import { useHlsPlayback } from "@/lib/use-hls-playback";
import type { MovieDetail, MovieEpisode } from "@/lib/types";

function fmt(t: number): string {
  if (!Number.isFinite(t) || t < 0) return "0:00";
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60).toString().padStart(2, "0");
  return h > 0 ? `${h}:${m.toString().padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/**
 * Docked player: a 16:9 video block that sits at the top of the portrait
 * watch page (info scrolls beneath it). The maximize button fullscreens the
 * block and locks the device to landscape where supported.
 */
export default function MoviePlayer({ movie, episode }: {
  movie: MovieDetail; episode: MovieEpisode;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const lastSaved = useRef(0);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [paused, setPaused] = useState(true);
  const [muted, setMuted] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [rotated, setRotated] = useState(false); // CSS landscape fallback when orientation.lock is unsupported
  const [time, setTime] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [duration, setDuration] = useState(episode.duration_seconds);

  const { state, youtubeId } = useHlsPlayback(videoRef, episode.id, !episode.locked);

  const saveProgress = useCallback((position: number, completed: boolean) => {
    if (isLoggedIn() === false) return; // guests: don't fire doomed requests
    apiFetch(`/api/v1/progress/${episode.id}`, {
      method: "PUT",
      body: JSON.stringify({ position_seconds: Math.floor(position), completed }),
    }).catch(() => {}); // unknown auth state: fail silently
  }, [episode.id]);

  const poke = useCallback(() => {
    setControlsVisible(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    // only auto-hide while playing; a paused player keeps its controls
    if (videoRef.current && !videoRef.current.paused) {
      hideTimer.current = setTimeout(() => setControlsVisible(false), 3000);
    }
  }, []);

  useEffect(() => {
    poke();
    return () => { if (hideTimer.current) clearTimeout(hideTimer.current); };
  }, [poke]);

  // autoplay once the stream is ready; fall back to muted autoplay
  useEffect(() => {
    const video = videoRef.current;
    if (!video || state !== "ready" || youtubeId) return;
    video.play().catch(() => {
      video.muted = true;
      setMuted(true);
      video.play().catch(() => {});
    });
  }, [state, youtubeId]);

  // fullscreen must always read landscape: if the viewport is still portrait
  // once fullscreen (orientation.lock unsupported/refused), rotate the player
  // 90° with CSS; a real device rotation makes the viewport landscape and
  // removes the fake rotation automatically.
  useEffect(() => {
    const update = () => {
      const fs = Boolean(document.fullscreenElement);
      setFullscreen(fs);
      setRotated(fs && window.innerHeight > window.innerWidth);
    };
    document.addEventListener("fullscreenchange", update);
    window.addEventListener("resize", update);
    return () => {
      document.removeEventListener("fullscreenchange", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  // flush progress when the tab is hidden or the player unmounts
  useEffect(() => {
    const flush = () => {
      const video = videoRef.current;
      if (video && video.currentTime > 0) saveProgress(video.currentTime, false);
    };
    document.addEventListener("visibilitychange", flush);
    return () => { flush(); document.removeEventListener("visibilitychange", flush); };
  }, [saveProgress]);

  function togglePlay() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => {});
    } else {
      video.pause();
      saveProgress(video.currentTime, false);
    }
    poke();
  }

  function skip(delta: number) {
    const video = videoRef.current;
    if (!video) return;
    const max = Number.isFinite(video.duration) ? video.duration : duration;
    video.currentTime = Math.min(Math.max(0, video.currentTime + delta), max);
    poke();
  }

  function toggleMute() {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setMuted(video.muted);
    poke();
  }

  async function toggleFullscreen() {
    const shell = shellRef.current;
    const video = videoRef.current as (HTMLVideoElement & {
      webkitEnterFullscreen?: () => void;
    }) | null;
    if (!shell || !video) return;
    poke();
    if (document.fullscreenElement) {
      await document.exitFullscreen().catch(() => {});
      try {
        (screen.orientation as unknown as { unlock?: () => void }).unlock?.();
      } catch { /* unsupported */ }
      return;
    }
    if (shell.requestFullscreen) {
      await shell.requestFullscreen().catch(() => {});
      try {
        // rotate to landscape — unsupported on iOS Safari and most desktops
        await (screen.orientation as unknown as {
          lock?: (o: string) => Promise<void>;
        }).lock?.("landscape");
      } catch { /* unsupported */ }
    } else {
      video.webkitEnterFullscreen?.(); // iOS Safari: native video fullscreen
    }
  }

  function onTimeUpdate() {
    const video = videoRef.current;
    if (!video) return;
    setTime(video.currentTime);
    if (video.buffered.length > 0) {
      setBuffered(video.buffered.end(video.buffered.length - 1));
    }
    if (video.currentTime - lastSaved.current >= 5) {
      lastSaved.current = video.currentTime;
      saveProgress(video.currentTime, false);
    }
  }

  function onSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Number(e.target.value);
    setTime(video.currentTime);
    poke();
  }

  if (episode.locked || state === "locked") {
    return (
      <div className="sticky top-0 z-30 aspect-video w-full bg-black">
        <Paywall seriesSlug={movie.slug} poster={movie.banner_url}
                 message="This film is for subscribers. Subscribe to start watching."
                 detailPath={`/movies/${movie.slug}`} />
      </div>
    );
  }

  // YouTube-sourced film: the embed brings its own controls (incl. fullscreen)
  if (youtubeId) {
    return (
      <div className="sticky top-0 z-30 aspect-video w-full bg-black">
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1&playsinline=1`}
          title={movie.title} allow="autoplay; encrypted-media; fullscreen"
          allowFullScreen className="h-full w-full" />
      </div>
    );
  }

  return (
    <div ref={shellRef} onClick={poke}
         onPointerMove={(e) => { if (e.pointerType === "mouse") poke(); }}
         onPointerLeave={(e) => {
           if (e.pointerType === "mouse" && videoRef.current && !videoRef.current.paused) {
             setControlsVisible(false);
           }
         }}
         className={`sticky top-0 z-30 w-full overflow-hidden bg-black ${
           fullscreen ? "h-full" : "aspect-video"}`}>
     <div className={rotated ? "absolute left-1/2 top-1/2" : "relative h-full w-full"}
          style={rotated
            ? { width: "100dvh", height: "100dvw",
                transform: "translate(-50%, -50%) rotate(90deg)" }
            : undefined}>
      <video ref={videoRef} playsInline
             poster={episode.thumbnail_url || movie.banner_url}
             onClick={(e) => {
               e.stopPropagation();
               // touch: first tap only reveals controls; play/pause needs a
               // second tap (desktop hover has already revealed them)
               if (controlsVisible) togglePlay();
               else poke();
             }}
             onTimeUpdate={onTimeUpdate}
             onLoadedMetadata={() => {
               const d = videoRef.current?.duration;
               if (d && Number.isFinite(d)) setDuration(d);
             }}
             onPlay={() => { setPaused(false); poke(); }}
             onPause={() => { setPaused(true); poke(); }}
             onEnded={() => {
               saveProgress(videoRef.current?.duration ?? duration, true);
               setControlsVisible(true);
               if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
             }}
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

      <div onClick={(e) => { e.stopPropagation(); togglePlay(); }}
           className={`absolute inset-0 flex flex-col justify-between bg-gradient-to-b from-black/70 via-transparent to-black/80 transition-opacity duration-200 ${
        controlsVisible ? "opacity-100" : "pointer-events-none opacity-0"}`}>
        <div className="flex items-center gap-2 p-3">
          <Link href={`/movies/${movie.slug}`} aria-label="Back"
                onClick={(e) => e.stopPropagation()}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-black/50 text-base">
            ←
          </Link>
          {fullscreen && (
            <p className="line-clamp-1 text-sm font-bold drop-shadow">{movie.title}</p>
          )}
        </div>

        <div className="flex items-center justify-center gap-8">
          <button onClick={(e) => { e.stopPropagation(); skip(-10); }}
                  aria-label="Back 10 seconds"
                  className="text-xs font-semibold text-zinc-200">⟲ 10</button>
          <button onClick={(e) => { e.stopPropagation(); togglePlay(); }}
                  aria-label={paused ? "Play" : "Pause"}
                  className="flex h-12 w-12 items-center justify-center rounded-full bg-black/50 text-xl backdrop-blur-sm">
            {paused ? "▶" : "⏸"}
          </button>
          <button onClick={(e) => { e.stopPropagation(); skip(10); }}
                  aria-label="Forward 10 seconds"
                  className="text-xs font-semibold text-zinc-200">10 ⟳</button>
        </div>

        <div className="px-3 pb-2.5">
          <div className="mb-1 h-0.5 w-full overflow-hidden rounded bg-zinc-800">
            <div className="h-full bg-zinc-500/70"
                 style={{ width: `${duration ? Math.min(100, (buffered / duration) * 100) : 0}%` }} />
          </div>
          <input type="range" min={0} max={Math.max(1, Math.floor(duration))} step={1}
                 value={Math.min(time, duration)} onChange={onSeek} aria-label="Seek"
                 onClick={(e) => e.stopPropagation()}
                 className="w-full accent-rose-600" />
          <div className="flex items-center justify-between text-xs text-zinc-300">
            <span>{fmt(time)} / {fmt(duration)}</span>
            <div className="flex items-center gap-4">
              <button onClick={(e) => { e.stopPropagation(); toggleMute(); }}
                      aria-label={muted ? "Unmute" : "Mute"}>{muted ? "🔇" : "🔊"}</button>
              <button onClick={(e) => { e.stopPropagation(); toggleFullscreen(); }}
                      aria-label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
                      className="text-base">{fullscreen ? "⤡" : "⛶"}</button>
            </div>
          </div>
        </div>
      </div>
     </div>
    </div>
  );
}
