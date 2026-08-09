# SimplyApply

**Free, open-source, self-hosted job search + truthful resume tailoring.**

Search real job postings, click Apply on one, and get an ATS-safe resume regenerated from your structured data and tailored to that posting — with a mechanical guarantee that nothing was invented.

```
search  →  pick a posting  →  tailor()  →  no-fabrication check  →  docx + PDF  →  apply link
```

Your resume, your API keys, and your application history never leave your machine.

---

## Why this exists

Most resume tailoring tools either paywall the useful part or quietly let a language model embellish your experience. SimplyApply does neither:

- **Tailoring is the product, and it's free.** No autofill engine, no accounts, no SaaS.
- **The no-fabrication rule is enforced in code, not in a prompt.** See below.
- **Your resume is structured data, not a file.** Every output is regenerated from it; no PDF is ever edited in place.

---

## The no-fabrication guardrail

This is the part that matters, so it's worth being precise about how it works.

Telling a model "don't invent experience" is a request, not a control. So after every tailoring run, `backend/app/services/guardrail.py` validates the output against your base resume:

| Checked | Rule |
|---|---|
| Employers, job titles, schools, degrees | Must match a value in your base resume |
| Every date | Must match a date in your base resume — no stretching to close a gap |
| Every number, percentage, and metric | Must appear in your base resume — 15% cannot become 40% |
| Every skill and keyword | Must appear *somewhere* in your base resume |

Reordering, rephrasing, dropping irrelevant bullets, and rewriting your summary are all free — that's what tailoring is. Surfacing a skill that's buried inside a bullet is allowed. Adding one because the job description asked for it is not.

**If the check fails, it retries once with the specific violations fed back. If it fails again, you get your original resume plus an explicit warning** — never silently fabricated content. The worst case is a generic application, not a rescinded offer.

It's a whitelist over your resume rather than a blocklist of suspicious phrases, so its failure mode is a false positive (mildly annoying) instead of a false negative (career damage).

---

## Installation — Step by Step

### Step 0: Check your prerequisites

**Pick one path:**

| Path | What you need |
|---|---|
| **Docker (simplest)** | [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running |
| **Native (more control)** | Python 3.12+, Node 20+, and pip/npm |

---

### Path A — Docker (recommended, one command)

1. **Clone the repo**

   ```bash
   git clone https://github.com/opioidem/simply-apply-1.git
   cd simply-apply-1
   ```

2. **Optionally copy the env template** (not required — you can configure everything in the UI)

   ```bash
   cp .env.example .env
   ```

   If you edit `.env`, any keys you put here become the defaults shown on first boot.

3. **Start the app**

   ```bash
   docker compose up
   ```

4. **Open your browser**

   Go to [http://localhost:3000](http://localhost:3000).

That's it. The backend runs inside the container and is invisible — only the frontend port is exposed.

---

### Path B — Native install (Python + Node)

1. **Clone the repo**

   ```bash
   git clone https://github.com/opioidem/simply-apply-1.git
   cd simply-apply-1
   ```

2. **Start the backend** (new terminal window)

   ```bash
   cd backend

   # Create a virtual environment
   python -m venv .venv

   # Activate it
   # macOS / Linux:
   source .venv/bin/activate
   # Windows:
   .venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt

   # Start the server
   uvicorn app.main:app --port 8000
   ```

   Leave this terminal open. You should see `Uvicorn running on http://0.0.0.0:8000`.

3. **Start the frontend** (second terminal window)

   ```bash
   cd frontend

   npm install
   npm run dev
   ```

4. **Open your browser**

   Go to [http://localhost:3000](http://localhost:3000).

---

### Step 1: Configure an AI provider

The app won't be able to tailor resumes until you add an LLM API key. Open the **Settings** page and pick a provider:

| Provider | Best for | What you need |
|---|---|---|
| **Anthropic** | Best results | An [Anthropic API key](https://console.anthropic.com) |
| **OpenAI-compatible** | Flexibility | A key from OpenAI, Groq, Together, OpenRouter, or any OpenAI-compatible server |
| **Ollama** | Completely free, offline | [Ollama](https://ollama.com) installed locally with a model pulled (`ollama pull qwen2.5:7b`) |

Keys are stored in the local SQLite database and are **write-only** — no endpoint ever returns the key value back to you.

**Test your connection:** after saving, click **"Test Connection"** in Settings. A green check means you're good to go.

---

### Step 2: Add your resume

Go to the **Resume** tab and either:

- **Upload** an existing resume (PDF or DOCX — it will be parsed into structured JSON Resume format), or
- **Type it in** manually using the form.

This structured resume is the source of truth. Every tailored application is regenerated from it.

---

### Step 3: Search and apply

1. Go to **Search**, enter a job title and location.
2. Pick a posting from the results (scraped from Greenhouse and Arbeitnow).
3. Click **Apply** — the app tailors your resume to that posting, runs the guardrail check, and gives you both a **DOCX** (safest for ATS uploads) and a one-page **PDF**.
4. Follow the apply link to submit on the employer's site.

---

## Project status

Milestones M0–M5 complete: the full search → tailor → render → apply loop works end to end.

**Verified:** 58 passing tests covering the guardrail, tailor retry/fallback, DOCX ordering, single-page PDF rendering, and the complete apply loop through the real app.

**Not yet built (M6+):** remaining Tier-1 connectors (Adzuna, USAJOBS), JD-match ranking, a two-column PDF theme, and the Tauri desktop wrap.

---

## Running the tests

```bash
cd backend
.venv/bin/python -m pytest        # Windows: .venv\Scripts\python -m pytest
```

If you touch `guardrail.py`, run these first. They're the difference between a tool that tailors resumes and one that fabricates them.

---

## Adding a job source

One file. Drop it in `backend/app/connectors/` — it's discovered automatically, with no registry to update:

```python
class MyBoardConnector(JobConnector):
    source = "myboard"
    label = "My Board"
    priority = 30          # lower wins when deduping across sources

    async def fetch(self, client, q) -> list[JobRecord]:
        resp = await client.get("https://example.com/api/jobs")
        resp.raise_for_status()
        return [self._normalize(row) for row in resp.json()]
```

Two rules: return normalized `JobRecord`s, and **raise on failure rather than returning `[]`** — the search layer catches per-connector and reports the failure in the UI, but a swallowed error would look identical to "no results."

Shipping today: **Greenhouse** (per-company ATS boards) and **Arbeitnow** (remote/EU).

---

## How it works

```
┌──────────────────────────────────────────────────────┐
│  docker compose up  (your machine)                    │
│                                                       │
│   Next.js  ──/api rewrite──▶  FastAPI                 │
│                                 ├── source connectors │
│                                 ├── dedupe + rank     │
│                                 ├── tailor()          │
│                                 ├── guardrail  ◀── the important bit
│                                 └── docx + PDF render │
│                                        │              │
│                                   SQLite (1 file)     │
└──────────────────────────────────────────────────────┘
          │                              │
   public job APIs              your LLM provider
```

**Resume format.** Stored as [JSON Resume](https://jsonresume.org) — a community standard, so your data stays portable to other tooling.

**Outputs.** Every apply produces both files. The **PDF** is the human-facing copy — always exactly one page, rendered with reportlab (pure Python, no system dependency) and scaled to fit rather than truncated when content runs long. The **DOCX** is the safest choice for ATS uploads (single column, no tables, standard headings). If PDF rendering ever fails, the apply degrades to DOCX-only for that one job with a clear message rather than erroring.

---

## License

[AGPL-3.0](LICENSE). Chosen deliberately: you can run, modify, and share this freely, but if you host a modified version as a service, you have to share your changes too.
