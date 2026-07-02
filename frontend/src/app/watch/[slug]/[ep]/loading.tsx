export default function Loading() {
  return (
    <div className="flex h-[calc(100dvh-3rem)] items-center justify-center bg-black">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-700 border-t-rose-500" />
    </div>
  );
}
