export default function Loading() {
  return (
    <div className="pb-4">
      <div className="skeleton aspect-video w-full rounded-none" />
      <div className="mt-6 px-4">
        <div className="skeleton h-5 w-32" />
        <div className="mt-3 flex gap-3 overflow-hidden">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-40 shrink-0">
              <div className="skeleton aspect-video w-full" />
              <div className="skeleton mt-2 h-3 w-24" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
