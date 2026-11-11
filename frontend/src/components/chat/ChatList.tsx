import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, LogOut, Loader2, MessagesSquare, Users, Settings } from "lucide-react";
import { listChats, sortChats, displayName, initials, formatListTime, openEventSource, type Member } from "@/lib/api";
import { playNotification, requestNotificationPermission, showDesktopNotification } from "@/lib/notify";
import { StatusBadge } from "./StatusBadge";

export function ChatList({ selected, onSelect, onLogout, isAdmin, members, onTeam, onSettings }: { selected: string | null; onSelect: (p: string) => void; onLogout: () => void; isAdmin: boolean; members: Member[]; onTeam: () => void; onSettings: () => void }) {
  const who = (id?: string | null) => { const m = members.find((x) => x.id === id); return m ? (m.full_name || m.email).split(" ")[0] : "Unassigned"; };
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["chats"], queryFn: listChats, refetchInterval: 15000 });
  const [term, setTerm] = useState("");
  const [pull, setPull] = useState(0);
  const startY = useRef<number | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => { requestNotificationPermission(); }, []);
  useEffect(() => openEventSource((hasSound) => {
    qc.invalidateQueries({ queryKey: ["chats"] });
    if (hasSound) {
      playNotification();
      showDesktopNotification("Living High", "New message from a tenant");
    }
  }), [qc]);

  const chats = useMemo(() => {
    const t = term.toLowerCase().trim();
    const list = sortChats(q.data ?? []);
    return t ? list.filter((c) => [c.name, c.phone, c.property, c.room].some((v) => v?.toLowerCase().includes(t))) : list;
  }, [q.data, term]);

  return (
    <div className="flex h-full flex-col bg-card">
      <header className="flex items-center justify-between bg-brand px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] text-brand-foreground">
        <h1 className="text-lg font-extrabold">Living High <span className="font-normal opacity-80">Staff</span></h1>
        <div className="flex items-center">
          {isAdmin && <button onClick={onTeam} aria-label="Team and shifts" className="rounded-full p-2 hover:bg-brand-foreground/10"><Users className="h-5 w-5" /></button>}
          <button onClick={onSettings} aria-label="Settings" className="rounded-full p-2 hover:bg-brand-foreground/10"><Settings className="h-5 w-5" /></button>
          <button onClick={onLogout} aria-label="Sign out" className="rounded-full p-2 hover:bg-brand-foreground/10"><LogOut className="h-5 w-5" /></button>
        </div>
      </header>
      <div className="border-b border-border p-2">
        <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Search name, phone or property"
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
        </div>
      </div>
      <div ref={scroller} className="flex-1 overflow-y-auto overscroll-contain"
        onTouchStart={(e) => { if ((scroller.current?.scrollTop ?? 0) <= 0) startY.current = (e.touches[0]?.clientY ?? 0); }}
        onTouchMove={(e) => { if (startY.current != null) setPull(Math.max(0, Math.min(80, (e.touches[0]?.clientY ?? 0) - startY.current))); }}
        onTouchEnd={() => { if (pull > 60) q.refetch(); setPull(0); startY.current = null; }}>
        <div style={{ height: pull }} className="flex items-center justify-center overflow-hidden transition-[height]">
          {pull > 0 && <Loader2 className={`h-5 w-5 text-primary ${pull > 60 ? "animate-spin" : ""}`} />}
        </div>
        {q.isLoading && <div className="flex justify-center p-8"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>}
        {!q.isLoading && chats.length === 0 && (
          <div className="flex flex-col items-center gap-2 p-10 text-center text-muted-foreground">
            <MessagesSquare className="h-10 w-10" />{term ? "No matches" : isAdmin ? "No conversations yet" : "No chats assigned to you yet"}
          </div>
        )}
        {chats.map((c) => (
          <button key={c.phone} onClick={() => onSelect(c.phone)}
            className={`flex w-full items-center gap-3 border-b border-border px-3 py-3 text-left transition-colors hover:bg-muted active:bg-accent ${selected === c.phone ? "bg-accent" : ""}`}>
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-bold text-primary">{initials(c)}</div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-bold">{displayName(c)}</span>
                <span className={`shrink-0 text-xs ${c.last_role === "user" ? "font-bold text-unread" : "text-muted-foreground"}`}>{formatListTime(c.last_ts)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="truncate text-xs text-muted-foreground">{[c.room, c.property].filter(Boolean).join(", ") || "—"}</span>
                <StatusBadge status={c.status} />
                {isAdmin && <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold ${c.assigned_to ? "bg-muted text-muted-foreground" : "bg-destructive/15 text-destructive"}`}>{who(c.assigned_to)}</span>}
              </div>
              <div className="mt-0.5 flex items-center justify-between gap-2">
                <span className="truncate text-sm text-muted-foreground">{c.last_message}</span>
                {c.last_role === "user" && <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-unread" aria-label="Unread" />}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
