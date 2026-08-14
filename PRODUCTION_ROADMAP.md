# BDO Call Analysis Platform — Audit, Cost Model & Production Roadmap

**Date:** 2026-08-13
**Branch reviewed:** `feature/proper-report-view` @ `6ad72f0`
**Constraint set by owner:** running budget ≈ **₹0**. Accuracy first, then completeness of analysis, then reports.

---

## 1. What exists today

### 1.1 Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 async, Alembic, Postgres |
| Frontend | Next.js 16 (App Router), React 19, Tailwind 4, TanStack Query |
| STT | Groq `whisper-large-v3-turbo` |
| LLM | Mistral `ministral-3b-2512` via OpenAI-compatible client |
| Audio storage | MinIO (self-hosted S3) |
| Auth | JWT in httpOnly cookie, PBKDF2-SHA256, multi-tenant by `organization_id` |
| Rate limiting | slowapi (in-process) |

~125 tracked files; backend services ≈ 2,000 LOC, frontend ≈ 8,800 LOC.

### 1.2 Current pipeline

```
POST /transcripts/upload-audio   (synchronous, inside the HTTP request)
  │
  ├─ 1. validate extension + content-type, read ≤25 MB into memory
  ├─ 2. Groq Whisper turbo  → verbose_json  → keeps ONLY .text, .language, .duration
  ├─ 3. regex language sniff (Devanagari/Tamil/Telugu/Bengali/Gujarati/Arabic + keyword lists)
  ├─ 4. LLM call #1 — "diarization": ministral-3b re-emits the ENTIRE transcript with
  │                    "Agent:" / "Customer:" prefixes
  ├─ 5. upload audio to MinIO (AFTER transcription; failure only logged)
  ├─ 6. INSERT transcript row
  ├─ 7. write 2 rows to llm_cost_logs
  └─ 8. if auto_analyze: trigger_analysis(...)
            └─ asyncio.create_task(run_async_analysis_job)
                  └─ template params split into batches of 15
                     → N parallel LLM calls, EACH resending the full transcript
                     → dynamic Pydantic model per batch, one correction retry on
                       ValidationError
                     → weighted score, ParameterResult + SectionResult rows
```

### 1.3 Data model

- `organizations` → `users` (roles: `admin` / `evaluator` / `viewer`)
- `evaluation_templates` → `evaluation_parameters` (weight, min/max score, `ai_instructions`) + `extraction_sections`
  - partial unique index enforces one active template per org — good
- `transcripts` (raw_text, `speaker_segments` JSON, audio key, detected_language, duration)
- `analysis_runs` → `parameter_results` (score/reason/evidence/suggestion/confidence) + `section_results`
  - snapshots parameter name + instructions at run time — good, gives immutable history
- `evaluator_assignments` / `transcript_assignments` — row-level visibility
- `llm_cost_logs` — per-call token + USD accounting with a hardcoded price matrix

### 1.4 What's genuinely good

These are real strengths worth preserving:

1. **Template versioning with snapshots.** `parameter_results.name_snapshot` / `ai_instructions_snapshot` means historical reports stay meaningful after a template edit. Most teams get this wrong.
2. **Cost logging exists at all.** `llm_cost_logs` with per-action attribution is unusual in an early-stage project and is exactly the instrumentation needed for the cost work below.
3. **Multi-tenancy is consistent.** Every repository method takes `organization_id`; I did not find a query that leaks across tenants.
4. **The partial unique index** `uq_one_active_template_per_org` — correctly prevents the `MultipleResultsFound` race.
5. **Optional parameter fields in the dynamic Pydantic model** — a small model omitting one parameter no longer discards the other 58. Well-reasoned, and the comment explains why.
6. **The 59-parameter BPO QA preset** is a real domain asset. That took work and it's the thing a client actually buys.

---

## 2. Cost reality check

### 2.1 Reference call

**5 minutes (300 s), 2 speakers, Hinglish, ~750 spoken words.**

Token estimate: Devanagari tokenizes at ~2.5–3 tokens/word on standard BPE; Latin-script Hinglish ~1.8. Mixed ≈ **2.2 tokens/word** → transcript ≈ **1,650 tokens**, ≈1,850 with speaker labels. *(This is the single biggest driver of Indic LLM cost and is routinely underestimated — English-only estimates run ~1.3 tok/word.)*

FX assumption: **₹95.3 / USD** (2026-08-13). The rupee moved ~9% over the preceding 12 months, which is larger than several of the cost differences compared below - so treat rupee figures as a snapshot, not a constant. The app reads this from `USD_TO_INR_RATE`.

### 2.2 Verified provider rates (Aug 2026)

| Service | Rate | Confidence |
|---|---|---|
| Groq `whisper-large-v3-turbo` | $0.040 / audio-hour | verified |
| Groq `whisper-large-v3` | $0.111 / audio-hour | verified |
| Groq `llama-3.1-8b-instant` | $0.05 in / $0.08 out per 1M tok | verified |
| Groq `gpt-oss-20b` | $0.075 in / $0.30 out per 1M tok | verified |
| Mistral `ministral-3b` | $0.10 in / $0.10 out per 1M tok | as configured in repo |
| Groq Batch API | −50% | verified |
| Groq prompt caching | −50% on input | verified |

Groq bills **a 10-second minimum per request**, which matters for short clips.

### 2.3 Path A — current pipeline, as built

| Step | Model | In | Out | USD |
|---|---|---:|---:|---:|
| STT | whisper-turbo | 300 s | — | 0.003333 |
| Diarization (full re-emit) | ministral-3b | 2,100 | 1,850 | 0.000395 |
| Scorecard, 59 params ÷ 15 = 4 batches | ministral-3b | 10,400 | 6,400 | 0.001680 |
| **Total** | | | | **$0.005408** |

### **₹0.52 per 5-minute call — ₹6.19 per audio-hour.**

Composition: **STT 62%**, scorecard 31%, diarization 7%.

### 2.4 Path B — optimized, same providers, no accuracy loss

Four changes, each justified in §4:

| Change | Effect |
|---|---|
| Silence/hold trim at chunk boundaries | −3% to −11% billable audio (measured, hold-dependent) |
| Kill transcript-regenerating diarization; label Whisper's existing segments by index | diarization output 1,850 → ~150 tok |
| Single scorecard call instead of 4 (transcript sent once, not 4×) | input 10,400 → 2,900 |
| Evidence returned as segment index, not a copied quote | output −35% |
| Route LLM to `llama-3.1-8b-instant` | $0.05/$0.08 vs $0.10/$0.10 |

| Step | In | Out | USD |
|---|---:|---:|---:|
| STT, turbo (267 s after trim) | | | 0.002967 |
| Diarization labels | 1,900 | 150 | 0.000107 |
| Scorecard, single call | 2,900 | 2,800 | 0.000369 |
| **Total** | | | **$0.003443** |

### **₹0.33 per 5-minute call — ₹3.94 per audio-hour. A 37% reduction.**

STT is now **85%** of the bill. Further LLM optimization is chasing 15%.

> ### The turbo-vs-large-v3 tension (read this before going paid)
>
> Path B above assumes **turbo** pricing. Finding 1 recommends **large-v3** — and on the *free* tier that is unambiguously right, because both models share one quota and large-v3 is more accurate on Indic.
>
> On the *paid* tier the two recommendations pull against each other. large-v3 is $0.111/hr vs turbo's $0.040/hr — **2.8×**:
>
> | Pipeline (5-min call) | STT model | Total |
> |---|---|---:|
> | Path B | turbo | **₹0.33** |
> | Path B | large-v3 | **₹0.88** |
>
> So the decision splits by tier:
>
> - **Free tier (now):** large-v3, always. Free accuracy, no tradeoff.
> - **Paid tier (later):** do not blanket-switch. Use the Phase 2 **two-pass router** — transcribe on turbo, read the confidence score, and re-run only the low-confidence calls on large-v3. If ~20% of calls need the second pass, the blended cost is ≈₹0.43 rather than ₹0.88, and the calls that mattered still got the better model.
>
> This is exactly the decision the golden set from Phase 0 should settle: measure the real WER gap between turbo and large-v3 on *your* Hinglish audio, and you will know whether the second pass is worth ₹0.10 a call or not. Right now nobody knows, including me.

### 2.5 Is ₹0.10–0.20 per report achievable?

**On pay-per-use APIs: no, not for a 5-minute call.** The floor is ₹0.33 and it is dominated by an irreducible STT charge.

But the target isn't wrong — it's **duration-dependent**, which you already suspected:

| Call length | Path B cost | Inside ₹0.10–0.20? |
|---|---:|---|
| 2 min | ₹0.13 | yes |
| 3 min | ₹0.20 | yes |
| 3.5 min | ₹0.23 | over the boundary |
| 5 min | ₹0.33 | no |
| 10 min | ₹0.64 | no |

**Path B costs ≈ ₹0.065 per audio-minute.** Quote the client per-minute, not per-report — it's honest and it maps to what actually drives the cost.

To hit ₹0.10–0.20 on a *5-minute* call you need self-hosted GPU STT, and the breakeven is brutal: a ₹24,000/month L4 instance pays for itself against Groq only above **~6,250 audio-hours/month ≈ 75,000 five-minute calls/month**. Below that, Groq is strictly cheaper. **Do not self-host STT until you are past ~50k calls/month.**

---

## 3. The ₹0 architecture

Budget is zero, so the above is a *future* problem. What matters now is: **what does ₹0 actually buy, and what breaks first?**

### 3.1 Free-tier capacity (verified)

**Groq free tier:**

| Model | RPM | RPD | Audio sec/hour | Audio sec/day |
|---|---:|---:|---:|---:|
| `whisper-large-v3` | 20 | 2,000 | 7,200 | 28,800 |
| `whisper-large-v3-turbo` | 20 | 2,000 | 7,200 | 28,800 |

| Model | RPM | RPD | TPM | TPD |
|---|---:|---:|---:|---:|
| `llama-3.1-8b-instant` | 30 | 14,400 | 6,000 | 500,000 |
| `gpt-oss-20b` | 30 | 1,000 | 8,000 | 200,000 |

### 3.2 Four findings that change the design

> **Finding 1 — Switch to `whisper-large-v3` today. It is free-tier identical to turbo.**
>
> Both models have the *same* free quota: 20 RPM, 28,800 audio-sec/day. Turbo is a distilled 4-decoder-layer model and is measurably weaker on Hindi and other Indic languages than full `large-v3`. On the free tier, turbo buys you nothing but speed — and you are queue-bound, not latency-bound. **This is a pure accuracy win at zero cost.** It is a one-line change to `STT_MODEL_NAME`.

> **Finding 2 — Audio-seconds are now the scarce resource, so silence trimming is a capacity feature, not a cost feature.**
>
> 28,800 audio-sec/day is your hard ceiling. Every second of ringing, hold music, IVR and dead air burns it. Trimming converts directly into more calls per day on the same quota.
>
> **Measured, not estimated** (implemented in `audio_service.py`, numbers from the chunk planner):
>
> | Call profile | Saving |
> |---|---:|
> | 1,000 s call with a 90 s hold + 12 s ring + 10 s dead air | **11%** |
> | 1,000 s call, no hold, only inter-turn pauses | **2–3%** |
>
> This is lower than the 15–30% figure I first quoted, and the reason is a deliberate design choice: **only silence at chunk boundaries and file edges is skipped.** Inter-turn pauses stay inside the chunk. Stripping those too would mean concatenating speech spans, which breaks the mapping from Whisper's timestamps back to the original recording — and that mapping is what makes every evidence link and audio-jump in the report land on the right moment. Correct timestamps are worth more than the extra few percent.
>
> So the honest rule: **the saving is roughly however much hold and dead air the call contains.** For collections and support queues with real hold time, 10–15%. For back-to-back sales calls, closer to 3%.

> **Finding 3 — The diarization pass burns ~8% of your daily LLM quota per call for nothing.**
>
> `diarize_transcript()` sends the transcript and asks a 3B model to write the whole thing back out with speaker prefixes: ~4,000 tokens round-trip against a 500K/day budget. Meanwhile Groq's `verbose_json` response **already contains timestamped segments** — and `stt_service.py` throws them away, keeping only `.text`. Labelling existing segments by index costs ~150 output tokens instead of 1,850. **Killing this roughly doubles daily analysis capacity** and removes a real hallucination risk (a 3B model rewriting a Hinglish transcript *will* silently drop and alter content, no matter what the prompt says).

> **Finding 4 — Rule out the Gemini free tier for real client audio.**
>
> Google's terms permit training on free-tier prompts; paid tier and Vertex do not. BDO call recordings contain customer PII and sit under client confidentiality plus India's DPDP Act. Gemini free tier is fine for synthetic test data and for building your golden set — **not** for production client calls. Groq's data-handling terms should be read and confirmed in writing before you rely on them the same way; I have not verified them.

### 3.3 Zero-cost throughput ceiling

| Bound | Calculation | Calls/day (5-min) |
|---|---|---:|
| STT quota, untrimmed | 28,800 ÷ 300 s | **96** |
| STT quota, silence-trimmed (11% hold) | 28,800 ÷ 267 s | **107** |
| STT hourly burst | 7,200 ÷ 267 s | **27/hour** |
| LLM quota, current pipeline | 500,000 ÷ ~10,700 tok | 46 |
| LLM quota, Path B | 500,000 ÷ ~5,700 tok | **87** |
| LLM quota, Path B + Mistral free tier overflow | — | not binding |

### **₹0 gets you ~95–107 five-minute calls/day, ~3,000/month.**

That is a real pilot. It is enough to onboard 2–3 client teams and prove the product.

**The 7,200 audio-sec/hour cap is the constraint that dictates the architecture.** You can process 30 calls in an hour, no more. A synchronous `upload → transcribe → respond` request cannot survive that — the 31st upload in an hour must *queue*, not fail. This is why the job queue in Phase 1 is not optional polish.

### 3.4 Free infrastructure

| Layer | Free option | Ceiling | Note |
|---|---|---|---|
| Compute | **Oracle Cloud Always Free** — 4 ARM cores, 24 GB RAM | free forever | Best free box available. Runs API + Postgres + Redis + VAD comfortably. Indian signup can be fussy. |
| Postgres | Same box, or Supabase / Neon free | 0.5 GB managed | Self-host on Oracle to avoid the cap |
| Audio storage | **Cloudflare R2** free: 10 GB, **zero egress** | ~2,800 calls at 16 kbps Opus | Replace MinIO. Zero egress is the key — presigned audio playback is free |
| Queue | Redis on the Oracle box | — | Upstash free is only 10K cmd/day; too tight |
| Frontend | Vercel / Cloudflare Pages | generous | |
| Errors | Sentry free — 5K events/month | | |
| Metrics | Grafana Cloud free — 10K series | | |
| CI | GitHub Actions — 2,000 min/month | | |

**On audio storage:** transcode to **16 kHz mono Opus @ 16 kbps** before storing. Speech is intelligible and Whisper-accurate at that rate, and it shrinks a 5-min call from ~2.4 MB (mp3 64 kbps) to ~0.6 MB. That turns R2's 10 GB from ~1,000 calls into ~2,800, and cuts upload time. ffmpeg does this for free on the Oracle box.

**Do not self-host Whisper on the Oracle ARM box.** 4 Ampere cores run `large-v3` at roughly 0.15x realtime — a 5-minute call would take ~33 minutes. That box is for hosting the app, not for inference.

---

## 4. Production readiness audit

Ordered by severity. Severity reflects likelihood × blast radius, not effort.

### 4.1 Critical — will break in production

**C1. STT runs inside the HTTP request.**
`upload_and_transcribe_audio` does validation → Whisper → diarization LLM → MinIO → DB inline. The frontend sets a 180-second timeout to cope. On the free tier, once you hit 20 RPM or 7,200 audio-sec/hour, Groq returns 429 and the **user's upload is simply lost** — there is no retry and no persisted job. Under any concurrency this is the first thing to fail.

**C2. `asyncio.create_task` is not a job queue.**
`analysis_service.py:219` fires analysis into a bare task. Consequences: dies silently on deploy/restart/crash leaving rows stuck in `processing` forever; no retry; no backoff; no dead-letter; no concurrency limit, so 50 simultaneous uploads issue 50×4 = 200 parallel LLM calls and instantly trip the rate limit; exceptions are logged and swallowed.

**C3. Audio is uploaded *after* transcription, and failure is only logged.**
`transcripts.py` — if MinIO is down, `audio_file_key` stays `None`, the transcript is created anyway, and **the recording is gone permanently**. Audio is your source of truth; everything else is derived and re-computable. Store it first, then transcribe from storage.

**C4. Connection pool will exhaust.**
`pool_size=5, max_overflow=5` = 10 connections total, while every background task opens its own `AsyncSessionLocal`. Ten concurrent analyses starve the API of connections and requests begin timing out.

**C5. `COMPLETED_RUNS_CACHE` is an unbounded module-level dict.**
`analysis_service.py:21` — commented "LRU" but has no eviction and no size bound. It grows until the process OOMs, and it is per-worker so it's inconsistent under multiple workers. It also caches a Pydantic response object indefinitely, so a re-run's results never appear.

**C6. No pagination anywhere on list endpoints.**
`GET /transcripts` returns *every* transcript for the org with full `raw_text`, and the frontend filters client-side in `transcripts/page.tsx:220`. At 3,000 calls/month this is a multi-megabyte response within the first month and the page becomes unusable.

### 4.2 High

**H1. No PII redaction.** Indian call-center audio routinely contains card numbers, CVVs, OTPs, Aadhaar, PAN, addresses. You are storing all of it in plaintext in `transcripts.raw_text` and shipping it to third-party LLM APIs. Under the DPDP Act and any BDO client contract this is the finding that fails a security review. Needs redaction before storage and before egress to any LLM.

**H2. No CSRF protection.** Cookie auth + `SameSite=Lax` + `allow_credentials=True` CORS. `Lax` blocks cross-site POST, so you are *mostly* covered — but any state-changing `GET`, or a future switch to `SameSite=None`, opens it. Add a double-submit CSRF token or require a custom header on mutations.

**H3. No idempotency on upload.** A retried or double-clicked upload re-transcribes and re-charges quota. Hash the audio (SHA-256) and return the existing transcript on a match — this also dedupes genuinely repeated recordings, which is common in QA workflows.

**H4. `detect_all_transcript_languages` is fragile.** Keyword matching on `\bka\b`, `\bki\b`, `\bji\b` etc. will misfire constantly on English text ("ka" appears in names, "hai" in "Shanghai" won't match but many will). Script-range detection (Devanagari/Tamil/…) is sound; the romanized-Hinglish keyword list is not. Use it as a weak signal only, and prefer Whisper's own `language` field plus per-segment language when available.

**H5. Whisper `prompt` is capped at 224 tokens and can induce hallucination.** The current `stt_prompt` is fine in length, but Whisper is known to loop or hallucinate on silence, especially with a leading prompt. This is another argument for VAD trimming, plus a `no_speech_prob` guard.

**H6. `raw_llm_response` stores every batch's full JSON per run.** With 4 batches × 59 parameters this is tens of KB per analysis in Postgres, growing unboundedly, and it is almost never read. Truncate, compress, or move to object storage.

**H7. In-process rate limiter.** slowapi with `get_remote_address` holds state in memory — ineffective across workers, and keyed on IP so a whole office NAT shares one bucket. Needs Redis backing and per-org/per-user keys.

**H8. No retry on the STT call.** `transcribe_audio` has no retry wrapper at all, while the LLM client has a sensible one. A single 429 or transient 5xx from Groq loses the upload.

### 4.3 Medium

- **M1.** Whole file held in memory 3–4× (`file.read()` → `BytesIO` for Groq → `BytesIO` for MinIO). At 25 MB × concurrency this is real memory pressure on a free-tier box. Stream to disk/R2 instead.
- **M2.** No structured logging. Human-readable strings with a request ID; not queryable. Emit JSON logs.
- **M3.** No metrics or tracing. No visibility into queue depth, STT latency, quota consumption, failure rate — all of which you must watch closely on a metered free tier.
- **M4.** No health check on dependencies. `/health` doesn't verify DB, storage, or provider reachability.
- **M5.** Tests are named by build phase (`test_phase1`, `test_phase7_8_...`) and cover services, not the API surface. No test asserts tenant isolation, which is the one invariant most worth pinning.
- **M6.** No alembic-vs-models drift check in CI. There's already a migration literally named `sync_schema_with_current_models`, which is the symptom.
- **M7.** Hardcoded `provider="mistral"` in cost logging (`analysis_service.py:266`, `:296`) — will misattribute the moment you route to Groq. The model→price matrix in `llm_cost_repository.py` also silently falls back to `DEFAULT_PRICING` on an unknown model, quietly producing wrong numbers.
- **M8.** No refresh tokens; a 24-hour access token with no revocation path. A suspended user keeps working until expiry (`is_active` is checked per request, so this is partly mitigated).
- **M9.** `estimate_audio_duration_seconds` guesses 64 kbps for compressed audio. Only used as a fallback when Whisper doesn't return duration, but it feeds billing estimates. Use ffprobe.

### 4.4 Accuracy gaps (priority #1 per your brief)

**A1. There is no way to know if the transcripts are accurate.** No golden set, no WER measurement, no regression test. Every accuracy claim in the product today is unverifiable — including mine. **This is the single most important gap in the project.**

**A2. Turbo is the wrong model for Indic.** See Finding 1. Free to fix.

**A3. No confidence signals surfaced.** Whisper's `verbose_json` returns `avg_logprob`, `no_speech_prob` and `compression_ratio` per segment. These are being discarded. They are exactly what you need to flag "this transcript is unreliable, don't trust the analysis" — which your brief asks for under "validation and quality checks".

**A4. No domain vocabulary biasing.** The 224-token Whisper prompt should carry client-specific brand names, product SKUs and agent names. This is a measurable WER win on proper nouns, which is where call-QA transcripts fail most visibly and most embarrassingly.

**A5. No audio preprocessing.** No resample to 16 kHz mono, no loudness normalization, no denoise. Real call-center audio is 8 kHz telephony with compression artifacts and background floor noise.

**A6. Diarization is speaker *role-guessing by an LLM from text alone*, with no acoustic input.** It cannot hear who is speaking. On overlapping speech, short turns, or a three-party call (agent + customer + supervisor), it will be wrong, and it fails silently.

---

## 5. Roadmap

Sequenced so each phase is independently shippable and every phase respects the ₹0 constraint.

### Phase 0 — Measure before changing anything (1 week)

Nothing else in this document is trustworthy without this.

1. **Build a golden set.** 50–100 real calls covering Hindi, Hinglish, English, and at least two other Indic languages; noisy and clean; short and long. Human-correct the transcripts. This is unglamorous manual work and it is the highest-leverage week in the whole project.
2. **Build a WER harness.** Score `large-v3` vs `turbo` vs any candidate, overall and sliced by language. Use it as a regression gate in CI.
3. **Instrument current cost per call** from `llm_cost_logs` and compare against §2.3. Verify my arithmetic against your real traffic; my token estimates are estimates.

**Exit criteria:** you can answer "what is our WER on Hinglish?" with a number.

### Phase 1 — Zero-cost wins + stop the bleeding (1–2 weeks)

Highest value per hour of work in the project.

| # | Change | Why |
|---|---|---|
| 1 | `STT_MODEL_NAME` → `whisper-large-v3` | Free accuracy (Finding 1) |
| 2 | Silence trim at chunk boundaries (ffmpeg silencedetect) | +3-11% daily capacity (Finding 2) |
| 3 | ffmpeg → 16 kHz mono Opus before storage | 4× more calls fit in R2's 10 GB |
| 4 | Persist Whisper `segments` incl. `avg_logprob` / `no_speech_prob` | Unlocks A3, and cheap diarization |
| 5 | Replace diarization with index-labelling over stored segments | ~2× LLM capacity, removes hallucination risk (Finding 3) |
| 6 | Single scorecard call; evidence as segment index | −72% input tokens |
| 7 | Job queue (arq or Celery + Redis on the Oracle box) with provider-aware rate limiting | Fixes C1, C2 |
| 8 | Upload audio to R2 **first**, transcribe from storage | Fixes C3 |
| 9 | SHA-256 audio dedup + idempotency key | Fixes H3, stops double-spend |
| 10 | Bound/remove `COMPLETED_RUNS_CACHE` | Fixes C5 |
| 11 | Paginate all list endpoints; move search to Postgres FTS | Fixes C6 |
| 12 | Raise pool size; single session per job | Fixes C4 |

**Exit criteria:** upload returns `202` immediately; a queued job survives a restart; 429s retry with backoff instead of losing work; measured cost per call matches §2.4.

### Phase 2 — Accuracy (2–3 weeks)

1. **Confidence scoring.** Aggregate per-segment `avg_logprob` into a transcript quality score. Surface a "low confidence — review before trusting" banner in the report. Gate analysis below a threshold.
2. **Two-pass STT routing.** Cheap pass → if confidence low, re-run on the stronger model. On the free tier both cost ₹0, so route purely on accuracy.
3. **Domain vocabulary injection** into the Whisper prompt, per organization (A4).
4. **Audio preprocessing** — resample, normalize, denoise (A5).
5. **Acoustic diarization.** `pyannote-audio` community model runs on CPU, free, and gives real speaker turns instead of LLM guesswork. Combine with the LLM only for *role assignment* (which speaker is the agent), which is a cheap classification over ~20 tokens.
6. **Code-switch handling.** Evaluate per-segment language detection; consider language-conditioned decoding for heavily mixed calls.
7. **Structured outputs** instead of prompt-and-pray JSON, where the provider supports it. Eliminates the correction-retry round trip.

**Exit criteria:** WER improvement over Phase 0 baseline is measured and non-trivial on the Hinglish slice.

### Phase 3 — Analysis depth (2–3 weeks)

Your brief lists summaries, intent, sentiment, topics, objections, outcomes, action items, key moments. Most of this can come from **one** well-designed LLM pass, not one pass per feature — that's the difference between ₹0.33 and ₹1.60 per call.

1. **One "call understanding" pass** producing a structured object: summary, intent, topics, sentiment trajectory (per segment window), objections, outcome, action items, key moments with timestamps, talk-time ratio, interruption count, longest monologue, silence/hold analysis.
2. **Derive the cheap things in code, not in the LLM.** Talk-time ratio, interruptions, silence duration, speaking rate, hold time, turn counts — all computable from segment timestamps for ₹0. Do not pay a model to estimate what arithmetic can give you exactly. (The current `Agent Talk-Time Ratio` extraction section *asks the LLM to estimate* this — replace it.)
3. **Cache the understanding pass.** Re-running a different scorecard against the same call should reuse it, not redo it.
4. **Scorecard evaluation consumes the understanding object**, not the raw transcript — smaller input, more consistent scoring.

### Phase 4 — Reports & dashboards (2–3 weeks)

1. Per-call report: score breakdown, sentiment timeline, key moments jumping to audio timestamps, evidence links into the transcript, confidence indicator.
2. Aggregate dashboards: score trends, agent leaderboards, topic/objection frequency, outcome distribution, FCR rate, compliance-failure heatmap.
3. Exports: PDF, CSV, XLSX. (JSON/CSV exist in `lib/export-utils.ts`.)
4. **Charts:** the frontend currently has zero charting library — the "Call Performance Distribution" panel is hand-rolled divs. Add one.

### Phase 5 — Client-facing features (2–3 weeks)

1. **Search across calls** — Postgres FTS first; embeddings only if FTS proves insufficient (embeddings cost money and add infrastructure).
2. **Ask-a-question over analyzed calls** — retrieve over the *structured understanding objects*, not raw transcripts. Far cheaper and more accurate.
3. Saved filters, alerting on compliance failures, scheduled digests, bulk upload, agent scorecards over time.

### Phase 6 — Hardening (ongoing, start early)

PII redaction (H1 — pull earlier if any real client data lands), CSRF, structured logs, Sentry, metrics, dependency health checks, tenant-isolation tests, alembic drift CI, retention policy, DPDP compliance review.

---

## 6. Answers to your specific questions

**"Is ₹0.10–0.20 per report realistic?"**
Per *5-minute* call on pay-per-use APIs: no. Floor is **₹0.33**, 85% of it irreducible STT. Per *3-minute* call: yes, ₹0.20. The honest unit is **₹0.065 per audio-minute** (Path B). Below ~75,000 calls/month, self-hosting STT costs more, not less.

**"Can we make it cheaper?"**
Yes — **₹0 for the first ~100 calls/day**, using Groq's free tier properly. That requires the queue and rate-limiting work in Phase 1; it is not a config change. Past that ceiling, Path B's ₹0.33/call means 3,000 calls/month ≈ **₹990/month**.

**"Should we keep Groq?"**
Yes. On the free tier it is the best option available and its Whisper quota is generous. Switch the *model* from turbo to `large-v3` immediately (free accuracy). Rule out the Gemini free tier for real client audio on data-training grounds.

**"What's the biggest risk?"**
Not cost. It's that **you cannot currently measure transcript accuracy**, while your #1 stated priority is accuracy. Phase 0 fixes that and should start before anything else.

---

## Appendix — sources

- [Groq pricing, 2026 breakdown — CloudZero](https://www.cloudzero.com/blog/groq-pricing/)
- [Groq rate limits (free tier) — Groq docs](https://console.groq.com/docs/rate-limits)
- [Whisper API pricing comparison — TokenMix](https://tokenmix.ai/blog/whisper-api-pricing)
- [Gemini API free tier limits, 2026 — TokenMix](https://tokenmix.ai/blog/gemini-api-free-tier-limits)
- [Gemini free tier data-training terms — Harboratory](https://harboratory.com/gemini-api-free-tier-limits-in-2026-explained/)
