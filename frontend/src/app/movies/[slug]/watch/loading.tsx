export default function Loading() {
  return (
    <div className="min-h-dvh bg-black">
      <div className="skeleton aspect-video w-full rounded-none" />
      <div className="px-4">
        <div className="skeleton mt-4 h-6 w-2/3" />
        <div className="skeleton mt-2 h-3 w-1/2" />
        <div className="skeleton mt-3 h-14 w-full" />
      </div>
    </div>
  );
}
