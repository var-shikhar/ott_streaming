import type { Credit } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = {
  director: "Director", writer: "Writer", producer: "Producer",
};

export default function CastList({ credits }: { credits: Credit[] }) {
  if (!credits.length) return null;
  const crew = credits.filter((c) => c.role !== "cast");
  const cast = credits.filter((c) => c.role === "cast");
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-base font-bold">Cast &amp; Crew</h2>
      <ul className="space-y-1.5">
        {crew.map((c, i) => (
          <li key={`crew-${i}`} className="flex items-baseline justify-between text-sm">
            <span className="font-medium">{c.person_name}</span>
            <span className="text-xs text-zinc-500">{ROLE_LABEL[c.role] ?? c.role}</span>
          </li>
        ))}
        {cast.map((c, i) => (
          <li key={`cast-${i}`} className="flex items-baseline justify-between text-sm">
            <span className="font-medium">{c.person_name}</span>
            <span className="text-xs text-zinc-500">
              {c.character_name ? `as ${c.character_name}` : "Cast"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
