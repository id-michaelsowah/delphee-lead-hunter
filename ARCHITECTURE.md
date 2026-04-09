# Delphee Lead Hunter — Architecture & Scoring Guide

This document explains how the application works, how leads are scored, and what users need to know when interpreting results.

---

## What the App Does

Delphee Lead Hunter is an AI-powered scanner that monitors developing markets for business opportunities relevant to Delphee's IFRS 9 / ECL software. It searches the web, scores what it finds, and surfaces the most actionable leads for the sales team.

---

## How a Scan Works — 4 Phases

When you start a scan, the app runs four sequential phases automatically:

```
Phase 1: Discovery (Gemini)
         ↓
Phase 2: Analysis & Scoring (Claude)
         ↓
Phase 3: Deduplication
         ↓
Phase 4: Store & Display
```

### Phase 1 — Discovery (Gemini + Google Search)

**Tool:** Google Gemini (gemini-2.5-flash, with fallback to 2.0-flash and 2.0-flash-lite)

Gemini is given live Google Search access. For each batch of 3 countries, it searches the web for:
- Tenders and RFQs for ECL / IFRS 9 software
- Regulatory deadlines forcing IFRS 9 adoption
- News about banks, MFIs, or DFIs needing credit risk / provisioning tools
- Consulting and partnership opportunities

For each result found, Gemini extracts: title, institution, country, type, summary, published date, deadline, source URL, and contact info.

Countries are processed in batches of 3 with a 1.5-second delay between batches to respect API rate limits.

### Phase 2 — Analysis & Scoring (Claude)

**Tool:** Claude Sonnet (claude-sonnet-4-6)

Claude receives the raw discovery results in batches of 12 and enriches each one with:
- A **relevance score** (0–100)
- A **freshness** classification
- An **urgency** level
- A **follow-up action** recommendation
- A **relevance reason** explaining the score

This is described in detail in the Scoring section below.

### Phase 3 — Deduplication

Before saving, the app removes duplicates:
- **Exact dedup:** within the current scan batch (title + institution)
- **Fuzzy dedup:** against all leads already in the database, using a similarity threshold of 85%

This prevents the same opportunity from appearing multiple times across repeated scans.

### Phase 4 — Store & Display

Unique leads are saved to the database (Firestore in production) and immediately shown in the UI, sorted by relevance score.

---

## Scoring Explained

### Why Not a Formula?

A deterministic formula (e.g. keyword counts × date weight) requires clean, structured input. Discovery results are unstructured web text — descriptions vary wildly, dates are sometimes implicit, and relevance is contextual. A formula would misclassify opportunities like:

- "Bank updating its credit risk framework" → likely needs ECL software (high relevance)
- "Bank hiring a credit risk analyst" → does not need ECL software (low relevance)

These look similar to a keyword formula but mean very different things. Claude reads the full description and applies judgment.

### The Semi-Deterministic Approach

Claude is not free to score arbitrarily. The prompt constrains it to specific score bands per opportunity type, making scores consistent and explainable:

| Score Range | Opportunity Type |
|-------------|-----------------|
| 70–100 | Active tenders or RFQs explicitly for ECL / IFRS 9 software |
| 50–75 | Regulatory news forcing IFRS 9 adoption in a new market |
| 40–65 | General credit risk or provisioning tenders (may require an ECL tool) |
| 20–45 | News or consulting not directly requiring a software tool |
| ≤40 (cap) | Expired or outdated results, regardless of type |

**Why the ranges overlap:** The overlaps are intentional judgment zones for ambiguous cases. For example, a central bank regulation that mandates IFRS 9 adoption and includes a named procurement process sits between "regulatory news" (50–75) and "active tender" (70–100) — Claude can score it at 72, reflecting its hybrid nature. Overlaps also allow strength within a category to be expressed: a weak regulatory notice scores 52, a strong one with a deadline and procurement process attached scores 73. Both are regulatory news, but they are not equally valuable leads.

The one hard rule is the **≤40 cap on expired/outdated results** — no matter how relevant the underlying opportunity was, Claude cannot score it above 40 once it has passed.

**Why this hybrid works:** The bands enforce consistency across scans and analysts, while Claude handles the ambiguity of real-world text. Scores are traceable — every lead includes a `relevance_reason` field explaining exactly why it received its score.

### Freshness

Freshness reflects how current the opportunity is, based on publication date and deadline:

| Status | Meaning |
|--------|---------|
| **active** | Published less than 6 months ago, or has a future deadline |
| **stale** | 6–12 months old, no clear deadline |
| **outdated** | More than 12 months old, no future dates |
| **expired** | Deadline has already passed |
| **unknown** | No dates found in the source |

### Urgency

Urgency reflects how time-sensitive the follow-up is:

| Level | Criteria |
|-------|---------|
| **high** | Active opportunity with a deadline within 30 days |
| **medium** | Active with deadline 30–90 days away, or stale with strong relevance |
| **low** | Everything else |

---

## Lead Fields Reference

Each lead in the database contains the following fields:

| Field | Description |
|-------|-------------|
| `title` | Short descriptive title of the opportunity |
| `institution` | Bank, MFI, DFI, or regulatory body name |
| `country` | Country where the opportunity is based |
| `type` | tender, rfq, news, regulation, consulting, or partnership |
| `summary` | 2–3 sentence description |
| `relevance_score` | 0–100 score (higher = more relevant to Delphee) |
| `relevance_reason` | Claude's explanation of the score |
| `freshness` | active / stale / outdated / expired / unknown |
| `freshness_reason` | Explanation of the freshness classification |
| `urgency` | high / medium / low |
| `deadline` | Submission or decision deadline (ISO date) |
| `published_date` | When the opportunity was published (ISO date) |
| `source_url` | Direct link to the original source |
| `contact_info` | Email, phone, or contact person if available |
| `follow_up_action` | Specific recommended next step |
| `lead_status` | new / contacted / qualified / closed (manually updated) |
| `assigned_to` | Team member responsible (manually set) |
| `notes` | Free-text notes (manually added) |

---

## Regions

The app organises countries into 9 regions. Scans are run per region — you can select one or multiple regions per scan.

| Region | Countries |
|--------|-----------|
| West Africa | Ghana, Nigeria, Senegal, Côte d'Ivoire, Burkina Faso, Mali, Niger, Togo, Benin, Guinea, Guinea-Bissau, Mauritania, Gambia, Liberia, Sierra Leone |
| East Africa | Kenya, Tanzania, Uganda, Ethiopia, Rwanda, Djibouti, Eritrea, Burundi |
| Central Africa | Cameroon, Chad, Gabon, DRC, Republic of Congo, Equatorial Guinea, São Tomé and Príncipe |
| Southern Africa | South Africa, Zambia, Zimbabwe, Mozambique, Malawi, Madagascar, Angola, Botswana, Namibia, Lesotho, Swaziland |
| North Africa & Middle East | Egypt, Morocco, Tunisia, Jordan, Lebanon, Algeria, Libya, Saudi Arabia, UAE, Qatar, Kuwait, Oman, Yemen, Syria |
| South & Southeast Asia | Bangladesh, Nepal, Cambodia, Vietnam, Sri Lanka, Pakistan, Indonesia, Philippines, Myanmar, Thailand, India |
| Central Asia & Caucasus | Georgia, Armenia, Uzbekistan, Kyrgyzstan, Azerbaijan |
| Latin America & Caribbean | Bolivia, Honduras, Guatemala, Paraguay, Ecuador, Colombia, Peru, El Salvador, Nicaragua, Costa Rica |
| Eastern Europe | Moldova, Albania, Kosovo, North Macedonia, Ukraine, Bosnia and Herzegovina, Serbia, Montenegro |

Regions can be updated by editing `app/scanner/regions.json` — no server restart required.

---

## Managing Leads

Leads can be tracked through a simple pipeline. Update `lead_status` directly from the Leads page:

- **new** — just discovered, not yet reviewed
- **contacted** — initial outreach made
- **qualified** — confirmed as a real opportunity
- **closed** — won, lost, or no longer relevant

You can also assign a lead to a team member (`assigned_to`) and add free-text notes.

Leads can be exported to CSV from the Leads page for use in external tools.

---

## Usage & Cost Tracking

The app tracks token consumption for both Gemini and Claude. Visit the `/api/usage` endpoint or check `usage.json` in the project root to see monthly token counts and estimated API costs.

---

## Access Control

The app is protected by HTTP Basic Auth. A password is required to access any page. This is configured via the `APP_PASSWORD` environment variable on Cloud Run.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI |
| Frontend | React (Vite) |
| AI — Discovery | Google Gemini 2.5 Flash (Google Search grounding) |
| AI — Analysis | Anthropic Claude Sonnet 4.6 |
| Database (production) | Google Firestore |
| Database (local) | SQLite |
| Hosting | Google Cloud Run |
| Real-time updates | WebSocket (during active scan) |
