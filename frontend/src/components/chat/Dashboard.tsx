import { useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import type { Session } from "@supabase/supabase-js";
import { Login } from "./Login";
import { ChatList } from "./ChatList";
import { ChatView } from "./ChatView";
import { Settings } from "./Settings";

export function Dashboard() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [isAdmin, setIsAdmin] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    // Initial session check
    supabase.auth.getSession().then(({ data }) => setSession(data.session ?? null));

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      if (!s) { setIsAdmin(false); setSelected(null); }
    });
    return () => subscription.unsubscribe();
  }, []);

  // Check admin role whenever session changes
  useEffect(() => {
    if (!session) { setIsAdmin(false); return; }
    supabase
      .rpc("has_role", { _role: "admin", _user_id: session.user.id })
      .then(({ data }) => setIsAdmin(!!data));
  }, [session?.user?.id]);

  const handleLogout = () => supabase.auth.signOut();

  // Loading — still checking session
  if (session === undefined) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-brand">
        <MessagesSquare className="h-12 w-12 animate-pulse text-brand-foreground" />
      </div>
    );
  }

  if (!session) return <Login />;

  return (
    <>
      <div className="flex h-dvh flex-col overflow-hidden bg-background">
        <div className="mx-auto flex min-h-0 w-full max-w-[1600px] flex-1 md:shadow-xl">
          <aside
            className={`h-full w-full border-r border-border md:block md:w-[380px] md:shrink-0 lg:w-[420px] ${
              selected ? "hidden" : "block"
            }`}
          >
            <ChatList
              selected={selected}
              onSelect={setSelected}
              onLogout={handleLogout}
              isAdmin={isAdmin}
              members={[]}
              onTeam={() => {}}
              onSettings={() => setShowSettings(true)}
            />
          </aside>

          <main
            className={`h-full min-w-0 flex-1 ${
              selected ? "block animate-slide-in md:animate-none" : "hidden md:block"
            }`}
          >
            {selected ? (
              <ChatView
                key={selected}
                phone={selected}
                onBack={() => setSelected(null)}
                isAdmin={isAdmin}
                members={[]}
              />
            ) : (
              <div className="chat-wall flex h-full flex-col items-center justify-center gap-4 text-center text-muted-foreground">
                <div className="flex h-24 w-24 items-center justify-center rounded-full bg-card shadow">
                  <MessagesSquare className="h-12 w-12 text-primary" />
                </div>
                <h2 className="text-2xl font-bold text-foreground">Select a conversation</h2>
                <p className="max-w-xs text-sm">
                  Tap a chat on the left to view the history and reply.
                </p>
              </div>
            )}
          </main>
        </div>
      </div>

      <Settings open={showSettings} onClose={() => setShowSettings(false)} />
    </>
  );
}
