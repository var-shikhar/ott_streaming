"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  {
    href: "/", label: "Home",
    icon: "M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-10.5Z",
  },
  {
    href: "/search", label: "Search",
    icon: "M10 4a6 6 0 1 0 3.87 10.6l4.26 4.27 1.42-1.42-4.27-4.26A6 6 0 0 0 10 4Zm-4 6a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z",
  },
  {
    href: "/my-list", label: "My List",
    icon: "M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z",
  },
  {
    href: "/account", label: "Profile",
    icon: "M12 3a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Zm0 11c4.42 0 8 2.24 8 5v2H4v-2c0-2.76 3.58-5 8-5Z",
  },
];

export default function BottomNav() {
  const pathname = usePathname();
  if (pathname.startsWith("/watch/")) return null; // fullscreen player
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-md border-t border-zinc-800/60 bg-zinc-950/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
      <div className="grid grid-cols-4">
        {TABS.map((tab) => {
          const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
          return (
            <Link key={tab.href} href={tab.href}
                  className={`flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium ${
                    active ? "text-rose-500" : "text-zinc-500 active:text-zinc-300"}`}>
              <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden>
                <path d={tab.icon} />
              </svg>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
