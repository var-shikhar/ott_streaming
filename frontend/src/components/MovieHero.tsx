"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { SeriesSummary } from "@/lib/types";

export default function MovieHero({ items }: { items: SeriesSummary[] }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (items.length < 2) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % items.length), 5000);
    return () => clearInterval(t);
  }, [items.length]);
  if (!items.length) return null;
  const m = items[index % items.length];
  return (
    <div className="relative w-full overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img key={m.id} src={m.banner_url} alt={m.title}
           className="aspect-video w-full object-cover animate-fade-in" />
      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/20 to-transparent" />
      <div className="absolute inset-x-0 bottom-3 px-4">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-rose-400">
          Featured Film
        </p>
        <h1 className="mt-1 text-2xl font-extrabold leading-tight">{m.title}</h1>
        <div className="mt-2 flex gap-2">
          <Link href={`/movies/${m.slug}/watch`}
                className="flex-1 rounded-lg bg-rose-600 py-2.5 text-center text-sm font-semibold active:bg-rose-500">
            ▶ Play
          </Link>
          <Link href={`/movies/${m.slug}`}
                className="flex-1 rounded-lg bg-zinc-800/90 py-2.5 text-center text-sm font-semibold active:bg-zinc-700">
            Details
          </Link>
        </div>
        {items.length > 1 && (
          <div className="mt-2.5 flex justify-center gap-1.5">
            {items.map((item, i) => (
              <button key={item.id} onClick={() => setIndex(i)} aria-label={`Show ${item.title}`}
                      className={`h-1 rounded-full transition-all ${
                        i === index ? "w-6 bg-rose-500" : "w-3 bg-zinc-600"}`} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
