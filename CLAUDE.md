# Living High — WhatsApp Chatbot + Staff Dashboard

## What this is

A standalone WhatsApp chatbot for **Living High** tenants (Sydney co-living operator, livinghigh.com.au). Built by **Alter Technologies** (Zunair, engineering; Haroon Sabir, CTO).

Tenant-facing only — tenants send WhatsApp messages to the AU business number and the bot replies using Claude AI. This is a **separate service** from the Living High internal Knowledge Base (KB).

This repo lives at `D:\Living High Chatbot` and is deployed as two Railway services (backend + frontend dashboard).

GitHub: https://github.com/Livinghighsydney/whatsapp-chatbot

---

## Sister project: the Knowledge Base

The KB is the source of truth. It lives in a separate repo (`D:\Living High DB`):

- **Backend:** FastAPI, deployed on Railway
- **Frontend:** React + Vite, deployed on Vercel
- **Database:** PostgreSQL + pgvector on Railway
- **Auth:** JWT (HS256), bcrypt
- **Content:** Property handbooks (building pages), department pages, general pages

The chatbot does **not** share code or a database with the KB. It will query the KB's existing REST API to retrieve property handbook content (Phase 2 — not yet built).

---

## Current status (as of November 2026)

**What is working:**
- Bot deployed on Railway: `https://web-production-9e95d.up.railway.app`
- Staff dashboard deployed on Railway: `https://staff-dashboard-production-9c44bf78.up.railway.app`
- Real AU WhatsApp number: **+61 450 879 134** (physical prepaid SIM)
- End-to-end flow: tenant messages → webhook → Claude → reply via WhatsApp ✅
- Meta app **published** (Live mode) ✅ — any tenant can now message the bot
- App Review approved ✅
- Tech Provider / Access Verification submitted ✅
- 60-day access token set in Railway ✅ (expires ~January 2027)
- Staff dashboard with JWT auth, full conversation history ✅
- Dual handoff system (Dashboard mode + WhatsApp mode) ✅
- Proactive tenant identity collection (name, property, room) ✅
- Shift-based routing (AEST timezone, overlap rule, 7-day fallback) ✅
- Real-time dashboard updates via SSE ✅
- Unread message count badges ✅
- Notification sound + desktop notifications ✅
- Auto-handoff when staff intervenes from dashboard ✅

**What is NOT yet built:**
- Phase 2: RAG against KB property handbooks
- Phase 5: Webhook signature verification (security hardening)

---

## Tech stack

| Layer | Choice |
|---|---|
| Bot framework | FastAPI |
| WhatsApp API | Meta WhatsApp Cloud API (direct, NOT Twilio) |
| AI | Claude Haiku (`claude-haiku-4-5-20251001`) |
| Database | Neon PostgreSQL (psycopg2-binary, connection pool) |
| Auth | JWT HS256 (python-jose), bcrypt |
| Email | Resend.io (staff invite emails) |
| Real-time | Server-Sent Events (SSE) |
| Dashboard frontend | TanStack Start (SSR), React, TanStack Query, shadcn/ui, Tailwind |
| Frontend deployment | Railway (Docker, node:24-alpine) |
| Backend deployment | Railway (Hobby plan, always-on) |
| Timezone | `zoneinfo.ZoneInfo("Australia/Sydney")` + `tzdata` package |

**Note:** Twilio was abandoned early due to AU number provisioning restrictions. All WhatsApp is now via Meta Cloud API directly.

---

## Meta WhatsApp setup

- **WhatsApp number:** +61 450 879 134 (physical AU prepaid SIM)
- **Phone Number ID:** `1312713438600035`
- **WABA ID:** `28190264097319654` (Living High's real WhatsApp Business Account)
- **Meta App name:** WA_bot
- **Meta App ID:** `4064757233818198`
- **Meta App Secret:** in `.env` as `APP_SECRET` (used to generate long-lived tokens)
- **Verify token:** `livinghigh2024`
- **Webhook URL (Railway):** `https://web-production-9e95d.up.railway.app/webhook/whatsapp`
- **App status:** Published (Live mode) ✅

**IMPORTANT — two WABAs exist:**
- WABA `3519420761569977` → test number only (+1 555-670-4313) — do NOT use this
- WABA `28190264097319654` → real AU number (+61 450 879 134) — this is the correct one

**Access token management:**
- Current token type: 60-day long-lived user token (expires ~January 2027)
- To regenerate: get short-lived token from Meta Developer Console → WA_bot → WhatsApp → API Setup → Generate access token, then exchange it:
```bash
curl "https://graph.facebook.com/v25.0/oauth/access_token?grant_type=fb_exchange_token&client_id=4064757233818198&client_secret=<APP_SECRET>&fb_exchange_token=<SHORT_LIVED_TOKEN>"
```
- Permanent fix (pending): Sophia (sophialivingh@gmail.com) needs to approve a System User token request in Meta Business Manager. Once approved, generate a never-expiring token from the GHL connector system user.

---

## Project structure

```
D:\Living High Chatbot\
├── app/
│   ├── main.py              # FastAPI entry, lifespan runs DB migrations, CORS, routers
│   ├── webhook.py           # GET/POST /webhook/whatsapp — message processing + SSE push
│   ├── whatsapp.py          # Send messages/templates/media via Meta Graph API v19.0
│   ├── ai.py                # Claude API — get_reply() with tenant context, is_handoff()
│   ├── structured.py        # Claude tool_use — extract_tenant_info() from free text
│   ├── handoff.py           # Dual-mode handoff orchestration (dashboard + WhatsApp)
│   ├── shifts.py            # Shift CRUD + AEST routing_target() with overlap rule
│   ├── db.py                # Neon connection pool (psycopg2 SimpleConnectionPool)
│   ├── db_conversations.py  # All conversation/message DB helpers, unread counts, mark_read
│   ├── migrate.py           # Idempotent startup migrations (CREATE IF NOT EXISTS + ALTER)
│   ├── auth.py              # JWT create/decode, bcrypt, user CRUD
│   ├── staff_api.py         # All /staff/* endpoints — auth, users, shifts, chats, SSE
│   ├── sse.py               # SSE pub/sub (asyncio.Queue per client, push/stream)
│   ├── email.py             # Resend.io invite email helper
│   └── state.py             # Legacy in-memory state (superseded by db_conversations.py)
├── frontend/
│   ├── Dockerfile           # Multi-stage Docker build (node:24-alpine), serves Nitro output
│   ├── railway.toml         # builder = "dockerfile"
│   ├── src/
│   │   ├── components/chat/
│   │   │   ├── Dashboard.tsx   # Root: auth check, members query, layout
│   │   │   ├── Login.tsx       # Sign in / sign up / invite flow (reads role from URL)
│   │   │   ├── ChatList.tsx    # Left sidebar with unread badges, colour avatars, SSE
│   │   │   ├── ChatView.tsx    # Open conversation — messages, send, resolve, assign
│   │   │   ├── Settings.tsx    # Modal: handoff toggle, Team tab, Shifts tab
│   │   │   └── StatusBadge.tsx # Coloured pill for bot_active / handed_off / etc.
│   │   └── lib/
│   │       ├── api.ts          # All API calls + types (ChatSummary, Member, Shift, etc.)
│   │       └── notify.ts       # Web Audio ping + desktop notification helpers
├── requirements.txt
├── Procfile                 # web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
├── .env                     # local env vars (never commit)
└── CLAUDE.md                # this file
```

---

## Database schema (Neon PostgreSQL)

Five tables — migrations run automatically on every startup via `app/migrate.py`:

```sql
staff_users     — id, email, name, password_hash, role, whatsapp_number, created_at
settings        — key (PK), value  [handoff_mode, session_counter]
shifts          — id, staff_user_id (FK), weekday (0=Mon), start_time, end_time
conversations   — id, tenant_phone (UNIQUE), tenant_name, property_address, room,
                  status, assigned_staff_id (FK), session_id, handoff_reason,
                  info_collected, last_read_at, created_at, updated_at
messages        — id, conversation_id (FK), role, content, created_at
```

**Conversation statuses:** `bot_active` | `collecting_info` | `handed_off` | `resolved`

---

## Environment variables

### Required in Railway Variables (backend service):

```
ANTHROPIC_API_KEY=          # from console.anthropic.com → API Keys
META_ACCESS_TOKEN=          # 60-day token (see token management above)
META_PHONE_NUMBER_ID=1312713438600035
META_WABA_ID=28190264097319654
META_VERIFY_TOKEN=livinghigh2024
DATABASE_URL=               # Neon PostgreSQL connection string
JWT_SECRET=                 # random secret for signing JWT tokens
RESEND_API_KEY=             # from resend.com
DASHBOARD_URL=https://staff-dashboard-production-9c44bf78.up.railway.app
```

### Required in Railway Variables (frontend service):
```
VITE_API_BASE_URL=https://web-production-9e95d.up.railway.app
```

### In local .env only (never commit, never put in Railway):
```
APP_SECRET=                 # Meta app secret — only needed to generate long-lived tokens
```

### Optional (WhatsApp mode fallback):
```
STAFF_NUMBERS=923219905434  # comma-separated WA numbers without + (legacy fallback)
```

### Not yet needed (Phase 2):
```
KB_API_BASE_URL=            # base URL of KB Railway backend
KB_API_KEY=                 # internal API key for chatbot→KB calls
```

---

## How it works (current flow)

### Tenant message flow
1. Tenant sends WhatsApp message to +61 450 879 134
2. Meta sends POST to `/webhook/whatsapp` — returns 200 immediately, processes in background
3. **First-ever message:** bot sends info prompt asking for name/property/room
4. **Collecting info:** Claude `tool_use` extracts name/property/room, stores in DB
5. **Bot active:** Claude replies with tenant identity injected into system prompt
6. **Handoff detected** (or staff intervenes): conversation set to `handed_off`, assigned to on-shift agent
7. **During handoff:** bot completely silent — only staff can reply
8. **Resolve:** staff clicks Resolve → status back to `bot_active`, bot resumes

### Handoff routing
- Reads on-shift agent via `shifts.routing_target()` — AEST timezone, Monday=0
- **Overlap rule:** if two shifts overlap, most recently started wins
- **No one on shift:** falls back to whoever's shift starts soonest (up to 7 days ahead)
- **Dashboard mode:** assigns in DB, staff sees it in dashboard, replies via UI → sent as bot's WA number
- **WhatsApp mode:** sends template alert to agent's personal WA number; agent replies directly

### Real-time updates (SSE)
- Backend `app/sse.py` maintains an `asyncio.Queue` per connected dashboard tab
- `sse.push("message")` — new tenant message → triggers notification sound in dashboard
- `sse.push("refresh")` — bot reply / staff send → silent UI update
- Frontend subscribes via `EventSource` on `/staff/events?token=...` (JWT via query param since EventSource doesn't support headers)
- TanStack Query `invalidateQueries` on SSE event — no page reload, React re-renders in place

### Staff dashboard
- Login at `https://staff-dashboard-production-9c44bf78.up.railway.app`
- Super admin: `zunair@livinghigh.com.au` / `12345678`
- Roles: `admin` (full access) | `agent` (own assigned chats only)
- Invite URL encodes role: `?invite=1&email=...&role=admin`
- First user to sign up always becomes admin regardless of URL param

---

## Staff dashboard features

### Chat list
- Real-time via SSE — new chats/messages appear instantly without refresh
- **Unread badges:** count of unread tenant messages, bold name + preview, green timestamp
- **Colour avatars:** deterministic hash of phone number → one of 12 distinct colours (consistent per tenant)
- Phone number shown on each row; property/room shown when available
- Pull-to-refresh on mobile

### Chat view
- Full message history (tenant / bot / staff bubbles)
- Staff can send text or media (images, video, audio, documents)
- Assign conversation to any team member
- Resolve handoff → bot resumes
- Delete conversation (soft reset)

### Settings modal (admin only)
- **Handoff mode toggle:** Dashboard ↔ WhatsApp
- **Team tab:** member list with roles + WA numbers; invite form (email, name, role, WA number)
- **Shifts tab:** add/delete shifts per member per weekday (AEST times); overlap rule explained

---

## Build plan

### Phase 1 — Basic working bot ✅ COMPLETE
### Phase 2 — Staff dashboard ✅ COMPLETE (was Phase 4)
- JWT auth, role-based access (admin/agent)
- DB-backed conversations (Neon PostgreSQL)
- Dual handoff: Dashboard mode + WhatsApp mode
- Shift management with AEST routing
- Proactive tenant identity collection via Claude structured output
- Real-time SSE, unread counts, notification sounds
- Colour avatars, phone/property in chat bar

### Phase 3 — RAG against KB property handbooks
- Add `GET /internal/search?q=...&type=building` to KB backend (internal, behind API key)
- Create `app/rag.py` — calls KB search API, retrieves top-N handbook chunks
- Update `ai.py` — inject retrieved context into Claude system prompt
- Scope answers to the tenant's specific property (uses name/property already in DB)

### Phase 4 — Webhook signature verification
- Verify `X-Hub-Signature-256` header on all incoming Meta webhooks
- Prevents spoofed webhook requests

---

## Working conventions

- Keep backend thin — relay between Meta, Claude, and the KB API
- No direct KB DB access — all KB data comes through the KB's REST API
- Only `visibility=general` pages from the KB used in RAG — never expose staff/team/restricted content
- Log every incoming message and outgoing reply (Railway logs)
- Background tasks for all Claude+Meta calls to avoid webhook timeouts
- Never commit `.env` — all secrets in Railway Variables
- Git commits go to Zunair (no co-author lines)
- Monday=0 (ISO weekday convention throughout)

---

## Deployment

### Backend (chatbot + API)
**Railway service:** `web-production-9e95d.up.railway.app`
**Start command (Procfile):** `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
**Deploy:** Push to `master` branch on GitHub → Railway auto-deploys

### Frontend (staff dashboard)
**Railway service:** `staff-dashboard-production-9c44bf78.up.railway.app`
**Build:** Docker (node:24-alpine), `frontend/Dockerfile`, `frontend/railway.toml`
**Root directory in Railway:** `frontend`

**After any Railway redeploy:** Re-subscribe WABA to app webhook if messages stop arriving:
```bash
curl -X POST "https://graph.facebook.com/v25.0/28190264097319654/subscribed_apps" \
  -H "Authorization: Bearer <META_ACCESS_TOKEN>"
```

---

## Known issues and solutions

| Issue | Cause | Fix |
|---|---|---|
| Bot stops receiving messages after redeploy | WABA subscription drops | Re-run the subscribed_apps curl above |
| Meta access token 401 | Token expired (~January 2027) | Regenerate 60-day token (see token management section) |
| Anthropic 401 invalid x-api-key | Wrong key type or expired | Generate fresh key from console.anthropic.com → API Keys |
| Webhook not receiving messages | WABA not subscribed to correct app | Re-run subscribed_apps curl |
| Two WABAs confusion | Test WABA vs real WABA | Always use WABA `28190264097319654` for production |
| Frontend build fails on Railway | Node version / builder mismatch | Uses Docker (node:24-alpine) — check Dockerfile and railway.toml |
| SSE disconnects | Normal browser behaviour | EventSource auto-reconnects; 15s polling acts as fallback |
| Bot replies during handoff | Old behaviour (fixed) | webhook.py returns early when status=handed_off |

---

## If Meta App Review gets rejected in future

Best fallback options (in order of preference):
1. **Zernio** (~$3/month) — new AU number, KYC required, 1-3 days
2. **360dialog** (€49/month) — can port existing +61 450 879 134 number
