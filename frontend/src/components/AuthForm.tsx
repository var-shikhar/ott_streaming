"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = mode === "signup" ? { email, password, name } : { email, password };
      await apiFetch(`/api/v1/auth/${mode}`, { method: "POST", body: JSON.stringify(body) });
      // full reload so the navbar picks up the session cookie
      window.location.href = params.get("next") ?? "/";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
      setBusy(false);
    }
  }

  const input = "w-full rounded bg-zinc-900 border border-zinc-700 px-3 py-2 outline-none focus:border-rose-500";
  return (
    <div className="mx-auto mt-16 max-w-sm px-4">
      <h1 className="mb-6 text-2xl font-bold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <form onSubmit={submit} className="space-y-4">
        {mode === "signup" && (
          <input className={input} placeholder="Name" value={name}
                 onChange={(e) => setName(e.target.value)} required />
        )}
        <input className={input} type="email" placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <input className={input} type="password" placeholder="Password (min 8 chars)" value={password}
               onChange={(e) => setPassword(e.target.value)} minLength={8} required />
        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button disabled={busy}
                className="w-full rounded bg-rose-600 py-2 font-semibold hover:bg-rose-500 disabled:opacity-50">
          {busy ? "..." : mode === "login" ? "Log in" : "Sign up"}
        </button>
      </form>
      <p className="mt-4 text-sm text-zinc-400">
        {mode === "login" ? (
          <>New here? <Link className="text-rose-400" href="/signup">Create an account</Link></>
        ) : (
          <>Already have an account? <Link className="text-rose-400" href="/login">Log in</Link></>
        )}
      </p>
    </div>
  );
}
