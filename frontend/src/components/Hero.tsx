import HeroCarousel from "@/components/HeroCarousel";
import type { SeriesSummary } from "@/lib/types";

export default function Hero({ items }: { items: SeriesSummary[] }) {
  return (
    <HeroCarousel slides={items.map((s) => ({
      key: s.id,
      image: s.poster_url,
      title: s.title,
      kicker: "Featured",
      subtitle: s.synopsis,
      playHref: `/watch/${s.slug}/1`,
      detailHref: `/series/${s.slug}`,
    }))} />
  );
}
