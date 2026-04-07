# Delphee Lead Hunter

AI-powered IFRS 9 / ECL opportunity scanner for developing markets.

Scans the web for tenders, RFQs, regulations, and news that signal demand for IFRS 9 / Expected Credit Loss solutions — then scores, ranks, and presents them as qualified leads.

---

## Quick Start (Docker — easiest)

1. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   # Edit .env — add GEMINI_API_KEY and ANTHROPIC_API_KEY
   ```

2. Start the full stack:
   ```bash
   docker-compose up --build
   ```

3. Open **http://localhost:8000**

That's it. The app, database (PostgreSQL), and frontend are all running in Docker.

---

## Quick Start (Local Development)

1. Copy and configure environment:
   ```bash
   cp .env.example .env
   # Edit .env — add GEMINI_API_KEY and ANTHROPIC_API_KEY
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the frontend dev server (terminal 1):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Start the backend (terminal 2):
   ```bash
   uvicorn app.main:app --reload
   ```

5. Open **http://localhost:5173** (Vite dev server with hot reload)

---

## API Keys Required

| Key | Where to get it |
|-----|-----------------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) |

Both keys are required. The scanner uses Gemini for web search/discovery and Claude for lead analysis and scoring.

---

## Sharing the Docker Image (offline / air-gapped)

Build and export to a portable file:
```bash
docker build -t delphee-lead-hunter .
docker save delphee-lead-hunter | gzip > delphee-lead-hunter.tar.gz
```

Recipient loads and runs with their own API keys:
```bash
docker load < delphee-lead-hunter.tar.gz
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=their-key \
  -e ANTHROPIC_API_KEY=their-key \
  -e DATABASE_URL=sqlite:///./delphee.db \
  -e DB_BACKEND=sql \
  delphee-lead-hunter
```

Open **http://localhost:8000** — no internet needed except for the scan itself.

---

## Deployment Option A — Google Cloud Run (serverless, recommended)

Scales to zero when idle — you pay nothing when not scanning.
Uses Firestore for persistent storage (free tier: 1 GiB, 50K reads/day).

**Prerequisites:** `gcloud` CLI installed, authenticated (`gcloud auth login`), API keys exported as environment variables.

```bash
export GEMINI_API_KEY=your-key
export ANTHROPIC_API_KEY=your-key

chmod +x deploy/cloudrun.sh
./deploy/cloudrun.sh YOUR_GCP_PROJECT_ID
```

The script will:
- Enable required GCP APIs (Cloud Run, Cloud Build, Firestore)
- Create a Firestore database
- Build and push the Docker image
- Deploy to Cloud Run and print the public URL

**Custom domain** (e.g. `leads.delphee.de`):
```bash
gcloud run domain-mappings create \
  --service delphee-lead-hunter \
  --domain leads.delphee.de \
  --region us-central1
```

---

## Deployment Option B — VPS with Docker (always-on, persistent)

Recommended for teams or scheduled daily scans. Uses PostgreSQL with a persistent volume.

Suitable VPS: DigitalOcean ($6/mo), Hetzner ($4/mo), or Vultr ($6/mo) — 1 vCPU, 1 GB RAM is sufficient.

**Step 1 — Bootstrap the server** (run once on a fresh Ubuntu 22.04+ VPS):
```bash
ssh root@YOUR_VPS_IP < deploy/vps-setup.sh
```

**Step 2 — Copy the project to the VPS:**
```bash
# Option A: git clone
ssh root@YOUR_VPS_IP "git clone YOUR_REPO_URL /opt/delphee"

# Option B: rsync
rsync -av --exclude='.env' --exclude='venv' --exclude='node_modules' \
  . root@YOUR_VPS_IP:/opt/delphee/
```

**Step 3 — Fill in API keys on the server:**
```bash
ssh root@YOUR_VPS_IP "nano /opt/delphee/.env"
```

**Step 4 — Set your domain** (optional — for HTTPS):
Edit `deploy/Caddyfile` and replace `leads.example.com` with your domain,
then point the domain's DNS A record to your VPS IP.

**Step 5 — Start the app:**
```bash
ssh root@YOUR_VPS_IP
cd /opt/delphee
docker compose -f deploy/vps-docker-compose.yml up -d --build
```

The app will be at `https://your-domain.com` (Caddy auto-provisions SSL)
or `http://YOUR_VPS_IP:80` if using IP-only access.

**Update after code changes:**
```bash
cd /opt/delphee
git pull
docker compose -f deploy/vps-docker-compose.yml up -d --build
```

---

## Access Control (APP_PASSWORD)

If `APP_PASSWORD` is set, the app requires a password before anyone can use it. The browser shows a native login prompt — any username works, only the password matters.

**Set it in `.env`:**
```bash
APP_PASSWORD=your-strong-password-here
```

**Change the password** (Docker):
```bash
# 1. Update APP_PASSWORD in .env
# 2. Restart the app container (no rebuild needed)
docker compose restart app
```

**Change the password** (VPS):
```bash
ssh root@YOUR_VPS_IP
nano /opt/delphee/.env   # update APP_PASSWORD
docker compose -f deploy/vps-docker-compose.yml restart app
```

**Disable password** (local dev): leave `APP_PASSWORD` blank or remove it from `.env`. The `/health` endpoint is always accessible regardless.

---

## Project Structure

```
delphee-lead-hunter/
├── app/                    # FastAPI backend
│   ├── main.py             # App entry point, static file serving
│   ├── config.py           # Settings (env vars)
│   ├── api/                # REST API routes + WebSocket
│   ├── pipeline/           # Scan pipeline (discovery + analysis)
│   ├── db_sql.py           # SQLite / PostgreSQL repository
│   └── db_firestore.py     # Firestore repository (Cloud Run)
├── frontend/               # React + Vite frontend
│   ├── src/
│   │   ├── pages/          # NewScan, ScanHistory, ScanDetail, AllLeads
│   │   ├── components/     # Layout, LeadCard
│   │   └── api.js          # API client + WebSocket connector
│   └── dist/               # Production build (served by FastAPI)
├── deploy/
│   ├── cloudrun.sh         # Google Cloud Run deployment script
│   ├── vps-setup.sh        # VPS bootstrap script
│   ├── vps-docker-compose.yml  # Production VPS compose (with Caddy)
│   └── Caddyfile           # Reverse proxy + auto-HTTPS config
├── Dockerfile              # Multi-stage build (Node → Python)
├── docker-compose.yml      # Local Docker stack (app + PostgreSQL)
├── .env.example            # Environment variable template
└── requirements.txt        # Python dependencies
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic Claude API key |
| `DB_BACKEND` | No | `sql` | `sql` or `firestore` |
| `DATABASE_URL` | No | SQLite | SQLAlchemy async URL |
| `DB_PASSWORD` | No | `changeme` | PostgreSQL password (Docker) |
| `GOOGLE_CLOUD_PROJECT` | Firestore only | — | GCP project ID |
| `APP_PASSWORD` | No | *(open)* | Password to access the app (recommended for any public deployment) |
| `SECRET_KEY` | No | — | App secret (future auth) |
| `SENDGRID_API_KEY` | No | — | Email digest (optional) |
| `ALERT_EMAIL` | No | — | Recipient for email digest |
