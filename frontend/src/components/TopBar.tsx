"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";
import type { User } from "@/lib/types";

export default function TopBar() {
  const [user, setUser] = useState<User | null>(null);
  const [loaded, setLoaded] = useState(false);
  const router = useRouter();

  useEffect(() => {
    apiFetch<User>("/api/v1/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoaded(true));
  }, []);

  async function logout() {
    await apiFetch("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    router.push("/");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800/60 bg-zinc-950/90 backdrop-blur">
      <div className="flex h-12 items-center justify-between px-4">
        <Link href="/" className="text-lg font-extrabold tracking-tight text-rose-500">
          ShortReel
        </Link>
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
