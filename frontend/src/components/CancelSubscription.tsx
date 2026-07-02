"use client";

import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

export default function CancelSubscription() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function cancel() {
    if (!confirm("Cancel your subscription? You keep access until the period ends.")) return;
    setBusy(true);
    try {
      const res = await apiFetch<{ message: string }>("/api/v1/subscriptions/cancel", { method: "POST" });
      setMessage(res.message);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Could not cancel");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3">
      <button onClick={cancel} disabled={busy}
              className="rounded-lg bg-zinc-800 px-4 py-2 text-xs active:bg-zinc-700 disabled:opacity-50">
        Cancel subscription
      </button>
      {message && <p className="mt-2 text-xs text-zinc-400">{message}</p>}
    </div>
  );
}
