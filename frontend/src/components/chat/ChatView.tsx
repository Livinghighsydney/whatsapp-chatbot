import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, MoreVertical, Paperclip, SendHorizontal, X, Loader2, FileText, CheckCircle2, Trash2, UserRound } from "lucide-react";
import { toast } from "sonner";
import { getChat, sendMessage, sendMedia, resolveChat, deleteChat, assignChat, mediaUrl, openEventSource, type Member, displayName, initials, formatMsgTime, type ChatDetail, type Message } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

const LABEL = { user: "Tenant", assistant: "Bot", staff: "You" } as const;

function Bubble({ m }: { m: Message }) {
  const mine = m.role === "staff";
  const bg = m.role === "staff" ? "bg-bubble-staff" : m.role === "assistant" ? "bg-bubble-bot" : "bg-bubble-user";
  const tail = m.role === "staff" ? "var(--bubble-staff)" : m.role === "assistant" ? "var(--bubble-bot)" : "var(--bubble-user)";
  return (
    <div className={`flex animate-bubble flex-col ${mine ? "items-end" : "items-start"} ${m.pending ? "opacity-60" : ""}`}>
      <div style={{ ["--tail" as string]: tail }}
        className={`max-w-[80%] rounded-lg px-3 py-1.5 shadow-sm md:max-w-[65%] ${bg} ${mine ? "rounded-tr-none bubble-tail-right" : "rounded-tl-none bubble-tail-left"}`}>
        <div className={`text-[11px] font-bold ${m.role === "user" ? "text-primary" : "text-muted-foreground"}`}>{LABEL[m.role]}</div>
        {m.media_path ? <button onClick={async () => { const u = await mediaUrl(m.media_path!); if (u) window.open(u, "_blank"); }} className="whitespace-pre-wrap break-words text-left text-[15px] leading-snug underline">{m.content}</button> : <div className="whitespace-pre-wrap break-words text-[15px] leading-snug">{m.content}</div>}
      </div>
      <span className="mt-0.5 px-1 text-[11px] text-muted-foreground">{m.pending ? "Sending…" : formatMsgTime(m.ts)}</span>
    </div>
  );
}

export function ChatView({ phone, onBack, isAdmin, members }: { phone: string; onBack: () => void; isAdmin: boolean; members: Member[] }) {
  const qc = useQueryClient();
  const key = ["chat", phone];
  const q = useQuery({ queryKey: key, queryFn: () => getChat(phone), refetchInterval: 15000 });
  const [text, setText] = useState(""); const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null); const [confirmDel, setConfirmDel] = useState(false);
  const endRef = useRef<HTMLDivElement>(null); const fileRef = useRef<HTMLInputElement>(null); const taRef = useRef<HTMLTextAreaElement>(null);

  // When opening a chat, mark it read on the server (GET fires automatically via useQuery)
  // and refresh the list so the unread badge disappears immediately
  useEffect(() => {
    setText(""); setFile(null);
    qc.invalidateQueries({ queryKey: ["chats"] });
  }, [phone]);
  useEffect(() => {
    if (!file || !/^(image|video)\//.test(file.type)) { setPreview(null); return; }
    const u = URL.createObjectURL(file); setPreview(u); return () => URL.revokeObjectURL(u);
  }, [file]);
  const count = q.data?.history.length ?? 0;
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [count, phone]);
  useEffect(() => { const t = taRef.current; if (t) { t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 104) + "px"; } }, [text]);
  useEffect(() => openEventSource((_s) => qc.invalidateQueries({ queryKey: key })), [phone]);

  const send = useMutation({
    mutationFn: async ({ msg, f }: { msg: string; f: File | null }) => {
      if (f) await sendMedia(phone, f);
      if (msg) await sendMessage(phone, msg);
    },
    onMutate: async ({ msg, f }) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<ChatDetail>(key);
      const now = new Date().toISOString();
      const add: Message[] = [];
      if (f) add.push({ role: "staff", content: `📎 ${f.name}`, ts: now, pending: true });
      if (msg) add.push({ role: "staff", content: msg, ts: now, pending: true });
      if (prev) qc.setQueryData<ChatDetail>(key, { ...prev, history: [...prev.history, ...add] });
      setText(""); setFile(null);
      return { prev, msg, f };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      if (ctx) { setText(ctx.msg); setFile(ctx.f); }
      toast.error("❌ Failed to send");
    },
    onSuccess: (_d, { msg, f }) => {
      if (f) toast.success("✅ Media sent"); if (msg) toast.success("✅ Message sent");
      qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["chats"] });
    },
  });
  const resolve = useMutation({
    mutationFn: () => resolveChat(phone),
    onSuccess: () => { toast.success("✅ Handoff resolved"); qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["chats"] }); },
    onError: () => toast.error("❌ Couldn't resolve handoff"),
  });
  const reassign = useMutation({
    mutationFn: (id: string | null) => assignChat(phone, id),
    onSuccess: () => { toast.success("✅ Chat reassigned"); qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["chats"] }); },
    onError: () => toast.error("❌ Couldn't reassign"),
  });
  const del = useMutation({
    mutationFn: () => deleteChat(phone),
    onSuccess: () => { toast.success("✅ Chat deleted"); qc.removeQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["chats"] }); onBack(); },
    onError: () => toast.error("❌ Couldn't delete chat"),
  });

  const c = q.data ?? (qc.getQueryData<{ phone: string }[]>(["chats"])?.find((x) => x.phone === phone) as ChatDetail | undefined);
  const canSend = (text.trim() || file) && !send.isPending;
  const submit = () => { if (canSend) send.mutate({ msg: text.trim(), f: file }); };

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-2 bg-brand px-2 pb-2 pt-[max(0.5rem,env(safe-area-inset-top))] text-brand-foreground md:px-4">
        <button onClick={onBack} aria-label="Back" className="rounded-full p-2 hover:bg-brand-foreground/10 md:hidden"><ArrowLeft className="h-5 w-5" /></button>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-foreground/20 text-sm font-bold">{c ? initials(c) : ""}</div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><span className="truncate font-bold">{c ? displayName(c) : `+${phone}`}</span>{c?.status && <span className="rounded-full bg-card"><StatusBadge status={c.status} /></span>}</div>
          <div className="truncate text-xs opacity-80">{[c?.room, c?.property].filter(Boolean).join(", ")}</div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger aria-label="Menu" className="rounded-full p-2 hover:bg-brand-foreground/10"><MoreVertical className="h-5 w-5" /></DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {c?.status === "handed_off" && <DropdownMenuItem onClick={() => resolve.mutate()}><CheckCircle2 className="mr-2 h-4 w-4" />Resolve handoff</DropdownMenuItem>}
            {isAdmin && members.map((m) => m.id !== c?.assigned_to && (
              <DropdownMenuItem key={m.id} onClick={() => reassign.mutate(m.id)}><UserRound className="mr-2 h-4 w-4" />Assign to {m.full_name || m.email}</DropdownMenuItem>
            ))}
            <DropdownMenuItem onClick={() => setConfirmDel(true)} className="text-destructive focus:text-destructive"><Trash2 className="mr-2 h-4 w-4" />Delete conversation</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <div className="chat-wall flex-1 space-y-2 overflow-y-auto overscroll-contain px-3 py-4 md:px-12">
        {q.isLoading && <div className="flex justify-center p-8"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>}
        {q.data?.history.map((m, i) => <Bubble key={`${m.ts}-${i}`} m={m} />)}
        <div ref={endRef} />
      </div>

      {file && (
        <div className="flex items-center gap-3 border-t border-border bg-card px-3 py-2">
          {preview && file.type.startsWith("image/") ? <img src={preview} alt="" className="h-14 w-14 rounded object-cover" />
            : preview ? <video src={preview} className="h-14 w-14 rounded object-cover" />
            : <div className="flex h-14 w-14 items-center justify-center rounded bg-muted"><FileText /></div>}
          <span className="flex-1 truncate text-sm">{file.name}</span>
          <button onClick={() => setFile(null)} aria-label="Remove file" className="rounded-full p-1.5 hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>
      )}
      <div className="flex items-end gap-2 bg-muted px-2 pt-2 pb-safe">
        <input ref={fileRef} type="file" hidden accept="image/*,video/*,audio/*,.pdf" onChange={(e) => { setFile(e.target.files?.[0] ?? null); e.target.value = ""; }} />
        <button disabled={send.isPending} onClick={() => fileRef.current?.click()} aria-label="Attach" className="rounded-full p-2.5 text-muted-foreground hover:bg-card disabled:opacity-50"><Paperclip className="h-5 w-5" /></button>
        <textarea ref={taRef} rows={1} value={text} disabled={send.isPending} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && window.matchMedia("(min-width: 768px)").matches) { e.preventDefault(); submit(); } }}
          placeholder="Type a message" className="max-h-[104px] flex-1 resize-none rounded-2xl bg-card px-4 py-2.5 text-[15px] outline-none disabled:opacity-60" />
        <button onClick={submit} disabled={!canSend} aria-label="Send" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-send text-send-foreground transition active:scale-95 disabled:opacity-40">
          {send.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <SendHorizontal className="h-5 w-5" />}
        </button>
      </div>

      <AlertDialog open={confirmDel} onOpenChange={setConfirmDel}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
            <AlertDialogDescription>The chat history with {c ? displayName(c) : phone} will be permanently removed.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => del.mutate()} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Delete</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
