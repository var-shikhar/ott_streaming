"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import EpisodeSlide from "@/components/EpisodeSlide";
import type { SeriesDetail } from "@/lib/types";

export default function SwipeFeed({ series, initialEp }: {
  series: SeriesDetail; initialEp: number;
}) {
  const episodes = series.episodes;
  const initialIdx = Math.max(0, episodes.findIndex((e) => e.episode_number === initialEp));
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeIdx, setActiveIdx] = useState(initialIdx);
  const [muted, setMuted] = useState(false);

  // jump to the requested episode once layout has settled
  useEffect(() => {
    const el = containerRef.current;
    if (!el || initialIdx === 0) return;
    const raf = requestAnimationFrame(() => {
      el.querySelector(`[data-idx="${initialIdx}"]`)?.scrollIntoView({ behavior: "instant", block: "start" });
    });
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // track which slide is in view
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const idx = Number((entry.target as HTMLElement).dataset.idx);
            setActiveIdx(idx);
            const ep = episodes[idx];
            window.history.replaceState(null, "", `/watch/${series.slug}/${ep.episode_number}`);
          }
        }
      },
      { root: el, threshold: 0.6 });
    el.querySelectorAll("[data-idx]").forEach((slide) => observer.observe(slide));
    return () => observer.disconnect();
  }, [episodes, series.slug]);

  const scrollToNext = useCallback((fromIdx: number) => {
    const el = containerRef.current;
    if (!el || fromIdx + 1 >= episodes.length) return;
    el.scrollTo({ top: (fromIdx + 1) * el.clientHeight, behavior: "smooth" });
  }, [episodes.length]);

  return (
    <div className="relative h-[calc(100dvh-3rem)] bg-black">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 bg-gradient-to-b from-black/70 to-transparent px-3 py-2">
        <Link href={`/series/${series.slug}`}
              className="pointer-events-auto text-sm text-zinc-200 drop-shadow active:text-white">
          ← {series.title}
        </Link>
      </div>
      <div ref={containerRef}
           className="h-full snap-y snap-mandatory overflow-y-scroll scrollbar-none">
        {episodes.map((ep, idx) => (
          <div key={ep.id} data-idx={idx} className="relative h-full w-full snap-start">
            <EpisodeSlide
              episode={ep}
              series={series}
              active={idx === activeIdx}
              muted={muted}
              onToggleMute={() => setMuted((m) => !m)}
              onEnded={() => scrollToNext(idx)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
