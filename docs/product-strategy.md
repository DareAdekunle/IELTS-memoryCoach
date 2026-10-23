# BandUp IELTS — Product Strategy

Market, positioning and business model. For how the system works, see
[`README.md`](../README.md) and [`ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## Who it's for

About 3.5 million people take IELTS every year. Most are not full-time
students — they are **working professionals** in cities like Lagos, Nairobi,
Manila and Dhaka who need Band 6.5 or 7.0 to unlock a visa, a job offer, or a
university place in an English-speaking country.

They cannot attend classes. They study in stolen windows: a 20-minute commute,
a lunch break, the hour before midnight. We call them **jugglers**, and every
product decision is made for them.

## The problem

Existing prep tools reset between sessions. Learners get the same generic
feedback, the same rubric and the same advice every time; the tool has no
memory of what they struggled with last week, no sense of whether they are
improving, and no way to pick up where they left off.

## How BandUp is different

| Feature | BandUp | British Council | Magoosh | IELTS.org |
|---|---|---|---|---|
| Persistent memory across sessions | ✅ | ❌ | ❌ | ❌ |
| Granular skill rank engine | ✅ | ❌ | ❌ | ❌ |
| Specialist AI tutors per section | ✅ | ❌ | Partial | ❌ |
| Coaching in Telegram / WhatsApp | ✅ | ❌ | ❌ | ❌ |
| Study schedule + Google Calendar | ✅ | ❌ | ❌ | ❌ |
| All 4 IELTS skills | ✅ | ✅ | ✅ | ✅ |

### Compounding advantages

**1. A learner model that improves with use.** Every practice session writes
coaching memories — specific observations about this learner's error
patterns — weighted by confidence and recency. After 10 sessions BandUp knows
the learner far better than a generic AI coach, and switching away means
starting from scratch. That switching cost grows with every session.

**2. Designed for the 20-minute window.**
- No-repeat content selection: a short session is always a new challenge.
- Adaptive difficulty matched to the current band, so no session is wasted.
- Session continuity: a five-day gap doesn't mean starting over.
- Cross-section insights: spots when a grammar gap in Writing and a fluency
  gap in Speaking share a root cause.

**3. A research-backed pedagogy layer.** Each Tutor session follows a
structured teaching plan — 16 evidence-based frameworks, deterministic stage
routing, and support that fades only when evidence earns it — rather than a
chatbot with an IELTS system prompt.

**4. Semantic memory retrieval.** Memories are retrieved by relevance to what
is being taught today, not just recency, combining embeddings with
spaced-repetition scoring.

### The chat thread as the classroom

The end-state for the juggler is that the chat app they already have open all
day becomes their IELTS classroom: no app to download, no tab to open. They
send a paragraph on the way to work and the score arrives before they reach
the office; they record a voice note at lunch and get Speaking feedback by the
time they sit back down. The Telegram and WhatsApp coaches already handle
coaching questions, progress and schedule changes; the roadmap below
completes the loop with full practice sessions in-thread, writing to the same
learner profile as the web app.

---

## Productization roadmap

```
Phase 1 (current) — Solo practitioner web app
  ✅ All 4 IELTS skills with persistent AI memory
  ✅ Band estimates (4.0–8.5) per skill, updated after every session
  ✅ Adaptive content — difficulty matched to current band level
  ✅ Specialist AI tutors grounded in real practice evidence
  ✅ Cross-section insights — identifies core gaps across skills
  ✅ Handwritten essay upload
  ✅ Study scheduler — recurring sessions with Google Calendar integration
  ✅ Telegram + WhatsApp coaches with secure account linking
  ⬜ Hosting — the app currently runs locally (beta)

Phase 2 — Chat-native coaching (the juggler's phone IS the classroom)
  ⬜ Full practice sessions in Telegram/WhatsApp:
       → send a paragraph → scored → feedback arrives in thread
       → record a voice note → transcribed → Speaking feedback inline
       → comprehension questions → Reading drills in chat
       → audio clip → Listening answers checked, memories saved
  ⬜ Push nudges: "You haven't practised Writing in 3 days — here's a
     quick paragraph task for your commute"
  ⬜ Streak tracking and milestone celebrations in thread
  ⬜ WhatsApp Business verification and go-live

Phase 3 — Mobile-first consumer product
  ⬜ React Native app (same FastAPI backend)
  ⬜ Offline mode — download practice content, sync results later
  ⬜ Voice selection for TTS — practise with the examiner accent
     (British, American, Australian) of the real test

Phase 4 — Freemium at scale
  ⬜ Free tier: 5 sessions/month, memory limited to last 3 sessions
  ⬜ Premium: unlimited sessions, full persistent memory, all 4 sections,
     complete band history
  ⬜ Multi-region hosting
  ⬜ Payments via Stripe (card) + regional methods (M-Pesa, GCash, UPI)

Phase 5 — Community and accountability
  ⬜ Anonymous band leaderboards by target score and country
  ⬜ Study groups — 2–3 learners hold each other accountable
  ⬜ Milestone sharing — "I just hit Band 6.5 on Writing"
  ⬜ Referral programme — one free month per friend who reaches their target

Phase 6 — Platform
  ⬜ Coaching data API — licensed tutors query a learner's coaching
     profile (with consent) and pick up where the app left off
  ⬜ Community-validated taxonomy; open-source core, hosted service
  ⬜ Webhooks when a learner hits their target band
```

## Business model

Freemium, direct to consumer. The free tier drives acquisition across emerging
markets; Premium converts motivated learners — someone paying around $250 for
an IELTS test fee will pay a small monthly fee for a coach that remembers
them. A coaching-data API for third-party tutoring platforms adds a B2B layer
without institutional sales cycles.

**Unit economics.** Measured AI cost is roughly $0.80–1.20 per active learner
per month (see `scripts/cost_model.py`; e.g. ~$0.013 per scored essay, ~$0.036
per Speaking test). Premium pricing should keep AI cost well under 10% of
revenue.
