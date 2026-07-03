"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";
import { setLoggedIn } from "@/lib/session";
import type { User } from "@/lib/types";

export default function TopBar() {
  const [user, setUser] = useState<User | null>(null);
  const [loaded, setLoaded] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const inMovies = pathname === "/movies" || pathname.startsWith("/movies/");

  useEffect(() => {
    apiFetch<User>("/api/v1/auth/me")
      .then((u) => { setUser(u); setLoggedIn(true); })
      .catch(() => { setUser(null); setLoggedIn(false); })
      .finally(() => setLoaded(true));
  }, []);

  async function logout() {
    await apiFetch("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    setLoggedIn(false);
    router.push("/");
    router.refresh();
  }

  if (/^\/movies\/[^/]+\/watch$/.test(pathname)) return null; // immersive movie player

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800/60 bg-zinc-950/90 backdrop-blur">
      <div className="flex h-12 items-center justify-between gap-2 px-4">
        <Link href="/" className="text-lg font-extrabold tracking-tight text-rose-500">
          Qisso
        </Link>
        <nav aria-label="Mode"
             className="flex rounded-full border border-zinc-800 bg-zinc-900 p-0.5 text-xs font-semibold">
          <Link href="/" className={`rounded-full px-3 py-1 ${
            !inMovies ? "bg-rose-600 text-white" : "text-zinc-400 active:text-white"}`}>
            Reels
          </Link>
          <Link href="/movies" className={`rounded-full px-3 py-1 ${
            inMovies ? "bg-rose-600 text-white" : "text-zinc-400 active:text-white"}`}>
            Movies
          </Link>
        </nav>
        {!loaded ? null : user ? (
          <button onClick={logout} className="text-xs text-zinc-400 active:text-white">
            Log out
          </button>
        ) : (
          <Link href="/login"
                className="rounded-full bg-rose-600 px-3 py-1 text-xs font-semibold active:bg-rose-500">
            Log in
          </Link>
        )}
      </div>
    </header>
  );
}
