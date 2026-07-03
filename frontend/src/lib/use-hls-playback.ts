"use client";

import Hls from "hls.js";
import { useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { PlaybackInfo } from "@/lib/types";

export type PlaybackState = "idle" | "loading" | "ready" | "locked" | "error";

/**
 * Fetches playback info for an episode and attaches the stream to `videoRef`
 * (hls.js for HLS, plain src for MP4; YouTube sources are surfaced via
 * `youtubeId` for the caller to render an iframe). Loads at most ONCE, the
 * first time `enabled` becomes true — callers decide when. Destroys the
 * hls.js instance on unmount. withCredentials is required for CloudFront
 * signed cookies in prod.
 */
export function useHlsPlayback(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  episodeId: string,
  enabled: boolean,
): { state: PlaybackState; youtubeId: string | null } {
  const hlsRef = useRef<Hls | null>(null);
  const loadedRef = useRef(false);
  const [state, setState] = useState<PlaybackState>("idle");
  const [youtubeId, setYoutubeId] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || loadedRef.current) return;
    loadedRef.current = true;
    setState("loading");
    let cancelled = false;
    apiFetch<PlaybackInfo>(`/api/v1/episodes/${episodeId}/playback`)
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
  }, [enabled, episodeId, videoRef]);

  useEffect(() => () => { hlsRef.current?.destroy(); }, []);

  return { state, youtubeId };
}
