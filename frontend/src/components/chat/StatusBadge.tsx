import type { Status } from "@/lib/api";
const MAP: Record<Status, { label: string; cls: string }> = {
  handed_off: { label: "Needs staff", cls: "bg-status-handoff/15 text-status-handoff" },
  collecting_info: { label: "Collecting", cls: "bg-status-collect/20 text-foreground" },
  bot_active: { label: "Bot", cls: "bg-status-bot/15 text-status-bot" },
};
export function StatusBadge({ status }: { status: Status }) {
  const m = MAP[status] ?? MAP.bot_active;
  return <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${m.cls}`}>{m.label}</span>;
}
