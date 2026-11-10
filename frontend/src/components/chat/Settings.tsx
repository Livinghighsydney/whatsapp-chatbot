import { useState } from "react";
import { X, Mail, User, Send, CheckCircle2, AlertCircle } from "lucide-react";
import { inviteStaff } from "@/lib/api";

interface SettingsProps {
  open: boolean;
  onClose: () => void;
}

export function Settings({ open, onClose }: SettingsProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  if (!open) return null;

  const reset = () => { setName(""); setEmail(""); setResult(null); };

  const handleClose = () => { reset(); onClose(); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      await inviteStaff(email.trim(), name.trim());
      setResult({ ok: true, msg: `Invite sent to ${email.trim()}` });
      setName("");
      setEmail("");
    } catch (err) {
      setResult({ ok: false, msg: err instanceof Error ? err.message : "Failed to send invite" });
    } finally {
      setBusy(false);
    }
  };

  const field = "flex w-full items-center gap-3 rounded-lg border border-input bg-background px-3 py-2.5 focus-within:ring-2 focus-within:ring-ring";
  const inputCls = "flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground";

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={handleClose}
      />

      {/* Sheet — slides in from the right */}
      <div className="fixed inset-y-0 right-0 z-50 flex h-full w-full max-w-sm flex-col bg-card shadow-2xl animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between bg-brand px-5 pb-4 pt-[max(1rem,env(safe-area-inset-top))] text-brand-foreground">
          <h2 className="text-lg font-extrabold">Settings</h2>
          <button
            onClick={handleClose}
            aria-label="Close settings"
            className="rounded-full p-1.5 hover:bg-brand-foreground/10"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Invite section */}
          <section>
            <p className="mb-1 text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Team
            </p>
            <h3 className="mb-4 text-base font-bold text-foreground">Invite a team member</h3>

            <form onSubmit={submit} className="space-y-3">
              <div className={field}>
                <User className="h-4 w-4 shrink-0 text-muted-foreground" />
                <input
                  required
                  placeholder="Full name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className={inputCls}
                />
              </div>

              <div className={field}>
                <Mail className="h-4 w-4 shrink-0 text-muted-foreground" />
                <input
                  required
                  type="email"
                  placeholder="Email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputCls}
                />
              </div>

              {result && (
                <div
                  className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm ${
                    result.ok
                      ? "bg-primary/10 text-primary"
                      : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {result.ok ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 shrink-0" />
                  )}
                  {result.msg}
                </div>
              )}

              <button
                type="submit"
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-send py-2.5 font-bold text-send-foreground transition hover:brightness-95 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                {busy ? "Sending…" : "Send invite"}
              </button>
            </form>

            <p className="mt-3 text-xs text-muted-foreground">
              The invitee will receive an email with a sign-up link. They can then sign in to this
              dashboard.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
