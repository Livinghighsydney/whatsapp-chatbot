import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { Loader2, Trash2, UserPlus, Zap, MessageSquarePlus, Clock } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { listMembers, listShifts, addShift, deleteShift, assignWaiting, whoIsOnShift, simulateIncomingChat, DAYS } from "@/lib/api";
import { inviteMember, removeMember } from "@/lib/team.functions";

const field = "rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";

export function TeamPanel({ open, onOpenChange, meId }: { open: boolean; onOpenChange: (o: boolean) => void; meId: string }) {
  const qc = useQueryClient();
  const members = useQuery({ queryKey: ["members"], queryFn: listMembers, enabled: open });
  const shifts = useQuery({ queryKey: ["shifts"], queryFn: listShifts, enabled: open });
  const onShift = useQuery({ queryKey: ["onShift"], queryFn: whoIsOnShift, enabled: open, refetchInterval: 30000 });
  const invite = useServerFn(inviteMember); const remove = useServerFn(removeMember);
  const [f, setF] = useState({ full_name: "", email: "", password: "" });
  const [s, setS] = useState({ user_id: "", weekday: 1, start_time: "09:00", end_time: "17:00" });
  const refresh = () => { ["members", "shifts", "onShift", "chats"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); };
  const nameOf = (id?: string | null) => members.data?.find((m) => m.id === id)?.full_name || members.data?.find((m) => m.id === id)?.email || "—";

  const add = useMutation({ mutationFn: () => invite({ data: f }), onSuccess: () => { toast.success(`✅ ${f.full_name} can now sign in`); setF({ full_name: "", email: "", password: "" }); refresh(); }, onError: (e) => toast.error(e.message) });
  const del = useMutation({ mutationFn: (id: string) => remove({ data: { id } }), onSuccess: () => { toast.success("Member removed"); refresh(); }, onError: (e) => toast.error(e.message) });
  const newShift = useMutation({ mutationFn: () => addShift({ ...s, user_id: s.user_id || members.data?.[0]?.id || "" }), onSuccess: () => { toast.success("Shift added"); refresh(); }, onError: (e) => toast.error(e.message) });
  const dropShift = useMutation({ mutationFn: deleteShift, onSuccess: refresh });
  const assign = useMutation({ mutationFn: assignWaiting, onSuccess: (n) => { toast.success(n ? `Assigned ${n} waiting chat${n > 1 ? "s" : ""}` : "Nobody is on shift right now, or nothing is waiting"); refresh(); }, onError: (e) => toast.error(e.message) });
  const sim = useMutation({ mutationFn: simulateIncomingChat, onSuccess: (who) => { toast.success(who ? `New demo chat → ${nameOf(who)}` : "New demo chat — nobody on shift, left unassigned"); refresh(); }, onError: (e) => toast.error(e.message) });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader><SheetTitle>Team & shifts</SheetTitle></SheetHeader>
        <div className="mt-4 space-y-6">
          <div className="rounded-lg bg-accent p-3 text-sm">
            <div className="flex items-center gap-2 font-semibold"><Clock className="h-4 w-4" />On shift now (Pakistan time): {onShift.data ? nameOf(onShift.data) : "nobody"}</div>
            <p className="mt-1 text-xs text-muted-foreground">New chats go to whoever is on shift. If two people overlap, the one with fewer open chats gets it.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button onClick={() => assign.mutate()} disabled={assign.isPending} className="flex items-center gap-1.5 rounded-md bg-send px-3 py-1.5 text-xs font-bold text-send-foreground disabled:opacity-50"><Zap className="h-3.5 w-3.5" />Assign waiting chats now</button>
              <button onClick={() => sim.mutate()} disabled={sim.isPending} className="flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-bold disabled:opacity-50"><MessageSquarePlus className="h-3.5 w-3.5" />Simulate a new chat</button>
            </div>
          </div>

          <section>
            <h3 className="mb-2 font-bold">Members</h3>
            {members.isLoading && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
            <ul className="divide-y divide-border rounded-lg border border-border">
              {members.data?.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-2 p-2.5 text-sm">
                  <div className="min-w-0"><div className="truncate font-semibold">{m.full_name || m.email} {m.role === "admin" && <span className="ml-1 rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-bold text-primary">ADMIN</span>}</div><div className="truncate text-xs text-muted-foreground">{m.email}</div></div>
                  {m.id !== meId && <button aria-label={`Remove ${m.email}`} onClick={() => confirm(`Remove ${m.full_name || m.email}?`) && del.mutate(m.id)} className="rounded p-1.5 text-destructive hover:bg-destructive/10"><Trash2 className="h-4 w-4" /></button>}
                </li>
              ))}
            </ul>
            <form onSubmit={(e) => { e.preventDefault(); add.mutate(); }} className="mt-3 grid gap-2 rounded-lg border border-dashed border-border p-3">
              <div className="flex items-center gap-1.5 text-sm font-semibold"><UserPlus className="h-4 w-4" />Add team member</div>
              <input required placeholder="Full name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} className={field} />
              <input required type="email" placeholder="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} className={field} />
              <input required minLength={8} placeholder="Temporary password (8+ characters)" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} className={field} />
              <button disabled={add.isPending} className="flex items-center justify-center gap-2 rounded-md bg-send py-2 text-sm font-bold text-send-foreground disabled:opacity-50">{add.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Add member</button>
              <p className="text-xs text-muted-foreground">Share the email and password with them so they can sign in.</p>
            </form>
          </section>

          <section>
            <h3 className="mb-2 font-bold">Shifts <span className="text-xs font-normal text-muted-foreground">(Pakistan time)</span></h3>
            <ul className="divide-y divide-border rounded-lg border border-border">
              {shifts.data?.length === 0 && <li className="p-3 text-sm text-muted-foreground">No shifts yet — chats stay unassigned until you add some.</li>}
              {shifts.data?.map((x) => (
                <li key={x.id} className="flex items-center justify-between p-2.5 text-sm">
                  <span><b>{DAYS[x.weekday]}</b> {x.start_time.slice(0, 5)}–{x.end_time.slice(0, 5)} · {nameOf(x.user_id)}</span>
                  <button aria-label="Delete shift" onClick={() => dropShift.mutate(x.id)} className="rounded p-1.5 text-destructive hover:bg-destructive/10"><Trash2 className="h-4 w-4" /></button>
                </li>
              ))}
            </ul>
            <form onSubmit={(e) => { e.preventDefault(); newShift.mutate(); }} className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-border p-3">
              <select aria-label="Member" value={s.user_id} onChange={(e) => setS({ ...s, user_id: e.target.value })} className={field}>
                {members.data?.map((m) => <option key={m.id} value={m.id}>{m.full_name || m.email}</option>)}
              </select>
              <select aria-label="Day" value={s.weekday} onChange={(e) => setS({ ...s, weekday: +e.target.value })} className={field}>
                {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
              </select>
              <input aria-label="Start" type="time" value={s.start_time} onChange={(e) => setS({ ...s, start_time: e.target.value })} className={field} />
              <span>–</span>
              <input aria-label="End" type="time" value={s.end_time} onChange={(e) => setS({ ...s, end_time: e.target.value })} className={field} />
              <button disabled={newShift.isPending} className="rounded-md bg-send px-3 py-1.5 text-sm font-bold text-send-foreground disabled:opacity-50">Add shift</button>
            </form>
            <p className="mt-1 text-xs text-muted-foreground">Night shifts work too, e.g. 22:00–06:00.</p>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}
