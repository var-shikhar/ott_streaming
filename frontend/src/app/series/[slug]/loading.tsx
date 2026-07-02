export default function Loading() {
  return (
    <div className="animate-fade-in pb-4">
      <div className="skeleton h-52 w-full !rounded-none" />
      <div className="px-4">
        <div className="skeleton mt-4 h-7 w-3/4" />
        <div className="skeleton mt-2 h-3 w-1/2" />
        <div className="skeleton mt-3 h-3 w-full" />
        <div className="skeleton mt-1.5 h-3 w-5/6" />
        <div className="mt-4 flex gap-2">
          <div className="skeleton h-10 flex-1" />
          <div className="skeleton h-10 flex-1" />
        </div>
        <div className="skeleton mb-2 mt-6 h-5 w-24" />
        <div className="grid grid-cols-3 gap-2.5">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton aspect-[9/16] w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
