import SeriesCard from "@/components/SeriesCard";
import type { SeriesSummary } from "@/lib/types";

export default function Rail({ title, series }: { title: string; series: SeriesSummary[] }) {
  if (!series.length) return null;
  return (
    <section className="mt-6">
      <h2 className="mb-2 px-4 text-base font-bold">{title}</h2>
      <div className="flex gap-3 overflow-x-auto px-4 pb-2">
        {series.map((s) => <SeriesCard key={s.id} series={s} />)}
      </div>
    </section>
  );
}
