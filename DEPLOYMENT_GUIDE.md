# Agentic Inventory Restocking Service - Deployment & Integration Guide

A comprehensive guide for deploying the Agentic Inventory Restocking Service to production, including all required APIs, databases, third-party integrations, and best practices.

---

## Table of Contents

1. [Prerequisites & System Requirements](#prerequisites--system-requirements)
2. [Required APIs & Services](#required-apis--services)
3. [Optional Integrations](#optional-integrations)
4. [Database Options](#database-options)
5. [Step-by-Step Deployment](#step-by-step-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Platform-Specific Guides](#platform-specific-guides)
8. [Tips & Tricks](#tips--tricks)
9. [Troubleshooting](#troubleshooting)
10. [Client Handover Checklist](#client-handover-checklist)

---

## Prerequisites & System Requirements

### Minimum Requirements
- **Python**: 3.10 or higher
- **Memory**: 512MB RAM minimum (1GB recommended)
- **Storage**: 100MB for application + database
- **Network**: Outbound HTTPS access to AI APIs

### Required Knowledge
- Basic command-line usage
- Environment variable configuration
- Git basics (for deployment)

---

## Required APIs & Services

### 1. Google AI Studio (Gemini API) - **REQUIRED**

The primary AI model for inventory reasoning.

| Detail | Value |
|--------|-------|
| **Purpose** | AI reasoning for inventory decisions |
| **Cost** | FREE (1,500 requests/day) |
| **Model Used** | gemini-1.5-flash |
| **Sign Up** | https://aistudio.google.com/app/apikey |

**Setup Steps:**
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and save it securely
5. Add to `.env` as `GOOGLE_API_KEY=your-key-here`

**Rate Limits:**
- Free tier: 1,500 requests/day, 15 requests/minute
- Paid tier: Unlimited (pay-as-you-go)

---

## Optional Integrations

### 2. Groq API (Llama 3.1) - **RECOMMENDED**

Backup AI model for failover when Gemini is unavailable.

| Detail | Value |
|--------|-------|
| **Purpose** | Backup LLM for high availability |
| **Cost** | FREE (rate-limited) |
| **Model Used** | llama-3.1-8b-instant |
| **Sign Up** | https://console.groq.com/keys |

**Setup Steps:**
1. Go to [Groq Console](https://console.groq.com/keys)
2. Create an account (email verification required)
3. Navigate to "API Keys" section
4. Generate a new API key
5. Add to `.env` as `GROQ_API_KEY=your-key-here`

**Why Use Groq?**
- Automatic failover if Gemini API is down
- Extremely fast inference (sub-100ms responses)
- Completely free with generous rate limits

---

### 3. Telegram Bot - **RECOMMENDED**

Mobile notifications with interactive approval buttons.

| Detail | Value |
|--------|-------|
| **Purpose** | Real-time mobile alerts |
| **Cost** | FREE (unlimited) |
| **Sign Up** | https://t.me/BotFather |

**Setup Steps:**
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Choose a name (e.g., "Inventory Agent")
4. Choose a username (must end in "bot", e.g., `myinventory_bot`)
5. Copy the token provided
6. Add to `.env` as `TELEGRAM_BOT_TOKEN=your-token-here`

**Features:**
- Real-time order notifications
- Inline "Approve" / "Reject" buttons
- Multi-user broadcasting (all registered users receive alerts)
- No configuration needed for end-users (they just click "Start")

---

### 4. Slack Webhook - **OPTIONAL**

Team channel notifications.

| Detail | Value |
|--------|-------|
| **Purpose** | Team channel alerts |
| **Cost** | FREE |
| **Sign Up** | Slack App Dashboard |

**Setup Steps:**
1. Go to [Slack API](https://api.slack.com/apps)
2. Create a new app
3. Enable "Incoming Webhooks"
4. Add to workspace and select channel
5. Copy webhook URL
6. Add to `.env` as `SLACK_WEBHOOK_URL=your-url-here`

---

### 5. ngrok - **DEVELOPMENT ONLY**

Expose localhost to the internet for testing webhooks.

| Detail | Value |
|--------|-------|
| **Purpose** | Local tunnel for Telegram webhooks |
| **Cost** | FREE (1 tunnel) |
| **Sign Up** | https://ngrok.com |

**Setup Steps:**
1. Download ngrok from https://ngrok.com/download
2. Unzip and run: `ngrok http 8000`
3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
4. Set `DASHBOARD_URL=https://abc123.ngrok.io` in `.env`

**Note:** ngrok URLs change on restart. Use a paid plan for static URLs.

---

## Database Options

The application uses SQLite by default, but can be adapted for production databases.

### Default: SQLite (Included)

| Detail | Value |
|--------|-------|
| **File** | `data/inventory.db` |
| **Cost** | FREE (embedded) |
| **Best For** | Development, single-server deployments |
| **Limitations** | No concurrent writes, single-file storage |

No setup required - works out of the box.

---

### Production Option 1: MongoDB Atlas

| Detail | Value |
|--------|-------|
| **Free Tier** | 512MB storage, shared cluster |
| **Cost** | FREE (M0 tier) |
| **Sign Up** | https://www.mongodb.com/cloud/atlas |
| **Best For** | Flexible schema, document storage |

**Setup Steps:**
1. Create account at MongoDB Atlas
2. Create a free M0 cluster
3. Add your IP to whitelist (or use `0.0.0.0/0` for any IP)
4. Create database user with password
5. Get connection string
6. Add to `.env` as `MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/inventory`

**Integration Code Required:** You would need to add `pymongo` to requirements and modify the data layer.

---

### Production Option 2: Supabase (PostgreSQL)

| Detail | Value |
|--------|-------|
| **Free Tier** | 500MB storage, 2GB bandwidth |
| **Cost** | FREE |
| **Sign Up** | https://supabase.com |
| **Best For** | SQL queries, real-time subscriptions |

**Setup Steps:**
1. Create project at Supabase
2. Go to Settings > Database
3. Copy the connection string
4. Add to `.env` as `DATABASE_URL=postgres://...`

**Integration Code Required:** Add `asyncpg` or `psycopg2` and use SQLAlchemy.

---

### Production Option 3: PlanetScale (MySQL)

| Detail | Value |
|--------|-------|
| **Free Tier** | 5GB storage, 1B row reads/month |
| **Cost** | FREE (Hobby plan) |
| **Sign Up** | https://planetscale.com |
| **Best For** | MySQL compatibility, serverless scaling |

---

### Production Option 4: Neon (PostgreSQL)

| Detail | Value |
|--------|-------|
| **Free Tier** | 512MB storage, autoscaling |
| **Cost** | FREE |
| **Sign Up** | https://neon.tech |
| **Best For** | Serverless PostgreSQL, auto-pause |

---

### Database Comparison Matrix

| Database | Free Storage | Concurrent Users | Serverless | Setup Difficulty |
|----------|-------------|------------------|------------|------------------|
| SQLite | Unlimited | 1 | No | None |
| MongoDB Atlas | 512MB | Unlimited | Yes | Easy |
| Supabase | 500MB | Unlimited | Yes | Easy |
| PlanetScale | 5GB | Unlimited | Yes | Medium |
| Neon | 512MB | Unlimited | Yes | Easy |

**Recommendation:** 
- **Development/Demo:** SQLite (default)
- **Production (small):** MongoDB Atlas or Supabase
- **Production (scale):** PlanetScale or Neon

---

## Step-by-Step Deployment

### Step 1: Clone Repository

```bash
git clone https://github.com/HemantSudarshan/Agentic-Inventory-Restocking-Servic.git
cd Agentic-Inventory-Restocking-Servic
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# REQUIRED
GOOGLE_API_KEY=your-gemini-api-key
API_KEY=your-secure-random-string

# RECOMMENDED
GROQ_API_KEY=your-groq-key
TELEGRAM_BOT_TOKEN=your-telegram-token

# PRODUCTION
DASHBOARD_URL=https://your-domain.com
DASHBOARD_PASSWORD=your-secure-password
```

### Step 4: Initialize Database

```bash
# Database auto-initializes on first run
python main.py
```

### Step 5: Verify Installation

1. Open browser: `http://localhost:8000`
2. Login with default password: `admin123`
3. Select a product and click "Run AI Analysis"
4. Verify you see valid results

---

## Environment Configuration

### Complete Environment Variables Reference

```env
# ============================================
# REQUIRED - Application will not start without these
# ============================================

# Google Gemini API Key (Primary AI)
GOOGLE_API_KEY=AIzaSy...your-key

# API Security Key (for /inventory-trigger endpoint)
API_KEY=your-random-secure-string-here

# ============================================
# RECOMMENDED - Enhances functionality
# ============================================

# Groq API Key (Backup AI - Llama 3.1)
GROQ_API_KEY=gsk_...your-key

# Telegram Bot Token (Mobile notifications)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...

# Telegram Fallback Chat ID (optional, for testing)
TELEGRAM_CHAT_ID=123456789

# ============================================
# PRODUCTION - Required for deployment
# ============================================

# Public URL (used in notification links)
DASHBOARD_URL=https://your-app.railway.app

# Dashboard Password (change from default!)
DASHBOARD_PASSWORD=your-secure-password

# ============================================
# OPTIONAL - Advanced configuration
# ============================================

# LLM Provider Selection: primary, backup, auto
LLM_PROVIDER=auto

# Logging Level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# Auto-execute Confidence Threshold (0.0 - 1.0)
CONFIDENCE_THRESHOLD=0.6

# Metrics Port (Prometheus)
METRICS_PORT=9090

# ============================================
# DATABASE - If using external database
# ============================================

# MongoDB
# MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/inventory

# PostgreSQL (Supabase/Neon)
# DATABASE_URL=postgres://user:pass@host:5432/inventory

# ============================================
# NOTIFICATIONS - Additional channels
# ============================================

# Slack Webhook URL
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

---

## Platform-Specific Guides

### Deploy to Railway (Recommended)

Railway offers the simplest deployment experience with automatic builds.

**Cost:** Free $5/month credit

**Steps:**
1. Push code to GitHub
2. Go to [railway.app](https://railway.app) and sign in with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Railway auto-detects Python and builds
6. Add environment variables in "Variables" tab:
   - `GOOGLE_API_KEY`
   - `API_KEY`
   - `DASHBOARD_URL` (use Railway-provided URL)
7. Deploy!

**Railway URL:** `https://your-app.up.railway.app`

---

### Deploy to Render

**Cost:** Free tier (512MB RAM, spins down after inactivity)

**Steps:**
1. Go to [render.com](https://render.com) and sign in
2. Create "New Web Service"
3. Connect GitHub repository
4. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
5. Add environment variables
6. Deploy

**Note:** Free tier spins down after 15 minutes of inactivity. First request takes ~30 seconds to wake.

---

### Deploy to Vercel

**Note:** Vercel is optimized for serverless functions. FastAPI works but requires configuration.

**Steps:**
1. Install Vercel CLI: `npm i -g vercel`
2. Create `vercel.json`:
```json
{
  "builds": [{"src": "main.py", "use": "@vercel/python"}],
  "routes": [{"src": "/(.*)", "dest": "main.py"}]
}
```
3. Run `vercel` and follow prompts

---

### Deploy with Docker

**Dockerfile** (included in repo):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```

**Build and Run:**
```bash
docker build -t inventory-agent .
docker run -d -p 8000:8000 --env-file .env --name inventory-agent inventory-agent
```

**Docker Compose** (optional):
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

---

### Deploy to AWS (ECS/Fargate)

1. Build Docker image
2. Push to ECR (Elastic Container Registry)
3. Create ECS Cluster
4. Create Task Definition with environment variables
5. Create Service with desired count

---

### Deploy to Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/inventory-agent

# Deploy
gcloud run deploy inventory-agent \
  --image gcr.io/PROJECT_ID/inventory-agent \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_API_KEY=xxx,API_KEY=xxx"
```

---

## Tips & Tricks

### 1. Secure Your API Key
Generate a strong, random API key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Test AI Reasoning Locally
Use curl to test without the dashboard:
```bash
curl -X POST http://localhost:8000/inventory-trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"product_id": "STEEL_SHEETS", "mode": "mock"}'
```

### 3. View Raw API Docs
Access Swagger UI at `/docs` for interactive API testing:
```
http://localhost:8000/docs
```

### 4. Debug LLM Responses
Set `LOG_LEVEL=DEBUG` to see full AI prompts and responses:
```env
LOG_LEVEL=DEBUG
```

### 5. Test Telegram Without Deploying
Use ngrok to expose localhost:
```bash
ngrok http 8000
# Update DASHBOARD_URL with ngrok URL
```

### 6. Bulk Test All Products
Script to test all products:
```python
import requests

products = [
    "STEEL_SHEETS", "ALUMINUM_BARS", "COPPER_WIRE",
    "PLASTIC_PELLETS", "TITANIUM_RODS", "RUBBER_SHEETS",
    "LEGACY_PARTS", "ELECTRONIC_COMPONENTS", "HOLIDAY_PACKAGING",
    "OFFICE_SUPPLIES", "CARBON_FIBER"
]

for product in products:
    resp = requests.post(
        "http://localhost:8000/inventory-trigger",
        json={"product_id": product, "mode": "mock"},
        headers={"X-API-Key": "your-api-key"}
    )
    print(f"{product}: {resp.json().get('recommended_action')}")
```

### 7. Monitor with Prometheus
Metrics available at `/metrics`:
```
http://localhost:9090/metrics
```

### 8. Custom Confidence Threshold
Adjust when orders require approval:
```env
CONFIDENCE_THRESHOLD=0.7  # Higher = more manual review
```

### 9. Add Custom Products
Edit `data/mock_inventory.csv` and `data/mock_demand.csv`:
```csv
# mock_inventory.csv
product_id,current_stock,lead_time_days,service_level,unit_price
NEW_PRODUCT,100,5,0.95,250
```

### 10. Backup Database
SQLite file can be copied directly:
```bash
cp data/inventory.db data/inventory_backup_$(date +%Y%m%d).db
```

---

## Troubleshooting

### "GOOGLE_API_KEY not found"
- Ensure `.env` file exists in project root
- Check for typos in variable name
- Restart the application after changes

### "401 Unauthorized" on API calls
- Verify `X-API-Key` header matches `API_KEY` in `.env`
- Check for trailing whitespace in the key

### "Gemini API rate limited"
- Wait 60 seconds (rate limit resets)
- Enable Groq backup: `LLM_PROVIDER=auto`

### Telegram bot not responding
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure you've started the bot (`/start` command)
- Check logs for errors

### Dashboard shows "Unknown" status
- Clear browser localStorage: `localStorage.clear()`
- Hard refresh: Ctrl+Shift+R

### Orders stuck in "pending"
- Low confidence orders require approval
- Use Telegram buttons or dashboard to approve

---

## Client Handover Checklist

Before handing over to a client, ensure:

### Documentation
- [ ] This deployment guide provided
- [ ] README.md reviewed
- [ ] API documentation (`/docs`) accessible

### Security
- [ ] Change default `DASHBOARD_PASSWORD`
- [ ] Generate unique `API_KEY`
- [ ] Remove any test/demo credentials

### Configuration
- [ ] All required API keys set
- [ ] `DASHBOARD_URL` set to production URL
- [ ] Telegram bot created (if using)

### Testing
- [ ] All 11 products tested successfully
- [ ] Notifications working (if configured)
- [ ] Login/logout flow verified

### Monitoring
- [ ] Health endpoint accessible (`/health`)
- [ ] Logs accessible on hosting platform
- [ ] Error alerts configured (if using Slack)

---

## Summary: Required vs Optional Services

### Minimum Viable Setup (Free)
| Service | Cost | Purpose |
|---------|------|---------|
| Google AI Studio | FREE | AI reasoning |
| Railway/Render | FREE | Hosting |

**Total Cost: $0/month**

### Recommended Setup (Free)
| Service | Cost | Purpose |
|---------|------|---------|
| Google AI Studio | FREE | Primary AI |
| Groq | FREE | Backup AI |
| Telegram | FREE | Notifications |
| Railway/Render | FREE | Hosting |

**Total Cost: $0/month**

### Production Setup
| Service | Cost | Purpose |
|---------|------|---------|
| Google AI Studio | FREE/$0.35/1M tokens | AI reasoning |
| Groq | FREE | Backup AI |
| Telegram | FREE | Mobile alerts |
| Slack | FREE | Team alerts |
| MongoDB Atlas | FREE/paid | Database |
| Railway | $5-20/month | Hosting |

**Total Cost: $5-25/month**

---

## Support & Contact

For issues or questions:
- GitHub Issues: [Repository Issues](https://github.com/HemantSudarshan/Agentic-Inventory-Restocking-Servic/issues)
- Documentation: See README.md

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-07  
**Author:** Agentic Inventory Restocking Service Team
