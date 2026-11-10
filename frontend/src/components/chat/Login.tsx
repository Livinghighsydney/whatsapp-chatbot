import { useEffect, useState } from "react";
import { Loader2, Building2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";

export function Login() {
  const params = new URLSearchParams(window.location.search);
  // If the URL contains ?invite=1 (from an invite email), go straight to signup
  const isInviteMode = params.get("invite") === "1";
  const inviteEmail = params.get("email") ?? "";

  const [setup, setSetup] = useState<boolean | null>(isInviteMode ? true : null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState(inviteEmail);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Skip admin_exists check when arriving from an invite link
    if (!isInviteMode) {
      supabase.rpc("admin_exists").then(({ data }) => setSetup(data === false));
    }
  }, [isInviteMode]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    setInfo("");
    if (setup) {
      const { data, error } = await supabase.auth.signUp({
        email,
        password: pw,
        options: {
          emailRedirectTo: window.location.origin,
          data: { full_name: name },
        },
      });
      if (error) setErr(error.message);
      else if (!data.session) setInfo("Check your email to confirm your account, then sign in.");
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password: pw });
      if (error)
        setErr(error.message === "Invalid login credentials" ? "Wrong email or password" : error.message);
    }
    setBusy(false);
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
            <p className="text-sm text-muted-foreground">
              {setup
                ? isInviteMode
                  ? "Create your account"
                  : "Create the first admin account"
                : "Team sign in"}
            </p>
          </div>

          {setup && (
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
            minLength={setup ? 8 : undefined}
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            className={field}
          />

          {err && <p className="mt-2 text-sm text-destructive">{err}</p>}
          {info && <p className="mt-2 text-sm text-primary">{info}</p>}

          <button
            disabled={busy || setup === null}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-send py-2.5 font-bold text-send-foreground transition hover:brightness-95 disabled:opacity-50"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {setup ? (isInviteMode ? "Create account" : "Create admin account") : "Sign in"}
          </button>

          {!setup && setup !== null && (
            <p className="mt-4 text-center text-xs text-muted-foreground">
              Accounts are created by your admin.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
