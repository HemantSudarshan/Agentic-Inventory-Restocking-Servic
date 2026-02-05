# Agentic Inventory Restocking Service - Implementation Plan

## Executive Summary

Build a **production-ready mini-service** that monitors inventory levels and uses an AI Agent to analyze demand forecasts and generate restock strategies or transfer orders.

---

## Phase 1: Problem Understanding

### Core Problem
An automated system that **detects low inventory → analyzes demand context → decides action → generates executable orders** without manual intervention for routine decisions.

### Sub-Problems
| Sub-Problem | Description |
|-------------|-------------|
| **Inventory Trigger** | Detect when stock falls below safety level |
| **Data Retrieval** | Query demand forecast data from CSV/database |
| **AI Reasoning** | Determine if shortage is crisis vs demand declining |
| **Action Generation** | Create Purchase Order or Transfer Order JSON |
| **Human Escalation** | Route low-confidence decisions for approval |

### Constraints
| Type | Constraint |
|------|------------|
| **Technical** | Python backend (FastAPI/Flask), SQLite/Pandas data source |
| **AI Orchestration** | LangGraph, CrewAI, or OpenAI Function Calling |
| **Model** | GPT-4o-mini, Gemini 2.5 Flash, or Llama 3 (cost-efficient) |
| **Budget** | <$0.01 per decision for production viability |

### Success Criteria
- ✅ Real-time inventory monitoring with configurable thresholds
- ✅ LLM-based reasoning that avoids overstock in declining demand
- ✅ Structured JSON output for Purchase Orders and Transfer Orders
- ✅ Confidence-based routing (auto-execute vs human review)
- ✅ <5 second latency per decision
- ✅ >85% decision accuracy

---

## Phase 2: Research & Assumption Analysis

### Validated Assumptions (from research docs)

| Assumption | Validation | Risk Level |
|------------|------------|------------|
| LangGraph handles workflow orchestration | ✅ Proven in JT_POC_master1 repo | Low |
| Gemini Flash is cost-efficient | ✅ $0.15/1M tokens, free tier available | Low |
| CSV caching reduces latency | ✅ 1-hour TTL recommended | Low |
| Safety stock formulas work | ✅ Standard inventory math (SS = Z × σ × √L) | Low |
| Prophet works for forecasting | ⚠️ Requires additional dependency, simple moving average sufficient for MVP | Medium |

### Dependencies
1. **LangGraph** - Workflow orchestration (proven pattern)
2. **FastAPI** - HTTP layer with async support
3. **Google Generative AI** - Gemini 2.5 Flash for reasoning
4. **Pandas** - CSV processing and caching
5. **SQLite** - Lightweight inventory storage
6. **Pydantic** - Schema validation

### Risky Assumptions Removed
- ❌ Prophet forecasting → Replaced with simple moving average for MVP
- ❌ Multi-warehouse coordination → Deferred to Phase 2
- ❌ Real-time streaming → Polling every 5 minutes sufficient

---

## Phase 3: Feasibility Validation

### Technical Viability ✅

| Component | Approach | Confidence |
|-----------|----------|------------|
| Backend | FastAPI (mature, async, production-proven) | Very High |
| Orchestration | LangGraph StateGraph (documented patterns available) | Very High |
| LLM | Gemini 2.5 Flash via langchain-google-genai | Very High |
| Data | Pandas + SQLite (standard Python) | Very High |

### Cost Analysis
| Item | Monthly Cost (1K decisions/day) |
|------|--------------------------------|
| Gemini Flash API | ~$0 (free tier: 15 RPM = 21,600/day) |
| Alternative: GPT-4o-mini | ~$22.50 |
| Hosting (basic VPS) | ~$5-20 |
| **Total** | **$5-45/month** |

---

## Phase 4: POC Design

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              AGENTIC INVENTORY RESTOCKING SERVICE           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  HTTP Layer: FastAPI                                        │
│  └── POST /inventory-trigger                                │
│  └── GET /health                                            │
│                                                             │
│  Workflow Layer (LangGraph - 6 Nodes):                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                │
│  │ Retrieve │ → │ Analyze  │ → │ Optimize │                │
│  │   Data   │   │  Demand  │   │Inventory │                │
│  └──────────┘   └──────────┘   └──────────┘                │
│        ↓              ↓              ↓                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                │
│  │  Assess  │ → │ Validate │ → │ Generate │                │
│  │   Risk   │   │ Decision │   │  Action  │                │
│  └──────────┘   └──────────┘   └──────────┘                │
│                       ↓                                     │
│              [Confidence Gate]                              │
│              ↓               ↓                              │
│         Auto-Execute    Human Review                        │
│                                                             │
│  Data Layer: SQLite + CSV                                   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

**INPUT:**
```json
{
  "product_id": "STEEL_SHEETS",
  "warehouse_id": "WH_BANGALORE",
  "current_stock": 150,
  "safety_stock_level": 300
}
```

**OUTPUT (Purchase Order):**
```json
{
  "po_number": "PO-20260204-STEEL_SHEETS",
  "type": "purchase_order",
  "status": "draft",
  "items": [{
    "material_id": "STEEL_SHEETS",
    "quantity": 2000,
    "required_by": "2026-02-18"
  }],
  "confidence_score": 0.92
}
```

---

## Phase 5: Step-by-Step Execution Plan

### Project Structure
```
inventory-agent/
├── main.py                 # FastAPI + LangGraph
├── agents/
│   ├── __init__.py
│   ├── retrieval_agent.py  # CSV loading
│   ├── reasoning_agent.py  # LLM decision
│   └── action_agent.py     # JSON generation
├── models/
│   ├── __init__.py
│   └── schemas.py          # Pydantic models
├── data/
│   ├── demand_forecast.csv
│   └── inventory.db
├── tests/
│   └── test_workflow.py
├── .env
└── requirements.txt
```

### Development Steps

| Step | Task | Files |
|------|------|-------|
| 1 | Project structure setup | All directories |
| 2 | Pydantic schemas | `models/schemas.py` |
| 3 | Data retrieval agent with caching | `agents/retrieval_agent.py` |
| 4 | LLM reasoning agent | `agents/reasoning_agent.py` |
| 5 | Action generation agent | `agents/action_agent.py` |
| 6 | LangGraph workflow | `main.py` |
| 7 | Unit and integration tests | `tests/test_workflow.py` |

---

## Phase 6: Technology Stack

### Core Stack (100% Open Source)

| Layer | Technology | License | Why |
|-------|------------|---------|-----|
| **HTTP** | FastAPI | MIT | Async, OpenAPI docs, battle-tested |
| **Orchestration** | LangGraph | MIT | Graph-based workflows, checkpointing |
| **LLM Client** | langchain-google-generativeai | MIT | Gemini Flash integration |
| **Data** | Pandas | BSD | DataFrame operations, CSV handling |
| **Database** | SQLite | Public Domain | Zero-config, embedded |
| **Validation** | Pydantic | MIT | Type-safe schemas |

### LLM Options

| Model | Cost/1M tokens | Recommended For |
|-------|----------------|-----------------|
| **Gemini 2.5 Flash** | $0.15 | Production (recommended) |
| GPT-4o-mini | $0.30 | Higher accuracy needs |
| Llama 3 (local) | $0 | Self-hosted, privacy |

---

## Proposed Changes

| Type | File | Description |
|------|------|-------------|
| [NEW] | `requirements.txt` | All dependencies |
| [NEW] | `models/schemas.py` | Pydantic models for type safety |
| [NEW] | `agents/retrieval_agent.py` | CSV loading with caching |
| [NEW] | `agents/reasoning_agent.py` | LLM decision making |
| [NEW] | `agents/action_agent.py` | JSON payload generator |
| [NEW] | `main.py` | FastAPI + LangGraph workflow |
| [NEW] | `data/demand_forecast.csv` | Sample data |
| [NEW] | `tests/test_workflow.py` | Unit and integration tests |

---

## Verification Plan

### Automated Tests

**Command to run all tests:**
```bash
cd inventory-agent
pytest tests/ -v
```

**Test Coverage:**
1. `test_retrieval_agent` - Validates CSV loading and trend detection
2. `test_reasoning_agent` - Validates LLM decision output schema
3. `test_action_agent` - Validates PO/Transfer JSON generation
4. `test_confidence_routing` - Validates approval gate logic
5. `test_full_workflow` - End-to-end integration test

### Manual Verification

1. **Start the server:**
   ```bash
   cd c:\Python Project\Agentic Inventory Restocking Service
   python main.py
   ```

2. **Test low stock scenario:**
   ```bash
   curl -X POST "http://localhost:8000/inventory-trigger" ^
     -H "Content-Type: application/json" ^
     -d "{\"product_id\":\"STEEL_SHEETS\",\"warehouse_id\":\"WH_BANGALORE\",\"current_stock\":150,\"safety_stock_level\":300}"
   ```

3. **Expected response should include:**
   - `"recommended_action": "restock"` or `"transfer"`
   - Valid JSON payload with quantity and dates
   - Confidence score between 0-1

4. **Check console logs** for workflow node execution

---

> [!IMPORTANT]
> This plan is ready for immediate implementation. All technologies are proven and open-source with extensive documentation.
