// ── Types ──────────────────────────────────────────────────────────────────────

export type Status = "handed_off" | "collecting_info" | "bot_active" | "resolved";
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
  assigned_to_name?: string | null;
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

export interface Member {
  id: string;
  full_name: string;
  email: string;
  role: "admin" | "agent";
  whatsapp_number?: string | null;
}

export interface Shift {
  id: string;
  staff_user_id: string;
  weekday: number;
  start_time: string;
  end_time: string;
  staff_name?: string;
  staff_email?: string;
}

export interface StaffUser { email: string; name: string; role: "admin" | "agent" }

export type HandoffMode = "dashboard" | "whatsapp";

// Monday=0 … Sunday=6 (ISO weekday)
export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];


// ── Token management ───────────────────────────────────────────────────────────

const TOKEN_KEY = "lh_staff_token";
const BASE = (import.meta.env["VITE_API_BASE_URL"] as string) ?? "";

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string): void => { localStorage.setItem(TOKEN_KEY, t); };
export const clearToken = (): void => { localStorage.removeItem(TOKEN_KEY); };


// ── Core fetch helper ──────────────────────────────────────────────────────────

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw new Error((detail["detail"] as string) ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}


// ── Auth ───────────────────────────────────────────────────────────────────────

export const adminExists = async (): Promise<boolean> => {
  const r = await call<{ exists: boolean }>("POST", "/staff/auth/admin-exists");
  return r.exists;
};

export const login = async (email: string, password: string): Promise<StaffUser> => {
  const r = await call<{ token: string; name: string; role: string }>(
    "POST", "/staff/auth/login", { email, password }
  );
  setToken(r.token);
  return { email, name: r.name, role: r.role as "admin" | "agent" };
};

export const signup = async (
  email: string,
  name: string,
  password: string,
  role: string = "agent",
  whatsapp_number?: string,
): Promise<StaffUser> => {
  const r = await call<{ token: string; name: string; role: string }>(
    "POST", "/staff/auth/signup", { email, name, password, role, whatsapp_number }
  );
  setToken(r.token);
  return { email, name: r.name, role: r.role as "admin" | "agent" };
};

export const getMe = async (): Promise<StaffUser> =>
  call<StaffUser>("GET", "/staff/auth/me");

export const logout = (): void => { clearToken(); window.location.reload(); };


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
  const token = getToken();
  const res = await fetch(`${BASE}/staff/chats/${phone}/media`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (res.status === 401) { clearToken(); window.location.reload(); throw new Error("Unauthorized"); }
  if (!res.ok) throw new Error(`Media upload failed: ${res.status}`);
};

export const mediaUrl = async (_path: string): Promise<string | null> => null;


// ── Handoff management ─────────────────────────────────────────────────────────

export const resolveChat = async (phone: string): Promise<void> => {
  await call("POST", `/staff/chats/${phone}/resolve`);
};

export const deleteChat = async (phone: string): Promise<void> => {
  await call("DELETE", `/staff/chats/${phone}`);
};

export const assignChat = async (phone: string, staffId: string | null): Promise<void> => {
  await call("POST", `/staff/chats/${phone}/assign`, { staff_id: staffId });
};


// ── Users ──────────────────────────────────────────────────────────────────────

export const listMembers = async (): Promise<Member[]> =>
  call<Member[]>("GET", "/staff/users");

export const deleteUser = async (userId: string): Promise<void> => {
  await call("DELETE", `/staff/users/${userId}`);
};


// ── Invite ─────────────────────────────────────────────────────────────────────

export const inviteStaff = async (
  email: string,
  name: string,
  role: "admin" | "agent",
  whatsapp_number?: string,
): Promise<void> => {
  await call("POST", "/staff/invite", { email, name, role, whatsapp_number });
};


// ── Handoff mode ───────────────────────────────────────────────────────────────

export const getHandoffMode = async (): Promise<HandoffMode> => {
  const r = await call<{ mode: string }>("GET", "/staff/settings/handoff-mode");
  return r.mode as HandoffMode;
};

export const setHandoffMode = async (mode: HandoffMode): Promise<void> => {
  await call("PUT", "/staff/settings/handoff-mode", { mode });
};


// ── Shifts ─────────────────────────────────────────────────────────────────────

export const listShifts = async (): Promise<Shift[]> =>
  call<Shift[]>("GET", "/staff/shifts");

export const addShift = async (s: Omit<Shift, "id" | "staff_name" | "staff_email">): Promise<void> => {
  await call("POST", "/staff/shifts", s);
};

export const deleteShift = async (id: string): Promise<void> => {
  await call("DELETE", `/staff/shifts/${id}`);
};


// ── SSE real-time feed ─────────────────────────────────────────────────────────

export function openEventSource(
  onUpdate: (hasSound: boolean) => void,
): () => void {
  const token = getToken();
  if (!token) return () => {};
  const es = new EventSource(`${BASE}/staff/events?token=${encodeURIComponent(token)}`);
  es.onmessage = (e) => {
    if (e.data === "message") onUpdate(true);   // new tenant msg → sound
    else if (e.data === "refresh") onUpdate(false); // bot reply → silent
  };
  es.onerror = () => {};
  return () => es.close();
}


// ── Sorting / display helpers ──────────────────────────────────────────────────

const ORDER: Partial<Record<Status, number>> = {
  handed_off: 0,
  collecting_info: 1,
  bot_active: 2,
  resolved: 3,
};

export function sortChats(chats: ChatSummary[]) {
  return [...chats].sort((a, b) =>
    (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9) ||
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
