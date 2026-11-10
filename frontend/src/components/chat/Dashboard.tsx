import { useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { getToken, clearToken } from "@/lib/api";
import { Login } from "./Login";
import { ChatList } from "./ChatList";
import { ChatView } from "./ChatView";

export function Dashboard() {
  // undefined = still checking localStorage, null = no token, string = authenticated
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setToken(getToken() ?? null);
  }, []);

  const handleLogout = () => {
    clearToken();
    setToken(null);
    setSelected(null);
  };

  const handleLogin = (t: string) => {
    setToken(t);
  };

  // Still reading localStorage
  if (token === undefined) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-brand">
        <MessagesSquare className="h-12 w-12 animate-pulse text-brand-foreground" />
      </div>
    );
  }

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  return (
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
            isAdmin={false}
            members={[]}
            onTeam={() => {}}
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
              isAdmin={false}
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
  );
}
