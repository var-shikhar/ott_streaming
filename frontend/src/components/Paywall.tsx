import Link from "next/link";

export default function Paywall({ seriesSlug, poster, message, detailPath }: {
  seriesSlug: string; poster: string; message?: string; detailPath?: string;
}) {
  const next = detailPath ?? `/series/${seriesSlug}`;
  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={poster} alt="" className="absolute inset-0 h-full w-full object-cover opacity-20 blur-sm" />
      <div className="relative z-10 mx-6 text-center">
        <div className="text-5xl">🔒</div>
        <h2 className="mt-3 text-xl font-bold">Subscribe to keep watching</h2>
        <p className="mt-1 text-sm text-zinc-400">
          {message ?? "You've reached the end of the free episodes for this series."}
        </p>
        <div className="mt-5 flex flex-col gap-2">
          <Link href="/plans" className="rounded-lg bg-rose-600 px-6 py-2.5 font-semibold active:bg-rose-500">
            View Plans
          </Link>
          <Link href={`/login?next=${next}`} className="text-sm text-zinc-400 active:text-white">
            Already subscribed? Log in
          </Link>
        </div>
      </div>
    </div>
  );
}
