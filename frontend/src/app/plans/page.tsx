import PlanCards from "@/components/PlanCards";
import { serverFetch } from "@/lib/api-server";
import type { Plan } from "@/lib/types";

export default async function PlansPage() {
  const plans = (await serverFetch<Plan[]>("/api/v1/plans")) ?? [];
  return (
    <div className="px-4 py-8">
      <h1 className="text-2xl font-extrabold leading-tight">Watch everything. One plan.</h1>
      <p className="mt-2 text-sm text-zinc-400">
        First episodes of every series are free. Subscribe to unlock everything —
        all episodes and every film.
      </p>
      <div className="mt-6">
        <PlanCards plans={plans} />
      </div>
    </div>
  );
}
