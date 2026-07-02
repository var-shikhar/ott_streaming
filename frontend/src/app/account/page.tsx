import Link from "next/link";
import { redirect } from "next/navigation";
import CancelSubscription from "@/components/CancelSubscription";
import { serverFetch } from "@/lib/api-server";
import type { ContinueItem, CurrentSubscription, User } from "@/lib/types";

export default async function AccountPage() {
  const user = await serverFetch<User>("/api/v1/auth/me");
  if (!user) redirect("/login?next=/account");
  const sub = await serverFetch<CurrentSubscription | null>("/api/v1/subscriptions/current");
  const history = (await serverFetch<ContinueItem[]>("/api/v1/progress/continue-watching")) ?? [];

  return (
    <div className="px-4 py-6">
      <h1 className="text-xl font-bold">Account</h1>
      <div className="mt-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <p className="text-sm font-medium">{user.name}</p>
        <p className="text-xs text-zinc-400">{user.email}</p>
      </div>

      <h2 className="mt-6 text-base font-bold">Subscription</h2>
      <div className="mt-2 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        {sub ? (
          <>
            <p className="text-sm font-medium">
              {sub.plan.name} — ₹{(sub.plan.price_inr / 100).toFixed(0)}/{sub.plan.interval.replace("ly", "")}
            </p>
            <p className="mt-1 text-xs text-zinc-400">
              Status: {sub.status}
              {sub.current_period_end &&
                ` · renews/ends ${new Date(sub.current_period_end).toLocaleDateString()}`}
            </p>
            {sub.status === "active" && <CancelSubscription />}
          </>
        ) : (
          <p className="text-sm text-zinc-400">
            No active subscription.{" "}
            <Link href="/plans" className="text-rose-400">See plans</Link>
          </p>
        )}
      </div>

      <h2 className="mt-6 text-base font-bold">Watch history</h2>
      {history.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-400">Nothing yet — go watch something!</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {history.map((h) => (
            <li key={h.episode_id}>
              <Link href={`/watch/${h.series.slug}/${h.episode_number}`}
                    className="text-sm text-zinc-300 active:text-white">
                {h.series.title} — Ep {h.episode_number} ({h.position_seconds}s in)
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
