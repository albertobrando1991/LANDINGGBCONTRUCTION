# PRD — GB Construction Lead Engine

## Problem statement (sintesi)
Sistema completo di acquisizione e gestione lead per GB Construction S.R.L. (ristrutturazioni, Napoli e Campania), con due interfacce collegate da un unico DB:
1. Landing pubblica immersiva (configuratore + motore predittivo) per acquisire e qualificare lead.
2. Dashboard staff per gestire e convertire i lead in cantieri.
Stack richiesto Next.js+Supabase → adattato a **React + FastAPI + MongoDB** (UI/UX e logica identiche).

## User choices
- Entrambe le interfacce (landing + dashboard)
- AI via Emergent LLM Key (modello gpt-4o)
- Email/WhatsApp/Calendario/PDF/render → placeholder/mock
- Auth JWT email+password (ruoli admin/staff/operations)
- Dataset completo 86 voci

## Architettura
- Backend: FastAPI, MongoDB (motor). Moduli: `server.py`, `auth.py` (JWT cookie httpOnly + bcrypt + seed),
  `predictive_engine.py` (algoritmo 7 fasi), `predictive_data.py` (86 voci + 18 coefficienti),
  `ai_service.py` (gpt-4o), `seed_data.py` (12 lead + 3 cantieri demo).
- Frontend: React + Tailwind (design system GB: Onyx/Construction Red/Gold, Oswald+Montserrat),
  framer-motion, recharts, embla, react-hook-form+zod, shadcn/ui. Routing: `/` landing, `/login`, `/dashboard/*`.

## Implementato (2026-05-30)
- Landing: loading screen, hero video, riprova sociale (carousel before/after + testimonianze),
  configuratore 7-step, gate contatti (calcolo animato + form validato), output 3 pacchetti, seconda chance (progetti+FAQ+callback), footer marquee.
- Motore predittivo: Essenziale/Premium/Luxury con range €/mq, dettaglio computo per categoria, alert tecnici, lead scoring 1-100.
- Dashboard: Oggi, Lead Inbox (filtri+ricerca+tabella), Scheda Lead (3 colonne, timeline, cambio stato, note, **AI suggerisci azione**),
  Pipeline Kanban drag&drop, Sopralluoghi, Preventivi, Cantieri, Report (KPI+grafici+**AI insight**), Impostazioni (staff/coefficienti/86 voci).
- Auth JWT con seed admin/staff/operations. Testing: backend 31/31, frontend tutti i flussi OK.

## Mocked / non implementato
- Email, WhatsApp, Cal.com, generazione PDF preventivo, render visivo AI, trascrizione note vocali → solo UI placeholder.

## Backlog (P1/P2)
- P1: Integrazione reale Email (Resend) + WhatsApp + Cal.com per CTA sopralluogo.
- P1: Editor preventivo con export PDF e tracking apertura.
- P2: Upload file lead reale (storage) + sequenze follow-up automatiche configurabili.
- P2: Render concettuale via AI image generation; trascrizione note vocali (whisper).
- P2: Mappa Campania interattiva nel Report; 2FA opzionale.
