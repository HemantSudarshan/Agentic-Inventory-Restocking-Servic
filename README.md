# 🤖 Agentic Inventory Restocking Service

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![AI Powered](https://img.shields.io/badge/AI-Gemini%20%2B%20Llama-purple.svg)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **AI-Powered Inventory Management System** that analyzes demand forecasts and autonomously generates purchase orders or transfer requests with human oversight for critical decisions.

---

## 🌟 Overview

Instead of simple alerts when inventory runs low, this service uses **Large Language Models (LLMs)** to:
- **Analyze demand trends** (rising, falling, seasonal)
- **Determine crisis severity** (avoid overstock vs prevent stockouts)
- **Generate smart actions** (purchase orders or warehouse transfers)
- **Self-execute high-confidence orders** with human approval for uncertain cases

Built for **production environments** with enterprise-grade features: multi-channel notifications, audit trails, rate limiting, and real-time monitoring.

---

## 🚀 Key Features

### 🧠 AI-Powered Decision Making
- **Dual LLM System**: Gemini 2.0 Flash (primary) + Llama 3.3 70B (backup via Groq)
- **Automatic failover**: 99.9% uptime even if one provider is down
- **Confidence scoring**: Auto-execute high-confidence orders (≥0.6), flag low-confidence for human review
- **Context-aware reasoning**: Analyzes 7-day demand trends, lead times, and safety stock calculations

### 📊 Production-Ready Architecture
- **Async FastAPI**: Non-blocking I/O with thread pool offloading for heavy operations
- **Database persistence**: SQLite with full audit trail for compliance
- **Rate limiting**: Protects endpoints from abuse (10-60 req/min)
- **Multi-channel notifications**: Slack (enterprise teams) + Telegram (mobile alerts)
- **Batch processing**: Process up to 20 products in parallel
- **Real-time dashboard**: Monitor orders, approve/reject pending actions

### 🔒 Security & Reliability
- **API Key authentication**: Fail-closed security model
- **Input validation**: Strict Pydantic schema enforcement
- **Structured logging**: Production-ready with `structlog`
- **Health monitoring**: Prometheus metrics integration
- **CI/CD pipeline**: GitHub Actions with automated testing

---

## 📋 System Requirements

- **Python**: 3.11 or higher
- **OS**: Windows, macOS, Linux
- **API Keys** (free tiers available):
  - Google AI Studio (Gemini): [Get key](https://aistudio.google.com/app/apikey)
  - Groq (Llama backup): [Get key](https://console.groq.com/keys)

---

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/agentic-inventory-service.git
cd agentic-inventory-service
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Create a `.env` file:
```env
# LLM Configuration
GOOGLE_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
LLM_PROVIDER=auto  # auto, primary, or backup

# Security
API_KEY=dev-inventory-agent-2026

# Notifications (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Confidence Threshold (0.0 - 1.0)
CONFIDENCE_THRESHOLD=0.6
```

### 4. Initialize Database
```bash
python -c "from utils.database import init_database; import asyncio; asyncio.run(init_database())"
```

### 5. Run the Server
```bash
python -m uvicorn main:app --reload --port 8000
```

🎉 **Visit**: http://localhost:8000/dashboard

---

## 📡 API Usage

### Trigger Inventory Analysis
```bash
curl -X POST http://localhost:8000/inventory-trigger \
  -H "X-API-Key: dev-inventory-agent-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "STEEL_SHEETS",
    "mode": "mock"
  }'
```

**Response**:
```json
{
  "status": "executed",
  "safety_stock": 57.57,
  "reorder_point": 897.57,
  "current_stock": 150,
  "shortage": 747.57,
  "recommended_action": "restock",
  "recommended_quantity": 898,
  "confidence_score": 0.9,
  "order": {
    "id": "PO-20260206012356-STEEL_SHEETS",
    "type": "purchase_order",
    "items": [{"material_id": "STEEL_SHEETS", "quantity": 898}],
    "cost": 449000.0
  },
  "reasoning": "Current stock is critically low..."
}
```

### View Calculation Details
```bash
curl http://localhost:8000/verify-calculation/STEEL_SHEETS?mode=mock \
  -H "X-API-Key: dev-inventory-agent-2026"
```

### Batch Processing
```bash
curl -X POST http://localhost:8000/inventory-trigger-batch \
  -H "X-API-Key: dev-inventory-agent-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "products": ["STEEL_SHEETS", "COPPER_WIRE", "PLASTIC_PELLETS"],
    "mode": "mock"
  }'
```

---

## 🎨 Dashboard

Access the real-time monitoring dashboard at **http://localhost:8000/dashboard**

**Features**:
- 📊 Live statistics (Total Orders, Completed, Pending, Avg AI Score)
- 📋 Recent orders table with approve/reject actions
- 🎯 Quick trigger panel for manual requests
- 📈 Order distribution chart
- 🔍 Calculation verification modal

---

## 🏗️ Architecture

### Agentic Workflow (3 Steps)

```
┌─────────────────────────────────────────────────────────┐
│  1. DATA RETRIEVAL (agents/data_loader.py)             │
│  └─ Load mock demand forecast CSV                      │
│     • demand_history: [100, 120, 110, 130, ...]        │
│     • current_stock, lead_time, service_level          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  2. SAFETY CALCULATIONS (agents/safety_calculator.py)  │
│  └─ Statistical inventory optimization                  │
│     • Average demand & standard deviation              │
│     • Safety stock (Z-score × σ)                       │
│     • Reorder point (demand × lead time + SS)          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  3. AI REASONING (agents/reasoning_agent.py)           │
│  └─ LLM analyzes context and decides:                  │
│     • Is this a crisis or just demand dropping?        │
│     • Should we restock (PO) or transfer?             │
│     • How much to order?                               │
│     • Confidence score (0.0 - 1.0)                     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  4. ACTION GENERATION (agents/action_agent.py)         │
│  └─ Generate JSON payload:                             │
│     • Purchase Order (type: "purchase_order")          │
│     • Transfer Order (type: "transfer")                │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  5. ROUTING (main.py)                                  │
│  └─ Based on confidence:                               │
│     • High (≥0.6) → Auto-execute + Telegram notify     │
│     • Low (<0.6) → Pending + Slack alert + Human review│
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (async Python framework) |
| **AI/LLM** | LangChain + Gemini 2.0 Flash + Llama 3.3 70B |
| **Database** | SQLite (with aiosqlite for async) |
| **Caching** | functools.lru_cache |
| **Rate Limiting** | SlowAPI |
| **Monitoring** | Prometheus metrics |
| **Logging** | structlog |
| **Notifications** | Slack webhooks + Telegram Bot API |
| **Frontend** | Tailwind CSS + Chart.js + Lucide icons |
| **CI/CD** | GitHub Actions |

---

## 📂 Project Structure

```
agentic-inventory-service/
├── agents/                  # Core agentic logic
│   ├── data_loader.py       # CSV & API data retrieval
│   ├── safety_calculator.py # Statistical inventory formulas
│   ├── reasoning_agent.py   # LLM decision-making
│   └── action_agent.py      # Order generation
├── models/
│   └── schemas.py           # Pydantic models for validation
├── utils/                   # Infrastructure utilities
│   ├── database.py          # SQLite persistence
│   ├── logging.py           # Structured logging setup
│   ├── rate_limiter.py      # API rate limiting
│   ├── metrics.py           # Prometheus metrics
│   ├── notifications.py     # Slack & webhook integration
│   └── telegram.py          # Telegram bot notifications
├── data/
│   ├── mock_inventory.csv   # Product catalog
│   └── mock_demand.csv      # 7-day demand history
├── static/
│   └── dashboard.html       # Real-time monitoring UI
├── tests/                   # Unit & integration tests
├── main.py                  # FastAPI application
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🧪 Testing

### Run Unit Tests
```bash
pytest tests/ -v
```

### Test Coverage
```bash
pytest tests/ --cov=. --cov-report=html
```

### Integration Testing
```bash
# Test with real LLM (requires API keys)
pytest tests/test_workflow.py -v -s
```

---

## 🔔 Notification Setup

### Slack Integration
1. Create a Slack webhook: https://api.slack.com/messaging/webhooks
2. Add to `.env`: `SLACK_WEBHOOK_URL=https://hooks.slack.com/...`
3. Low-confidence orders auto-send to Slack with approve/reject buttons

### Telegram Integration
1. Create bot via @BotFather on Telegram → `/newbot`
2. Get your Chat ID from @userinfobot
3. Add to `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=1234567890:ABC...
   TELEGRAM_CHAT_ID=123456789
   ```
4. All executed orders send Telegram notifications

---

## 📈 Monitoring

### Prometheus Metrics
Available at: http://localhost:8000/metrics

**Key Metrics**:
- `inventory_trigger_total` - Total API calls
- `orders_generated_total` - Orders by type (PO/Transfer)
- `llm_calls_total` - LLM usage by provider
- `current_safety_stock` - Real-time safety stock levels
- `inventory_shortage_total` - Shortage events

### Dashboard Stats
- Total Orders (all-time)
- Completed vs Pending
- Average AI Confidence Score
- Recent order activity

---

## 🚢 Deployment

### Docker (Recommended)
```bash
docker build -t inventory-agent .
docker run -p 8000:8000 --env-file .env inventory-agent
```

### Google Cloud Run
```bash
gcloud run deploy inventory-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

### Railway / Render
1. Connect GitHub repository
2. Set environment variables in dashboard
3. Deploy with one click

---

## 🔐 Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` as template
2. **Rotate API keys regularly** - Especially for production
3. **Use strong API_KEY** - Generate with `openssl rand -hex 32`
4. **Enable HTTPS** - Use reverse proxy (nginx/Caddy) in production
5. **Monitor audit logs** - Check `data/inventory.db` → `audit_log` table

---

## 🛠️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | - | Gemini API key (required) |
| `GROQ_API_KEY` | - | Groq API key (optional, for backup) |
| `LLM_PROVIDER` | `auto` | `auto`, `primary`, or `backup` |
| `API_KEY` | - | Protect endpoints (required for production) |
| `CONFIDENCE_THRESHOLD` | `0.6` | Auto-execute threshold (0.0 - 1.0) |
| `SLACK_WEBHOOK_URL` | - | Slack notifications (optional) |
| `TELEGRAM_BOT_TOKEN` | - | Telegram bot token (optional) |
| `TELEGRAM_CHAT_ID` | - | Telegram chat ID (optional) |

---

## 🐛 Troubleshooting

### Issue: "LLM_PROVIDER not configured"
**Solution**: Add `GOOGLE_API_KEY` to `.env` file

### Issue: "403 Forbidden" on API calls
**Solution**: Include `X-API-Key` header with your API key

### Issue: Server won't start
**Solution**: Check `uvicorn main:app --reload` logs, ensure port 8000 is free

### Issue: No Telegram notifications
**Solution**: Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`, restart server

---

## 🎯 Future Enhancements

### Phase 4: Advanced AI Features
- [ ] **Multi-product optimization** - Holistic inventory planning across all SKUs
- [ ] **Seasonal forecasting** - ARIMA/Prophet models for demand prediction
- [ ] **Cost optimization** - Factor in supplier pricing, shipping costs, volume discounts
- [ ] **Supplier recommendation** - AI suggests best vendor based on pricing, lead time, reliability
- [ ] **Anomaly detection** - Alert on unusual demand spikes/drops

### Phase 5: Enterprise Integration
- [ ] **ERP connectors** - SAP, Oracle, NetSuite integration
- [ ] **Real-time data sync** - WebSocket streams from warehouse systems
- [ ] **Multi-warehouse support** - Global inventory visibility and transfers
- [ ] **Role-based access control (RBAC)** - Approver workflows, audit trails
- [ ] **Email notifications** - SendGrid/SES integration

### Phase 6: Advanced UI/UX
- [ ] **React/Vue dashboard** - Modern SPA with real-time updates
- [ ] **Mobile app** - React Native/Flutter for on-the-go approvals
- [ ] **Data visualization** - Advanced charts (demand trends, stock levels over time)
- [ ] **Approval workflows** - Multi-level approval chains for large orders
- [ ] **Dark mode** - User preference toggle

### Phase 7: AI Model Improvements
- [ ] **Fine-tuned models** - Train on company-specific inventory data
- [ ] **Multi-agent collaboration** - Separate agents for demand forecasting, pricing, supplier selection
- [ ] **Reinforcement learning** - Learn from past order outcomes to improve recommendations
- [ ] **Natural language queries** - "Show me all products below safety stock with rising demand"

### Phase 8: Scalability & Performance
- [ ] **Redis caching** - Distributed cache for high-traffic scenarios
- [ ] **PostgreSQL migration** - Scale beyond SQLite for enterprise workloads
- [ ] **Horizontal scaling** - Kubernetes deployment with load balancing
- [ ] **Message queue** - RabbitMQ/Kafka for async order processing
- [ ] **CDN integration** - Cloudflare for static assets

---

## 👨‍💻 Author

**Hemant Sudarshan**  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat&logo=linkedin)](https://www.linkedin.com/in/hemant-sudarshan-01633928a/)

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google AI Studio** - Gemini 2.0 Flash API
- **Groq** - Lightning-fast Llama 3.3 70B inference
- **FastAPI** - Modern Python web framework
- **LangChain** - LLM orchestration toolkit
- **Tailwind CSS** - Utility-first CSS framework

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/agentic-inventory-service/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/agentic-inventory-service/discussions)
- **Email**: hemant.sudarshan@example.com

---

**⭐ Star this repo if you find it helpful!**

Built with ❤️ using AI, FastAPI, and Python
