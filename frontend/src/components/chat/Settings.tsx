import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2, UserPlus, Clock, ToggleLeft, ToggleRight } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  listMembers, deleteUser, inviteStaff,
  listShifts, addShift, deleteShift,
  getHandoffMode, setHandoffMode,
  type Member, type Shift, DAYS,
} from "@/lib/api";

const inputCls = "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring";

interface Props {
  open: boolean;
  onClose: () => void;
  isAdmin: boolean;
}

// ── Handoff mode toggle ────────────────────────────────────────────────────────

function HandoffToggle() {
  const qc = useQueryClient();
  const { data: mode, isLoading } = useQuery({
    queryKey: ["handoffMode"],
    queryFn: getHandoffMode,
  });
  const toggle = useMutation({
    mutationFn: () => setHandoffMode(mode === "dashboard" ? "whatsapp" : "dashboard"),
    onSuccess: () => {
      toast.success("Handoff mode updated");
      qc.invalidateQueries({ queryKey: ["handoffMode"] });
    },
    onError: () => toast.error("Failed to update mode"),
  });

  if (isLoading) return <div className="h-16 animate-pulse rounded-xl bg-muted" />;

  const isDash = mode === "dashboard";
  return (
    <div className="flex items-center justify-between rounded-xl border border-border bg-card p-4">
      <div>
        <p className="font-semibold text-sm">Handoff mode</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {isDash
            ? "Agents handle escalated chats in this dashboard"
            : "Agents receive WhatsApp alerts on their personal phone"}
        </p>
      </div>
      <button
        onClick={() => toggle.mutate()}
        disabled={toggle.isPending}
        aria-label="Toggle handoff mode"
        className="ml-4 shrink-0 disabled:opacity-50"
      >
        {isDash
          ? <ToggleRight className="h-9 w-9 text-primary" />
          : <ToggleLeft className="h-9 w-9 text-muted-foreground" />}
      </button>
    </div>
  );
}

// ── Team tab ───────────────────────────────────────────────────────────────────

function TeamTab({ isAdmin }: { isAdmin: boolean }) {
  const qc = useQueryClient();
  const { data: members = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: listMembers,
  });
  const [form, setForm] = useState({ name: "", email: "", role: "agent" as "admin" | "agent", wa: "" });
  const [busy, setBusy] = useState(false);

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email.trim()) return;
    setBusy(true);
    try {
      await inviteStaff(form.email.trim(), form.name.trim(), form.role, form.wa.trim() || undefined);
      toast.success(`Invite sent to ${form.email}`);
      setForm({ name: "", email: "", role: "agent", wa: "" });
      qc.invalidateQueries({ queryKey: ["users"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to send invite");
    } finally {
      setBusy(false);
    }
  };

  const remove = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => { toast.success("Member removed"); qc.invalidateQueries({ queryKey: ["users"] }); },
    onError: () => toast.error("Failed to remove member"),
  });

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">Members</h3>
        {isLoading && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
        <ul className="divide-y divide-border rounded-xl border border-border">
          {members.length === 0 && !isLoading && (
            <li className="p-3 text-sm text-muted-foreground">No members yet.</li>
          )}
          {members.map((m: Member) => (
            <li key={m.id} className="flex items-center justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-sm font-semibold">{m.full_name || m.email}</span>
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                    m.role === "admin"
                      ? "bg-primary/15 text-primary"
                      : "bg-muted text-muted-foreground"
                  }`}>{m.role.toUpperCase()}</span>
                </div>
                <div className="truncate text-xs text-muted-foreground">{m.email}</div>
                {m.whatsapp_number && (
                  <div className="text-xs text-muted-foreground">+{m.whatsapp_number}</div>
                )}
              </div>
              {isAdmin && (
                <button
                  onClick={() => {
                    if (confirm(`Remove ${m.full_name || m.email}?`)) remove.mutate(m.id);
                  }}
                  aria-label="Remove member"
                  className="shrink-0 rounded p-1.5 text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>

      {isAdmin && (
        <form onSubmit={invite} className="space-y-2 rounded-xl border border-dashed border-border p-3">
          <div className="flex items-center gap-1.5 text-sm font-semibold">
            <UserPlus className="h-4 w-4" /> Invite team member
          </div>
          <input
            required
            placeholder="Full name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={inputCls}
          />
          <input
            required
            type="email"
            placeholder="Email address"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className={inputCls}
          />
          <input
            placeholder="WhatsApp number (e.g. 61412345678)"
            value={form.wa}
            onChange={(e) => setForm({ ...form, wa: e.target.value })}
            className={inputCls}
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as "admin" | "agent" })}
            className={inputCls}
          >
            <option value="agent">Agent</option>
            <option value="admin">Admin</option>
          </select>
          <button
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-send py-2 text-sm font-bold text-send-foreground disabled:opacity-50"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            Send invite
          </button>
        </form>
      )}
    </div>
  );
}

// ── Shifts tab ─────────────────────────────────────────────────────────────────

function ShiftsTab({ isAdmin }: { isAdmin: boolean }) {
  const qc = useQueryClient();
  const { data: shifts = [], isLoading: loadingShifts } = useQuery({
    queryKey: ["shifts"],
    queryFn: listShifts,
  });
  const { data: members = [] } = useQuery({
    queryKey: ["users"],
    queryFn: listMembers,
  });

  const [form, setForm] = useState({
    staff_user_id: "",
    weekday: 0,
    start_time: "09:00",
    end_time: "17:00",
  });
  const [busy, setBusy] = useState(false);

  const addShiftSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const uid = form.staff_user_id || members[0]?.id;
    if (!uid) { toast.error("Select a team member first"); return; }
    setBusy(true);
    try {
      await addShift({ ...form, staff_user_id: uid });
      toast.success("Shift added");
      qc.invalidateQueries({ queryKey: ["shifts"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to add shift");
    } finally {
      setBusy(false);
    }
  };

  const remove = useMutation({
    mutationFn: deleteShift,
    onSuccess: () => { toast.success("Shift removed"); qc.invalidateQueries({ queryKey: ["shifts"] }); },
    onError: () => toast.error("Failed to remove shift"),
  });

  const byDay = DAYS.map((day, i) => ({
    day,
    idx: i,
    shifts: (shifts as Shift[]).filter((s) => s.weekday === i),
  }));

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        All times are AEST/AEDT. When shifts overlap, the most recently started one takes priority.
      </p>

      {isAdmin && (
        <form onSubmit={addShiftSubmit} className="space-y-2 rounded-xl border border-dashed border-border p-3">
          <div className="flex items-center gap-1.5 text-sm font-semibold">
            <Clock className="h-4 w-4" /> Add shift
          </div>
          <select
            value={form.staff_user_id || members[0]?.id || ""}
            onChange={(e) => setForm({ ...form, staff_user_id: e.target.value })}
            className={inputCls}
          >
            {members.length === 0 && <option value="">— invite members first —</option>}
            {members.map((m: Member) => (
              <option key={m.id} value={m.id}>{m.full_name || m.email}</option>
            ))}
          </select>
          <select
            value={form.weekday}
            onChange={(e) => setForm({ ...form, weekday: +e.target.value })}
            className={inputCls}
          >
            {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
          <div className="flex items-center gap-2">
            <input
              type="time"
              value={form.start_time}
              onChange={(e) => setForm({ ...form, start_time: e.target.value })}
              className={`${inputCls} flex-1`}
            />
            <span className="text-xs text-muted-foreground">to</span>
            <input
              type="time"
              value={form.end_time}
              onChange={(e) => setForm({ ...form, end_time: e.target.value })}
              className={`${inputCls} flex-1`}
            />
          </div>
          <button
            disabled={busy || members.length === 0}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-send py-2 text-sm font-bold text-send-foreground disabled:opacity-50"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            Add shift
          </button>
        </form>
      )}

      {loadingShifts && <Loader2 className="h-5 w-5 animate-spin text-primary" />}

      {byDay.map(({ day, idx, shifts: dayShifts }) =>
        dayShifts.length === 0 ? null : (
          <div key={idx}>
            <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-foreground">{day}</h4>
            <ul className="divide-y divide-border rounded-xl border border-border">
              {dayShifts.map((s) => (
                <li key={s.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <div>
                    <span className="font-semibold">{s.staff_name || s.staff_email}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {s.start_time.slice(0, 5)} – {s.end_time.slice(0, 5)} AEST
                    </span>
                  </div>
                  {isAdmin && (
                    <button
                      onClick={() => remove.mutate(s.id)}
                      aria-label="Delete shift"
                      className="rounded p-1.5 text-destructive hover:bg-destructive/10"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      )}

      {!loadingShifts && (shifts as Shift[]).length === 0 && (
        <p className="text-sm text-muted-foreground">No shifts yet — add one above.</p>
      )}
    </div>
  );
}

// ── Main modal ─────────────────────────────────────────────────────────────────

export function Settings({ open, onClose, isAdmin }: Props) {
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader className="mb-4">
          <SheetTitle>Settings</SheetTitle>
        </SheetHeader>

        {isAdmin && (
          <div className="mb-6">
            <HandoffToggle />
          </div>
        )}

        <Tabs defaultValue="team">
          <TabsList className="mb-4 w-full">
            <TabsTrigger value="team" className="flex-1">Team</TabsTrigger>
            <TabsTrigger value="shifts" className="flex-1">Shifts</TabsTrigger>
          </TabsList>
          <TabsContent value="team">
            <TeamTab isAdmin={isAdmin} />
          </TabsContent>
          <TabsContent value="shifts">
            <ShiftsTab isAdmin={isAdmin} />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
