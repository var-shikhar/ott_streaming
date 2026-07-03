import HeroCarousel from "@/components/HeroCarousel";
import type { SeriesSummary } from "@/lib/types";

export default function MovieHero({ items }: { items: SeriesSummary[] }) {
  return (
    <HeroCarousel slides={items.map((m) => ({
      key: m.id,
      image: m.banner_url || m.poster_url,
      title: m.title,
      kicker: "Featured Film",
      subtitle: m.synopsis,
      playHref: `/movies/${m.slug}/watch`,
      detailHref: `/movies/${m.slug}`,
    }))} />
  );
}
