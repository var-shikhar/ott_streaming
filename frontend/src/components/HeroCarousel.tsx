"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

export interface HeroSlide {
  key: string;
  image: string;
  title: string;
  kicker: string;
  subtitle?: string;
  playHref: string;
  detailHref: string;
}

/** Shared home-page hero: swipeable snap carousel with auto-advance and dots. */
export default function HeroCarousel({ slides }: { slides: HeroSlide[] }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const interacting = useRef(false); // pause auto-advance while the user swipes
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (slides.length < 2) return;
    const t = setInterval(() => {
      const track = trackRef.current;
      if (!track || interacting.current) return;
      const next = (Math.round(track.scrollLeft / track.clientWidth) + 1) % slides.length;
      track.scrollTo({ left: next * track.clientWidth, behavior: "smooth" });
    }, 5000);
    return () => clearInterval(t);
  }, [slides.length]);

  useEffect(() => () => {
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
  }, []);

  function pauseAuto() {
    interacting.current = true;
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
    resumeTimer.current = setTimeout(() => { interacting.current = false; }, 6000);
  }

  function onScroll() {
    const track = trackRef.current;
    if (!track) return;
    setIndex(Math.max(0, Math.min(slides.length - 1,
      Math.round(track.scrollLeft / track.clientWidth))));
  }

  function goTo(i: number) {
    pauseAuto();
    const track = trackRef.current;
    track?.scrollTo({ left: i * track.clientWidth, behavior: "smooth" });
  }

  if (!slides.length) return null;

  return (
    <div className="relative h-[430px] w-full overflow-hidden">
      <div ref={trackRef} onScroll={onScroll} onTouchStart={pauseAuto} onPointerDown={pauseAuto}
           className="flex h-full w-full snap-x snap-mandatory overflow-x-auto scrollbar-none">
        {slides.map((s) => (
          <div key={s.key} className="relative h-full w-full shrink-0 snap-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={s.image} alt={s.title} draggable={false}
                 className="h-full w-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/30 to-zinc-950/10" />
            <div className="absolute inset-x-0 bottom-9 px-4">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-rose-400">
                {s.kicker}
              </p>
              <h1 className="mt-1 text-2xl font-extrabold leading-tight">{s.title}</h1>
              {s.subtitle && (
                <p className="mt-1 line-clamp-2 text-xs text-zinc-300">{s.subtitle}</p>
              )}
              <div className="mt-3 flex gap-2">
                <Link href={s.playHref}
                      className="flex-1 rounded-lg bg-rose-600 py-2.5 text-center text-sm font-semibold active:bg-rose-500">
                  ▶ Play
                </Link>
                <Link href={s.detailHref}
                      className="flex-1 rounded-lg bg-zinc-800/90 py-2.5 text-center text-sm font-semibold active:bg-zinc-700">
                  Details
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
      {slides.length > 1 && (
        <div className="absolute inset-x-0 bottom-3.5 flex justify-center gap-1.5">
          {slides.map((s, i) => (
            <button key={s.key} onClick={() => goTo(i)} aria-label={`Show ${s.title}`}
                    className={`h-1 rounded-full transition-all ${
                      i === index ? "w-6 bg-rose-500" : "w-3 bg-zinc-600"}`} />
          ))}
        </div>
      )}
    </div>
  );
}
