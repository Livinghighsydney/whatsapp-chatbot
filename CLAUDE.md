# Living High — WhatsApp Chatbot

## What this is

A standalone WhatsApp chatbot for **Living High** tenants (Sydney co-living operator, livinghigh.com.au). Built by **Alter Technologies** (Zunair, engineering; Haroon Sabir, CTO).

This is a **separate service** from the Living High internal Knowledge Base (KB). It is tenant-facing only — tenants send WhatsApp messages and the bot replies with information about their property.

This repo lives at `D:\Living High Chatbot` and is deployed as its own Railway service.

---

## Sister project: the Knowledge Base

The KB is the source of truth. It lives in a separate repo (`D:\Living High DB`):

- **Backend:** FastAPI, deployed on Railway
- **Frontend:** React + Vite, deployed on Vercel
- **Database:** PostgreSQL + pgvector on Railway
- **Auth:** JWT (HS256), bcrypt
- **Content:** Property handbooks (building pages), department pages, general pages

The chatbot does **not** share code or a database with the KB. It queries the KB's existing REST API to retrieve property handbook content.

---

## What the chatbot does

1. Tenant sends a WhatsApp message
2. Chatbot receives it via Twilio webhook
3. Chatbot calls the KB API to fetch relevant property handbook pages (RAG)
4. Chatbot calls Claude API with retrieved context + tenant question
5. Chatbot replies to the tenant on WhatsApp via Twilio

**RAG scope:** Only `type=building`, `visibility=general` pages from the KB — property handbooks only. No staff-only, team, or restricted pages are ever exposed.

---

## Tech stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| WhatsApp API | Twilio WhatsApp (sandbox for dev, real AU number for prod) |
| AI | Claude API (Anthropic) |
| KB data access | HTTP calls to the KB's REST API |
| Deployment | Railway (separate service from KB backend) |

---

## Twilio setup (already done)

- **Account SID:** (see .env)
- **Auth Token:** ROTATED — get fresh one from Twilio console (the original was accidentally shared in chat)
- **Sandbox number:** `+1 415 523 8886`
- **Sandbox join code:** `join selection-carbon`
- **Webhook URL:** not set yet — set this in Twilio Sandbox settings once Railway URL is known

To activate sandbox: send `join selection-carbon` from your WhatsApp to `+1 415 523 8886`.

---

## Project structure

```
chatbot/
├── main.py          # FastAPI app entry point
├── webhook.py       # POST /webhook/whatsapp — receives Twilio messages
├── whatsapp.py      # Twilio helper — sends WhatsApp replies
├── ai.py            # Claude API call
├── .env.example     # env vars template
├── requirements.txt # dependencies
└── CLAUDE.md        # this file
```

---

## Environment variables

```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=         # get fresh from Twilio console — old one was rotated
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
ANTHROPIC_API_KEY=
KB_API_BASE_URL=           # base URL of the KB Railway backend e.g. https://xxx.up.railway.app
KB_API_KEY=                # internal API key for chatbot→KB calls (to be added to KB backend)
```

---

## Build plan

### Phase 1 — Basic working bot (current focus)
- [ ] `main.py` — FastAPI app, single `/webhook/whatsapp` route
- [ ] `webhook.py` — parse Twilio POST, extract message + sender number
- [ ] `ai.py` — call Claude API with the raw message, return reply
- [ ] `whatsapp.py` — send reply back via Twilio
- [ ] Deploy to Railway, set webhook URL in Twilio sandbox settings
- [ ] End-to-end test: send a WhatsApp message, get a Claude reply

### Phase 2 — RAG against KB property handbooks
- [ ] Add a search endpoint to the KB backend (`GET /internal/search?q=...&type=building`) — internal only, behind an API key
- [ ] `rag.py` — call KB search API, retrieve top-N relevant handbook chunks
- [ ] Update `ai.py` — inject retrieved context into Claude prompt
- [ ] Optionally detect which property the tenant is asking about (match suburb/address)
- [ ] Test RAG accuracy against real handbook content

### Phase 3 — Tenant identity
- [ ] On first message, ask tenant for their name + property/suburb
- [ ] Store session (phone number → property mapping) so subsequent messages are scoped automatically
- [ ] Skip identity prompt once tenant has been identified

### Phase 4 — Production
- [ ] Buy an AU number through Twilio (~$2-3/month)
- [ ] Register it on WhatsApp Business via Twilio
- [ ] Point `chatbot.livinghigh.com.au` subdomain to Railway service
- [ ] Switch Twilio webhook from sandbox to the real number config
- [ ] Monitor via Twilio logs

---

## Working conventions

- Keep this service thin — it is a relay between Twilio, Claude, and the KB API
- No direct DB access ever — all KB data comes through the KB's REST API
- Only `visibility=general` pages from the KB are used in RAG — never expose staff/team/restricted content to tenants
- Log every incoming message and outgoing reply (at minimum to Railway logs, later to a DB table)
- Twilio webhook signature verification must be implemented before going to production
