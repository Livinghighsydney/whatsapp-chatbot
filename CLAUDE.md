# Living High — WhatsApp Chatbot

## What this is

A standalone WhatsApp chatbot for **Living High** tenants (Sydney co-living operator, livinghigh.com.au). Built by **Alter Technologies** (Zunair, engineering; Haroon Sabir, CTO).

Tenant-facing only — tenants send WhatsApp messages to the AU business number and the bot replies using Claude AI. This is a **separate service** from the Living High internal Knowledge Base (KB).

This repo lives at `D:\Living High Chatbot` and is deployed as its own Railway service.

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
- Real AU WhatsApp number: **+61 450 879 134** (physical prepaid SIM)
- End-to-end flow: tenant messages → webhook → Claude → reply via WhatsApp ✅
- Meta app **published** (Live mode) ✅ — any tenant can now message the bot
- App Review approved ✅
- Tech Provider / Access Verification submitted ✅
- 60-day access token set in Railway ✅ (expires ~January 2027)

**What is NOT yet built:**
- Phase 2: RAG against KB property handbooks
- Phase 3: Tenant identity via Google Sheets
- Phase 4: Human handoff dashboard
- Webhook signature verification (security hardening)

---

## Tech stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| WhatsApp API | Meta WhatsApp Cloud API (direct, NOT Twilio) |
| AI | Claude API (Anthropic) — model: `claude-haiku-4-5-20251001` |
| KB data access | HTTP calls to KB REST API (Phase 2, not yet built) |
| Deployment | Railway (Hobby plan, always-on) |

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
│   ├── main.py        # FastAPI entry point, loads .env, registers router, root + health routes
│   ├── webhook.py     # GET /webhook/whatsapp (Meta verification) + POST (incoming messages)
│   ├── whatsapp.py    # Sends replies via Meta Graph API v19.0
│   └── ai.py          # Claude API call with system prompt
├── requirements.txt
├── Procfile           # web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
├── .env               # local env vars (never commit)
└── CLAUDE.md          # this file
```

---

## Environment variables

### Required in Railway Variables (and local .env):

```
ANTHROPIC_API_KEY=          # from console.anthropic.com → API Keys
META_ACCESS_TOKEN=          # 60-day token (see token management above)
META_PHONE_NUMBER_ID=1312713438600035
META_WABA_ID=28190264097319654
META_VERIFY_TOKEN=livinghigh2024
```

### In local .env only (never commit, never put in Railway):
```
APP_SECRET=                 # Meta app secret — only needed to generate long-lived tokens
```

### Human handoff:
```
STAFF_NUMBERS=923219905434  # comma-separated WhatsApp numbers (without +) for staff relay
```

### Not yet needed (Phase 2):
```
KB_API_BASE_URL=            # base URL of KB Railway backend
KB_API_KEY=                 # internal API key for chatbot→KB calls
```

### Legacy (Twilio — no longer used):
```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

---

## How it works (current flow)

1. Tenant sends WhatsApp message to +61 450 879 134
2. Meta sends POST to `https://web-production-9e95d.up.railway.app/webhook/whatsapp`
3. `webhook.py` extracts sender number + message body, queues background task
4. `ai.py` calls Claude API with the message
5. `whatsapp.py` sends Claude's reply back via Meta Graph API v19.0

Background tasks are used to return 200 to Meta immediately (avoids webhook timeout).

---

## Build plan

### Phase 1 — Basic working bot ✅ COMPLETE
- FastAPI app deployed on Railway
- Meta WhatsApp Cloud API integrated
- Claude API integrated
- End-to-end: tenant messages → bot replies
- Real AU number (+61 450 879 134) registered, app published to Live mode

### Phase 2 — RAG against KB property handbooks
- Add `GET /internal/search?q=...&type=building` to KB backend (internal, behind API key)
- Create `app/rag.py` — calls KB search API, retrieves top-N handbook chunks
- Update `ai.py` — inject retrieved context into Claude system prompt
- Scope answers to the tenant's specific property (requires Phase 3 first)

### Phase 3 — Tenant identity via Google Sheets
- Tenant list maintained in a Google Sheet: columns = phone number, name, property/suburb, room
- On first message from an unknown number: ask for name, look up in sheet
- Once identified: scope all answers to their property
- Store session state (phone → identity mapping) in memory or Redis

### Phase 4 — Human handoff dashboard
- Custom internal web UI (React) where staff can see flagged conversations
- Bot detects it can't answer → flags conversation as "needs human", pauses itself for that tenant
- Staff see the conversation in the dashboard, reply from there
- Reply is sent to the tenant's WhatsApp thread via the same +61 450 879 134 number
- Staff mark conversation "resolved" → bot resumes for that tenant
- Backend: extend FastAPI app with conversation storage (PostgreSQL on Railway)
- Frontend: React dashboard, login protected, deployed separately
- Real-time: WebSockets or polling

### Phase 5 — Webhook signature verification
- Verify `X-Hub-Signature-256` header on all incoming Meta webhooks
- Prevents spoofed webhook requests

---

## Working conventions

- Keep this service thin — relay between Meta, Claude, and the KB API
- No direct DB access ever — all KB data comes through the KB's REST API
- Only `visibility=general` pages from the KB used in RAG — never expose staff/team/restricted content
- Log every incoming message and outgoing reply (currently to Railway logs)
- Background tasks for all Claude+Meta calls to avoid webhook timeouts
- Never commit `.env` — all secrets in Railway Variables

---

## Deployment

**Railway service:** `web-production-9e95d.up.railway.app`
**Start command (Procfile):** `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
**Deploy:** Push to `master` branch on GitHub → Railway auto-deploys

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
| Meta access token 401 | Token expired | Regenerate 60-day token (see token management section) |
| Anthropic 401 invalid x-api-key | Wrong key type or expired | Generate fresh key from console.anthropic.com → API Keys |
| Webhook not receiving messages | WABA not subscribed to correct app | Re-run subscribed_apps curl |
| Two WABAs confusion | Test WABA vs real WABA | Always use WABA `28190264097319654` for production |
| Meta publish blocked — broken link | Root URL returned 404 | Fixed: added root route `/` to main.py returning 200 |

---

## If Meta App Review gets rejected in future

Best fallback options (in order of preference):
1. **Zernio** (~$3/month) — new AU number, KYC required, 1-3 days
2. **360dialog** (€49/month) — can port existing +61 450 879 134 number
