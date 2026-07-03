import FallbackImage from "@/components/FallbackImage";

export default function StillsGallery({ stills, fallback }: {
  stills: string[]; fallback: string;
}) {
  if (!stills.length) return null;
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-base font-bold">Stills</h2>
      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-none">
        {stills.map((url, i) => (
          <div key={i} className="w-56 shrink-0">
            <FallbackImage src={url} fallback={fallback} alt={`Still ${i + 1}`}
                           className="aspect-video w-full rounded-lg object-cover ring-1 ring-zinc-800" />
          </div>
        ))}
      </div>
    </section>
  );
}
