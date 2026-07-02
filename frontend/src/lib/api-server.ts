import { cookies } from "next/headers";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function serverFetch<T>(path: string): Promise<T | null> {
  const cookieHeader = (await cookies()).toString();
  try {
    const res = await fetch(`${API}${path}`, {
      headers: cookieHeader ? { cookie: cookieHeader } : {},
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
