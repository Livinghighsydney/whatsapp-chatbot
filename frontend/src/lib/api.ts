// ── Types (unchanged — all components import from here) ───────────────────────

export type Status = "handed_off" | "collecting_info" | "bot_active";
export type Role = "user" | "assistant" | "staff";

export interface ChatSummary {
  id?: string;
  phone: string;
  name?: string | null;
  property?: string | null;
  room?: string | null;
  status: Status;
  last_message?: string | null;
  last_role?: Role | null;
  last_ts?: string | null;
  assigned_to?: string | null;
}

export interface Message {
  role: Role;
  content: string;
  ts: string;
  pending?: boolean;
  media_path?: string | null;
}

export interface ChatDetail extends ChatSummary {
  history: Message[];
}

// Kept for TeamPanel type compatibility — not used with Railway backend
export interface Member { id: string; full_name: string; email: string; role: "admin" | "agent" }
export interface Shift { id: string; user_id: string; weekday: number; start_time: string; end_time: string }


// ── Core fetch helper ──────────────────────────────────────────────────────────

const BASE = (import.meta.env["VITE_API_BASE_URL"] as string) ?? "";
// Hidden API key — users never see or type this; auth is handled by Supabase
const API_KEY = (import.meta.env["VITE_STAFF_DASHBOARD_TOKEN"] as string) ?? "";

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (API_KEY) headers["Authorization"] = `Bearer ${API_KEY}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}


// ── Chat list ──────────────────────────────────────────────────────────────────

export const listChats = async (): Promise<ChatSummary[]> =>
  call<ChatSummary[]>("GET", "/staff/chats");


// ── Single conversation ────────────────────────────────────────────────────────

export const getChat = async (phone: string): Promise<ChatDetail> =>
  call<ChatDetail>("GET", `/staff/chats/${phone}`);


// ── Send messages ──────────────────────────────────────────────────────────────

export const sendMessage = async (phone: string, message: string): Promise<void> => {
  await call("POST", `/staff/chats/${phone}/send`, { message });
};

export const sendMedia = async (phone: string, file: File): Promise<void> => {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/staff/chats/${phone}/media`, {
    method: "POST",
    headers: API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error(`Media upload failed: ${res.status}`);
};

// Media is sent directly to WhatsApp — no stored URL to retrieve
export const mediaUrl = async (_path: string): Promise<string | null> => null;


// ── Handoff management ─────────────────────────────────────────────────────────

export const resolveChat = async (phone: string): Promise<void> => {
  await call("POST", `/staff/chats/${phone}/resolve`);
};

export const deleteChat = async (phone: string): Promise<void> => {
  await call("DELETE", `/staff/chats/${phone}`);
};

// Chat assignment is not supported by the Railway backend — no-op
export const assignChat = async (_phone: string, _userId: string | null): Promise<void> => {};


// ── Invite ─────────────────────────────────────────────────────────────────────

export const inviteStaff = async (email: string, name: string): Promise<void> => {
  await call("POST", "/staff/invite", { email, name });
};


// ── Team / shift stubs (TeamPanel is hidden — isAdmin is always false) ─────────

export const listMembers = async (): Promise<Member[]> => [];
export const listShifts = async (): Promise<Shift[]> => [];
export const addShift = async (_s: Omit<Shift, "id">): Promise<void> => {};
export const deleteShift = async (_id: string): Promise<void> => {};
export const assignWaiting = async (): Promise<number> => 0;
export const whoIsOnShift = async (): Promise<string | null> => null;
export const simulateIncomingChat = async (): Promise<string | null> => null;


// ── Sorting / display helpers (unchanged) ──────────────────────────────────────

const ORDER: Record<Status, number> = { handed_off: 0, collecting_info: 1, bot_active: 2 };

export function sortChats(chats: ChatSummary[]) {
  return [...chats].sort((a, b) =>
    (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3) ||
    new Date(b.last_ts ?? 0).getTime() - new Date(a.last_ts ?? 0).getTime()
  );
}

export const displayName = (c: Pick<ChatSummary, "name" | "phone">) =>
  c.name || `+${c.phone}`;

export const initials = (c: Pick<ChatSummary, "name" | "phone">) =>
  c.name
    ? c.name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase()
    : c.phone.slice(-4);

export function formatListTime(ts?: string | null) {
  if (!ts) return "";
  const d = new Date(ts);
  const now = new Date();
  return d.toDateString() === now.toDateString()
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString([], { day: "numeric", month: "short" });
}

export const formatMsgTime = (ts: string) => {
  const d = new Date(ts);
  const today = d.toDateString() === new Date().toDateString();
  const t = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return today ? t : `${d.toLocaleDateString([], { day: "numeric", month: "short" })}, ${t}`;
};

export const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
