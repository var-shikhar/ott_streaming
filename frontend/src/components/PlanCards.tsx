"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { CurrentSubscription, Plan } from "@/lib/types";

declare global {
  interface Window { Razorpay?: new (options: Record<string, unknown>) => { open: () => void } }
}

function loadRazorpay(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

export default function PlanCards({ plans }: { plans: Plan[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function pollActivation(tries = 10): Promise<boolean> {
    for (let i = 0; i < tries; i++) {
      const sub = await apiFetch<CurrentSubscription | null>("/api/v1/subscriptions/current")
        .catch(() => null);
      if (sub) return true;
      await new Promise((r) => setTimeout(r, 2000));
    }
    return false;
  }

  async function subscribe(planId: number) {
    setBusy(planId);
    setError("");
    try {
      const res = await apiFetch<{ razorpay_subscription_id: string; razorpay_key_id: string }>(
        "/api/v1/subscriptions", { method: "POST", body: JSON.stringify({ plan_id: planId }) });
      if (!(await loadRazorpay()) || !window.Razorpay) {
        setError("Could not load the payment window. Check your connection.");
        return;
      }
      new window.Razorpay({
        key: res.razorpay_key_id,
        subscription_id: res.razorpay_subscription_id,
        name: "Qisso",
        description: "Unlimited dramas & films",
        theme: { color: "#e11d48" },
        handler: async () => {
          await pollActivation();
          window.location.href = "/account";
        },
      }).open();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login?next=/plans");
      } else if (err instanceof ApiError && err.code === "already_subscribed") {
        setError("You already have an active subscription.");
      } else {
        setError(err instanceof ApiError ? err.message : "Could not start checkout");
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      {plans.map((p) => (
        <div key={p.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <div className="flex items-baseline justify-between">
            <h3 className="text-base font-bold">{p.name}</h3>
            <p className="text-2xl font-extrabold">
              ₹{(p.price_inr / 100).toFixed(0)}
              <span className="text-xs font-normal text-zinc-400"> / {p.interval.replace("ly", "")}</span>
            </p>
          </div>
          <ul className="mt-3 space-y-1 text-xs text-zinc-400">
            <li>✓ Every series &amp; every film</li>
            <li>✓ New releases daily</li>
            <li>✓ Cancel anytime</li>
          </ul>
          <button onClick={() => subscribe(p.id)} disabled={busy !== null}
                  className="mt-4 w-full rounded-lg bg-rose-600 py-2.5 text-sm font-semibold active:bg-rose-500 disabled:opacity-50">
            {busy === p.id ? "Opening checkout..." : "Subscribe"}
          </button>
        </div>
      ))}
      {error && <p className="text-sm text-rose-400">{error}</p>}
    </div>
  );
}
