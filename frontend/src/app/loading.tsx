export default function Loading() {
  return (
    <div className="animate-fade-in pb-4">
      <div className="skeleton h-[430px] w-full !rounded-none" />
      <div className="mt-6 px-4">
        <div className="skeleton h-5 w-32" />
        <div className="mt-3 flex gap-3 overflow-hidden">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="w-28 shrink-0">
              <div className="skeleton aspect-[9/16] w-full" />
              <div className="skeleton mt-2 h-3 w-20" />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-6 px-4">
        <div className="skeleton h-5 w-40" />
        <div className="mt-3 flex gap-3 overflow-hidden">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="w-28 shrink-0">
              <div className="skeleton aspect-[9/16] w-full" />
              <div className="skeleton mt-2 h-3 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
