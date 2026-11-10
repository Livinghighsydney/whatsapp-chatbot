import { useState } from "react";
import { Loader2, Building2 } from "lucide-react";
import { verifyToken } from "@/lib/api";

export function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [token, setToken] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await verifyToken(token.trim());
      onLogin(token.trim());
    } catch {
      setErr("Invalid access token — check with your admin.");
    } finally {
      setBusy(false);
    }
  };

  const field =
    "w-full rounded-lg border border-input bg-background px-3 py-2.5 outline-none focus:ring-2 focus:ring-ring";

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
            <p className="text-sm text-muted-foreground">Staff sign in</p>
          </div>

          <label className="mb-1 block text-xs font-semibold text-muted-foreground" htmlFor="tok">
            Access token
          </label>
          <input
            id="tok"
            type="password"
            required
            autoFocus
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Paste your access token"
            className={field}
          />

          {err && <p className="mt-2 text-sm text-destructive">{err}</p>}

          <button
            disabled={busy || !token.trim()}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-send py-2.5 font-bold text-send-foreground transition hover:brightness-95 disabled:opacity-50"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            Sign in
          </button>

          <p className="mt-4 text-center text-xs text-muted-foreground">
            Your token is set by your admin in Railway.
          </p>
        </form>
      </div>
    </div>
  );
}
