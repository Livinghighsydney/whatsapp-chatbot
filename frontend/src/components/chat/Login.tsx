import { useEffect, useState } from "react";
import { Loader2, Building2 } from "lucide-react";
import { login, signup, adminExists, type StaffUser } from "@/lib/api";

interface LoginProps {
  onLogin: (user: StaffUser) => void;
}

export function Login({ onLogin }: LoginProps) {
  const params = new URLSearchParams(window.location.search);
  const isInviteMode = params.get("invite") === "1";
  const inviteEmail = params.get("email") ?? "";
  const inviteRole = (params.get("role") ?? "agent") as "admin" | "agent";

  const [mode, setMode] = useState<"loading" | "signin" | "signup">(
    isInviteMode ? "signup" : "loading"
  );
  const [name, setName] = useState("");
  const [email, setEmail] = useState(inviteEmail);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isInviteMode) {
      adminExists().then((exists) => setMode(exists ? "signin" : "signup"));
    }
  }, [isInviteMode]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      let user: StaffUser;
      if (mode === "signup") {
        user = await signup(email.trim(), name.trim(), pw, inviteRole);
      } else {
        user = await login(email.trim(), pw);
      }
      onLogin(user);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const field =
    "w-full rounded-lg border border-input bg-background px-3 py-2.5 outline-none focus:ring-2 focus:ring-ring";

  if (mode === "loading") {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-brand">
        <Loader2 className="h-10 w-10 animate-spin text-brand-foreground" />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <div className="h-56 bg-brand" />
      <div className="-mt-40 flex flex-1 justify-center px-4">
        <form onSubmit={submit} className="h-fit w-full max-w-sm rounded-2xl bg-card p-8 shadow-xl animate-bubble">
          <div className="mb-6 flex flex-col items-center gap-3 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-send text-send-foreground">
              <Building2 />
            </div>
            <h1 className="text-2xl font-extrabold text-brand">Living High</h1>
            <p className="text-sm text-muted-foreground">
              {mode === "signup"
                ? isInviteMode ? "Create your account" : "Create the first admin account"
                : "Team sign in"}
            </p>
          </div>

          {mode === "signup" && (
            <>
              <label className="mb-1 block text-xs font-semibold text-muted-foreground" htmlFor="nm">
                Your name
              </label>
              <input
                id="nm"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={`${field} mb-3`}
              />
            </>
          )}

          <label className="mb-1 block text-xs font-semibold text-muted-foreground" htmlFor="em">
            Email
          </label>
          <input
            id="em"
            type="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={`${field} mb-3`}
          />

          <label className="mb-1 block text-xs font-semibold text-muted-foreground" htmlFor="pw">
            Password
          </label>
          <input
            id="pw"
            type="password"
            required
            minLength={mode === "signup" ? 8 : undefined}
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            className={field}
          />

          {err && <p className="mt-2 text-sm text-destructive">{err}</p>}

          <button
            disabled={busy}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-send py-2.5 font-bold text-send-foreground transition hover:brightness-95 disabled:opacity-50"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {mode === "signup"
              ? isInviteMode ? "Create account" : "Create admin account"
              : "Sign in"}
          </button>

          {mode === "signin" && (
            <p className="mt-4 text-center text-xs text-muted-foreground">
              Accounts are created by your admin via invite.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
