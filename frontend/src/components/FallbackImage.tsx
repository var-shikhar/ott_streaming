"use client";

import { useState } from "react";

/** <img> that swaps to a fallback source if the primary fails to load. */
export default function FallbackImage({ src, fallback, alt, className }: {
  src: string; fallback: string; alt: string; className?: string;
}) {
  const [failed, setFailed] = useState(false);
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={failed || !src ? fallback : src} alt={alt} className={className}
              loading="lazy" onError={() => setFailed(true)} />;
}
