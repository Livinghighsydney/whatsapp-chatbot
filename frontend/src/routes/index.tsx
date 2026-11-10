import { createFileRoute } from "@tanstack/react-router";
import { ClientOnly } from "@tanstack/react-router";
import { Dashboard } from "@/components/chat/Dashboard";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Living High Staff — Tenant Chats" },
      { name: "description", content: "Manage escalated WhatsApp tenant conversations for Living High co-living." },
      { property: "og:title", content: "Living High Staff — Tenant Chats" },
      { property: "og:description", content: "Manage escalated WhatsApp tenant conversations for Living High co-living." },
    ],
  }),
  component: () => <ClientOnly fallback={<div className="min-h-dvh bg-brand" />}><Dashboard /></ClientOnly>,
});
