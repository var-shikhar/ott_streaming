"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { CommentOut } from "@/lib/types";

function timeAgo(iso: string): string {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

export default function CommentsSheet({ episodeId, open, onClose }: {
  episodeId: string; open: boolean; onClose: () => void;
}) {
  const [comments, setComments] = useState<CommentOut[] | null>(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(false);

  useEffect(() => {
    if (!open) return;
    setComments(null);
    apiFetch<CommentOut[]>(`/api/v1/episodes/${episodeId}/comments`)
      .then(setComments)
      .catch(() => setComments([]));
  }, [open, episodeId]);

  async function post(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    try {
      const c = await apiFetch<CommentOut>(`/api/v1/episodes/${episodeId}/comments`, {
        method: "POST", body: JSON.stringify({ body: body.trim() }),
      });
      setComments((prev) => [c, ...(prev ?? [])]);
      setBody("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setNeedsLogin(true);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await apiFetch(`/api/v1/comments/${id}`, { method: "DELETE" }).catch(() => {});
    setComments((prev) => (prev ?? []).filter((c) => c.id !== id));
  }

  return (
    <div className={`absolute inset-0 z-30 overflow-hidden ${open ? "" : "pointer-events-none invisible"}`}
         style={{ transitionProperty: "visibility", transitionDuration: "300ms" }}>
      <div onClick={onClose}
           className={`absolute inset-0 bg-black/50 transition-opacity duration-300 ${
             open ? "opacity-100" : "opacity-0"}`} />
      <div className={`absolute inset-x-0 bottom-0 flex h-[65%] flex-col rounded-t-2xl bg-zinc-900 transition-transform duration-300 ease-out ${
             open ? "translate-y-0" : "translate-y-full"}`}>
        <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
          <h3 className="text-sm font-bold">
            Comments {comments ? `(${comments.length})` : ""}
          </h3>
          <button onClick={onClose} className="p-1 text-zinc-400 active:text-white" aria-label="Close">
            ✕
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3 scrollbar-thin">
          {comments === null ? (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-pulse space-y-1.5">
                  <div className="h-3 w-24 rounded bg-zinc-800" />
                  <div className="h-3 w-3/4 rounded bg-zinc-800" />
                </div>
              ))}
            </div>
          ) : comments.length === 0 ? (
            <p className="pt-8 text-center text-sm text-zinc-500">
              No comments yet — be the first!
            </p>
          ) : (
            comments.map((c) => (
              <div key={c.id} className="animate-fade-in">
                <div className="flex items-baseline gap-2">
                  <span className="text-xs font-semibold text-zinc-300">{c.user_name}</span>
                  <span className="text-[10px] text-zinc-500">{timeAgo(c.created_at)}</span>
                  {c.is_mine && (
                    <button onClick={() => remove(c.id)}
                            className="ml-auto text-[10px] text-zinc-500 active:text-rose-400">
                      Delete
                    </button>
                  )}
                </div>
                <p className="mt-0.5 text-sm text-zinc-100">{c.body}</p>
              </div>
            ))
          )}
        </div>
        {needsLogin ? (
          <div className="border-t border-zinc-800 p-3 text-center text-sm text-zinc-400">
            <Link href="/login" className="text-rose-400">Log in</Link> to join the conversation
          </div>
        ) : (
          <form onSubmit={post} className="flex gap-2 border-t border-zinc-800 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            <input value={body} onChange={(e) => setBody(e.target.value)} maxLength={500}
                   placeholder="Add a comment..."
                   className="flex-1 rounded-full border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm outline-none focus:border-rose-500" />
            <button disabled={busy || !body.trim()}
                    className="rounded-full bg-rose-600 px-4 text-sm font-semibold active:bg-rose-500 disabled:opacity-40">
              Post
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
