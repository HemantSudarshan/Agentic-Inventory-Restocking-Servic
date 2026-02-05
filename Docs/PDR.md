# Project Design Review (PDR)
## Agentic Inventory Restocking Service

---

## 📋 Document Overview

| Field | Value |
|-------|-------|
| **Project** | Agentic Inventory Restocking Service |
| **Version** | 1.0 |
| **Date** | 2026-02-05 |
| **Status** | Ready for Implementation |
| **Delivery Timeline** | 2 Weeks |
| **Monthly Cost** | $0-45 |

---

## 1. Executive Summary

This service is an **AI-powered inventory management agent** that:
- Monitors inventory levels against dynamically calculated safety thresholds
- Uses Gemini LLM for intelligent restock/transfer decisions
- Supports both **mock data** (for testing) and **real input data** (for production)
- Routes decisions based on confidence scores (auto-execute vs human review)

---

## 2. Problem Statement

### 2.1 Core Problems to Solve

| # | Problem | Solution | When |
|---|---------|----------|------|
| 0 | Load Data | CSV/API data loading | First |
| 1 | Calculate Safety Stock | `SS = Z × σ × √L` formula | Before trigger |
| 2 | Detect Low Inventory | `current_stock < ROP` | Trigger point |
| 3 | Get Demand Forecast | Trend analysis from data | After trigger |
| 4 | AI Reasoning | Gemini LLM decision | Core logic |
| 5 | Generate Action | PO or Transfer JSON | Output |
| 6 | Route by Confidence | Auto-execute or review | Final step |

### 2.2 Key Formulas

```
Safety Stock (SS) = Z × σ × √L

Where:
  Z = Service level factor (1.65 for 95%, 2.33 for 99%)
  σ = Standard deviation of daily demand
  L = Lead time in days

Reorder Point (ROP) = (Avg Daily Demand × Lead Time) + Safety Stock

Trigger Condition:
  IF current_stock < ROP → INITIATE RESTOCK WORKFLOW
```

**Example Calculation:**
- Avg demand = 100 units/day, Std dev = 20 units, Lead time = 7 days
- SS = 1.65 × 20 × √7 = **87 units**
- ROP = (100 × 7) + 87 = **787 units**
- If current_stock = 150 → **TRIGGER** (150 < 787)

---

## 3. System Architecture

### 3.1 Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     SYSTEM WORKFLOW                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE 1: Data Loading                                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Load    │ →  │ Calculate│ →  │  Store   │              │
│  │  Data    │    │ Safety   │    │Thresholds│              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       ↓                                                      │
│  PHASE 2: Monitoring                                         │
│  ┌──────────┐                                                │
│  │  Detect  │ → stock < ROP? → YES → Trigger Agent          │
│  │Low Stock │                → NO  → Continue monitoring    │
│  └──────────┘                                                │
│       ↓                                                      │
│  PHASE 3: Agent Workflow                                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐               │
│  │Analyze │→│Optimize│→│Validate│→│Generate│               │
│  │ Demand │ │  Qty   │ │Decision│ │ Action │               │
│  └────────┘ └────────┘ └────────┘ └────────┘               │
│                              ↓                               │
│                    [Confidence Gate]                         │
│                    ↓              ↓                          │
│             Auto-Execute    Human Review                     │
│             (≥0.6)          (<0.6)                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 LangGraph Node Flow (6 Nodes)

| Node | Function | Input | Output |
|------|----------|-------|--------|
| 1. `data_loader` | Load inventory + demand data | product_id, mode | Raw data |
| 2. `safety_calculator` | Calculate SS, ROP | Demand history | Thresholds |
| 3. `trigger_detector` | Check if restock needed | Current stock, ROP | Boolean |
| 4. `reasoning_agent` | LLM decision making | All context | Recommendation |
| 5. `action_agent` | Generate PO/Transfer JSON | Recommendation | Order JSON |
| 6. `confidence_router` | Route based on confidence | Confidence score | Execution path |

---

## 4. Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| HTTP API | FastAPI | Latest |
| Orchestration | LangGraph | Latest |
| LLM (Primary) | Gemini 2.0 Flash | Latest |
| LLM (Backup) | Groq (llama-3.3-70b) | Free Tier |
| Data Processing | Pandas | Latest |
| Local Storage | SQLite | 3.x |
| Logging | structlog | Latest |
| Metrics | prometheus-client | Latest |
| Retry Logic | tenacity | Latest |

### 4.1 LLM Failover Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                   LLM FAILOVER CHAIN                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Request → [Primary: Gemini 2.0 Flash]                      │
│                    ↓                                         │
│            Success? → YES → Return response                  │
│                    ↓                                         │
│                   NO (Rate limit / Error)                    │
│                    ↓                                         │
│            [Backup: Groq llama-3.3-70b-versatile]           │
│                    ↓                                         │
│            Success? → YES → Return response                  │
│                    ↓                                         │
│                   NO → Raise error                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

| Provider | Model | Free Tier | Speed | Use Case |
|----------|-------|-----------|-------|----------|
| **Gemini** | gemini-2.0-flash | Yes (generous) | Fast | Primary |
| **Groq** | llama-3.3-70b-versatile | Yes (30 RPM) | Very Fast | Backup |

---

## 5. Project Structure

```
inventory-agent/
├── main.py                     # FastAPI + LangGraph workflow
├── agents/
│   ├── __init__.py
│   ├── data_loader.py          # Mock + Input data handling
│   ├── safety_calculator.py    # Safety stock formulas (SS, ROP, EOQ)
│   ├── reasoning_agent.py      # Gemini LLM integration
│   └── action_agent.py         # PO/Transfer JSON generation
├── models/
│   ├── __init__.py
│   └── schemas.py              # Pydantic models
├── utils/
│   ├── __init__.py
│   ├── logging.py              # structlog configuration
│   ├── metrics.py              # Prometheus counters
│   └── retry.py                # tenacity error handling
├── data/
│   ├── mock_inventory.csv      # Sample inventory data
│   └── mock_demand.csv         # Sample demand history
├── tests/
│   ├── __init__.py
│   ├── test_safety_calc.py     # Formula validation tests
│   ├── test_data_loader.py     # Data loading tests
│   ├── test_reasoning_agent.py # LLM tests
│   ├── test_action_agent.py    # JSON generation tests
│   └── test_workflow.py        # Full integration tests
├── .env.example                # Environment template
├── requirements.txt            # All dependencies
└── README.md                   # Setup + usage guide
```

---

## 6. API Specification

### 6.1 Main Endpoint: `POST /inventory-trigger`

#### Request - Mock Mode (Development/Testing)
```json
{
  "product_id": "STEEL_SHEETS",
  "mode": "mock"
}
```

#### Request - Input Mode (Production)
```json
{
  "product_id": "STEEL_SHEETS",
  "mode": "input",
  "current_stock": 150,
  "demand_history": [100, 120, 110, 130, 125, 115, 140],
  "lead_time_days": 7,
  "service_level": 0.95,
  "unit_price": 500
}
```

#### Success Response
```json
{
  "status": "executed",
  "safety_stock": 87,
  "reorder_point": 787,
  "current_stock": 150,
  "shortage": 637,
  "recommended_action": "restock",
  "recommended_quantity": 2000,
  "confidence_score": 0.92,
  "order": {
    "po_number": "PO-20260205-STEEL_SHEETS",
    "type": "purchase_order",
    "items": [{"material_id": "STEEL_SHEETS", "quantity": 2000}]
  },
  "reasoning": "Stock 637 units below ROP, demand trend increasing"
}
```

#### Error Response
```json
{
  "status": "error",
  "error_code": "INVALID_INPUT",
  "message": "demand_history must have at least 3 data points",
  "details": {
    "field": "demand_history",
    "provided": 2,
    "required": 3
  }
}
```

### 6.2 Debug Endpoint: `GET /debug/{product_id}`

```bash
GET /debug/STEEL_SHEETS?mode=mock
```

**Response:**
```json
{
  "product_id": "STEEL_SHEETS",
  "mode": "mock",
  "calculations": {
    "avg_daily_demand": 100,
    "std_dev": 20,
    "safety_stock": 87,
    "reorder_point": 787
  },
  "current_status": {
    "current_stock": 150,
    "shortage": 637
  },
  "would_trigger": true,
  "trigger_reason": "current_stock (150) < reorder_point (787)"
}
```

### 6.3 Metrics Endpoint: `GET /metrics`

Returns Prometheus-format metrics for monitoring.

---

## 7. Implementation Guide - Week by Week

---

### 📅 WEEK 1: Core Implementation

---

#### Day 1: Project Setup + Data Models

**Objective:** Create project foundation and define data structures.

| # | Task | File | Description |
|---|------|------|-------------|
| 1 | Create folder structure | All directories | Create `agents/`, `models/`, `utils/`, `data/`, `tests/` |
| 2 | Dependencies | `requirements.txt` | List all pip packages |
| 3 | Data Models | `models/schemas.py` | Define Pydantic models |
| 4 | Environment | `.env.example` | Template for API keys |

**`requirements.txt` Content:**
```
fastapi>=0.109.0
uvicorn>=0.27.0
langgraph>=0.0.26
langchain-google-genai>=0.0.6
langchain-groq>=0.1.0
groq>=0.4.0
pandas>=2.1.0
numpy>=1.26.0
scipy>=1.11.0
pydantic>=2.5.0
structlog>=24.1.0
prometheus_client>=0.19.0
tenacity>=8.2.0
python-dotenv>=1.0.0
pytest>=7.4.0
pytest-cov>=4.1.0
httpx>=0.26.0
```

**`models/schemas.py` Key Models:**
```python
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class InventoryRequest(BaseModel):
    product_id: str
    mode: Literal["mock", "input"] = "mock"
    current_stock: Optional[int] = None
    demand_history: Optional[List[float]] = None
    lead_time_days: Optional[int] = None
    service_level: Optional[float] = Field(default=0.95, ge=0.5, le=0.99)
    unit_price: Optional[float] = None

class SafetyParams(BaseModel):
    safety_stock: float
    reorder_point: float
    avg_demand: float
    std_dev: float

class OrderAction(BaseModel):
    po_number: str
    type: Literal["purchase_order", "transfer"]
    items: List[dict]
    created_at: datetime = Field(default_factory=datetime.now)

class InventoryResponse(BaseModel):
    status: Literal["executed", "pending_review", "error"]
    safety_stock: float
    reorder_point: float
    current_stock: int
    shortage: float
    recommended_action: str
    recommended_quantity: int
    confidence_score: float
    order: Optional[OrderAction] = None
    reasoning: str
```

**`.env.example` Content:**
```
# Primary LLM - Gemini (get from https://aistudio.google.com/app/apikey)
GOOGLE_API_KEY=your_gemini_api_key_here

# Backup LLM - Groq (get from https://console.groq.com/keys - FREE!)
GROQ_API_KEY=your_groq_api_key_here

# LLM Selection (primary, backup, or auto)
LLM_PROVIDER=auto

LOG_LEVEL=INFO
METRICS_PORT=9090
```

---

#### Day 2: Data Layer + Safety Calculation

**Objective:** Implement data loading and safety stock calculations.

| # | Task | File | Description |
|---|------|------|-------------|
| 1 | Data Loader | `agents/data_loader.py` | Mock + input mode handling |
| 2 | Safety Calculator | `agents/safety_calculator.py` | SS, ROP, EOQ formulas |
| 3 | Mock Data | `data/mock_inventory.csv` | Sample inventory |
| 4 | Mock Data | `data/mock_demand.csv` | Sample demand history |
| 5 | Unit Tests | `tests/test_safety_calc.py` | Formula validation |

**`agents/data_loader.py` Implementation:**
```python
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from models.schemas import InventoryRequest

DATA_DIR = Path(__file__).parent.parent / "data"

def load_data(request: InventoryRequest) -> Dict[str, Any]:
    """Load data based on mode (mock or input)."""
    if request.mode == "mock":
        return load_mock_data(request.product_id)
    else:
        return request.model_dump()

def load_mock_data(product_id: str) -> Dict[str, Any]:
    """Load mock data from CSV files."""
    inventory = pd.read_csv(DATA_DIR / "mock_inventory.csv")
    demand = pd.read_csv(DATA_DIR / "mock_demand.csv")
    
    product_inv = inventory[inventory["product_id"] == product_id].iloc[0]
    product_demand = demand[demand["product_id"] == product_id]["quantity"].tolist()
    
    return {
        "product_id": product_id,
        "current_stock": int(product_inv["current_stock"]),
        "demand_history": product_demand,
        "lead_time_days": int(product_inv["lead_time_days"]),
        "service_level": float(product_inv["service_level"]),
        "unit_price": float(product_inv.get("unit_price", 100))
    }
```

**`agents/safety_calculator.py` Implementation:**
```python
import math
from scipy.stats import norm
from typing import Tuple
import numpy as np

def calculate_safety_stock(std_dev: float, lead_time: int, service_level: float = 0.95) -> float:
    """
    Calculate Safety Stock using formula: SS = Z × σ × √L
    
    Args:
        std_dev: Standard deviation of daily demand
        lead_time: Lead time in days
        service_level: Service level (0.95 = 95%)
    
    Returns:
        Safety stock quantity
    """
    z = norm.ppf(service_level)  # 1.65 for 95%, 2.33 for 99%
    return z * std_dev * math.sqrt(lead_time)

def calculate_reorder_point(avg_demand: float, lead_time: int, safety_stock: float) -> float:
    """
    Calculate Reorder Point: ROP = (Avg Daily Demand × Lead Time) + Safety Stock
    """
    return (avg_demand * lead_time) + safety_stock

def calculate_eoq(annual_demand: float, order_cost: float, holding_cost: float) -> float:
    """
    Calculate Economic Order Quantity (optional optimization).
    EOQ = √((2 × D × S) / H)
    """
    return math.sqrt((2 * annual_demand * order_cost) / holding_cost)

def process_inventory_data(demand_history: list, lead_time: int, service_level: float) -> Tuple[float, float, float, float]:
    """
    Process demand history and calculate all safety parameters.
    
    Returns:
        (avg_demand, std_dev, safety_stock, reorder_point)
    """
    avg_demand = np.mean(demand_history)
    std_dev = np.std(demand_history)
    safety_stock = calculate_safety_stock(std_dev, lead_time, service_level)
    reorder_point = calculate_reorder_point(avg_demand, lead_time, safety_stock)
    
    return avg_demand, std_dev, safety_stock, reorder_point
```

**`data/mock_inventory.csv` Sample:**
```csv
product_id,current_stock,lead_time_days,service_level,unit_price
STEEL_SHEETS,150,7,0.95,500
ALUMINUM_BARS,300,5,0.95,350
COPPER_WIRE,80,10,0.99,1200
PLASTIC_PELLETS,500,3,0.90,50
```

**`data/mock_demand.csv` Sample:**
```csv
product_id,date,quantity
STEEL_SHEETS,2026-01-01,100
STEEL_SHEETS,2026-01-02,120
STEEL_SHEETS,2026-01-03,110
STEEL_SHEETS,2026-01-04,130
STEEL_SHEETS,2026-01-05,125
STEEL_SHEETS,2026-01-06,115
STEEL_SHEETS,2026-01-07,140
```

**`tests/test_safety_calc.py`:**
```python
import pytest
from agents.safety_calculator import (
    calculate_safety_stock,
    calculate_reorder_point,
    process_inventory_data
)

def test_safety_stock_95_service_level():
    """Test SS calculation at 95% service level."""
    ss = calculate_safety_stock(std_dev=20, lead_time=7, service_level=0.95)
    assert 85 < ss < 90  # Should be ~87 units

def test_reorder_point():
    """Test ROP calculation."""
    rop = calculate_reorder_point(avg_demand=100, lead_time=7, safety_stock=87)
    assert rop == 787

def test_process_inventory_data():
    """Test full processing pipeline."""
    demand = [100, 120, 110, 130, 125, 115, 140]
    avg, std, ss, rop = process_inventory_data(demand, lead_time=7, service_level=0.95)
    
    assert 110 < avg < 130  # Average should be ~120
    assert std > 0
    assert ss > 0
    assert rop > ss
```

---

#### Day 3: Reasoning Agent

**Objective:** Implement Gemini LLM integration for decision-making.

| # | Task | File | Description |
|---|------|------|-------------|
| 1 | LLM Agent | `agents/reasoning_agent.py` | Gemini integration |
| 2 | Prompts | Embedded in agent | Restock/transfer templates |
| 3 | Test | Manual | Verify LLM connection |

**`agents/reasoning_agent.py` Implementation (with Backup LLM):**
```python
import os
import json
from typing import Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential
from utils.logging import get_logger

logger = get_logger(__name__)

RESTOCK_PROMPT = """You are an inventory management AI agent. Analyze the following inventory situation and recommend an action.

## Current Status:
- Product: {product_id}
- Current Stock: {current_stock} units
- Safety Stock: {safety_stock:.0f} units
- Reorder Point: {reorder_point:.0f} units
- Shortage: {shortage:.0f} units below ROP
- Average Daily Demand: {avg_demand:.0f} units
- Lead Time: {lead_time_days} days

## Demand Trend (last 7 days):
{demand_history}

## Your Task:
1. Analyze if restocking is needed
2. Recommend: "restock" (purchase order) or "transfer" (from other warehouse)
3. Calculate optimal quantity to order
4. Provide confidence score (0.0 to 1.0)

## Response Format (JSON only, no markdown):
{{
    "action": "restock" or "transfer",
    "quantity": <number>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
}}
"""


class LLMProvider:
    """LLM Provider with automatic failover support."""
    
    def __init__(self):
        self.provider_mode = os.getenv("LLM_PROVIDER", "auto")  # auto, primary, backup
        self._primary_llm = None
        self._backup_llm = None
    
    @property
    def primary(self):
        """Lazy-load Gemini (primary LLM)."""
        if self._primary_llm is None:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                self._primary_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=api_key,
                    temperature=0.3
                )
        return self._primary_llm
    
    @property
    def backup(self):
        """Lazy-load Groq (backup LLM) - FREE and stable."""
        if self._backup_llm is None:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                self._backup_llm = ChatGroq(
                    model="llama-3.3-70b-versatile",
                    groq_api_key=api_key,
                    temperature=0.3
                )
        return self._backup_llm
    
    def get_llm_chain(self):
        """
        Get ordered list of LLMs to try based on provider mode.
        
        Returns:
            List of (name, llm) tuples in order of preference
        """
        if self.provider_mode == "primary":
            return [("gemini", self.primary)] if self.primary else []
        elif self.provider_mode == "backup":
            return [("groq", self.backup)] if self.backup else []
        else:  # auto - try primary, fallback to backup
            chain = []
            if self.primary:
                chain.append(("gemini", self.primary))
            if self.backup:
                chain.append(("groq", self.backup))
            return chain


class ReasoningAgent:
    """Reasoning agent with automatic LLM failover."""
    
    def __init__(self):
        self.llm_provider = LLMProvider()
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Extract and parse JSON from LLM response."""
        # Remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        # Find JSON object
        start = content.find("{")
        end = content.rfind("}") + 1
        
        if start == -1 or end == 0:
            raise ValueError("No JSON object found in response")
        
        json_str = content[start:end]
        return json.loads(json_str)
    
    async def _call_llm(self, llm, prompt: str, llm_name: str) -> Optional[Dict[str, Any]]:
        """
        Call a single LLM with retry logic.
        
        Returns:
            Parsed response or None if failed
        """
        try:
            logger.info(f"Calling LLM", provider=llm_name)
            response = await llm.ainvoke(prompt)
            result = self._parse_json_response(response.content)
            logger.info(f"LLM call successful", provider=llm_name)
            return result
        except Exception as e:
            logger.warning(f"LLM call failed", provider=llm_name, error=str(e))
            return None
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze inventory context with automatic failover.
        
        Tries primary LLM first (Gemini), falls back to backup (Groq) on failure.
        """
        prompt = RESTOCK_PROMPT.format(**context)
        llm_chain = self.llm_provider.get_llm_chain()
        
        if not llm_chain:
            raise ValueError("No LLM providers configured. Check GOOGLE_API_KEY or GROQ_API_KEY.")
        
        last_error = None
        for llm_name, llm in llm_chain:
            result = await self._call_llm(llm, prompt, llm_name)
            if result:
                # Add metadata about which LLM was used
                result["_llm_provider"] = llm_name
                return result
        
        # All LLMs failed
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


# --- Standalone functions for testing ---
async def analyze_with_gemini(context: Dict[str, Any]) -> Dict[str, Any]:
    """Direct Gemini call (for testing)."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.3
    )
    prompt = RESTOCK_PROMPT.format(**context)
    response = await llm.ainvoke(prompt)
    return json.loads(response.content[response.content.find("{"):response.content.rfind("}")+1])


async def analyze_with_groq(context: Dict[str, Any]) -> Dict[str, Any]:
    """Direct Groq call (for testing) - FREE!"""
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3
    )
    prompt = RESTOCK_PROMPT.format(**context)
    response = await llm.ainvoke(prompt)
    return json.loads(response.content[response.content.find("{"):response.content.rfind("}")+1])
```

> [!TIP]
> **Getting Groq API Key (FREE):**
> 1. Go to https://console.groq.com/keys
> 2. Sign up with Google/GitHub (free)
> 3. Create API key → Copy to `.env`
> 4. Free tier: 30 requests/minute, 6000 requests/day

---

#### Day 4: Action Agent + Utilities

**Objective:** Implement action generation and utility functions.

| # | Task | File | Description |
|---|------|------|-------------|
| 1 | Action Agent | `agents/action_agent.py` | PO/Transfer JSON generation |
| 2 | Logging | `utils/logging.py` | structlog setup |
| 3 | Retry | `utils/retry.py` | Error handling |
| 4 | Metrics | `utils/metrics.py` | Prometheus counters |

**`agents/action_agent.py` Implementation:**
```python
from datetime import datetime
from typing import Dict, Any
from models.schemas import OrderAction

def generate_action(product_id: str, recommendation: Dict[str, Any]) -> OrderAction:
    """
    Generate PO or Transfer order based on recommendation.
    """
    action_type = recommendation["action"]
    quantity = recommendation["quantity"]
    
    if action_type == "restock":
        return OrderAction(
            po_number=f"PO-{datetime.now().strftime('%Y%m%d')}-{product_id}",
            type="purchase_order",
            items=[{"material_id": product_id, "quantity": quantity}]
        )
    else:
        return OrderAction(
            po_number=f"TR-{datetime.now().strftime('%Y%m%d')}-{product_id}",
            type="transfer",
            items=[{"material_id": product_id, "quantity": quantity, "source": "WAREHOUSE_B"}]
        )
```

**`utils/logging.py` Implementation:**
```python
import structlog
import logging
import os

def setup_logging():
    """Configure structured logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logging.basicConfig(format="%(message)s", level=getattr(logging, log_level))

def get_logger(name: str):
    """Get a structured logger."""
    return structlog.get_logger(name)
```

**`utils/metrics.py` Implementation:**
```python
from prometheus_client import Counter, Histogram, generate_latest

# Metrics
REQUEST_COUNT = Counter(
    "inventory_requests_total",
    "Total inventory trigger requests",
    ["mode", "status"]
)

DECISION_COUNT = Counter(
    "inventory_decisions_total",
    "Total inventory decisions",
    ["action", "auto_executed"]
)

PROCESSING_TIME = Histogram(
    "inventory_processing_seconds",
    "Time to process inventory request",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

def record_request(mode: str, status: str):
    REQUEST_COUNT.labels(mode=mode, status=status).inc()

def record_decision(action: str, auto_executed: bool):
    DECISION_COUNT.labels(action=action, auto_executed=str(auto_executed)).inc()

def get_metrics():
    return generate_latest()
```

**`utils/retry.py` Implementation:**
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from functools import wraps

def with_retry(max_attempts: int = 3, min_wait: int = 1, max_wait: int = 10):
    """Decorator for retry logic with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(Exception)
    )
```

---

#### Day 5: Main Workflow

**Objective:** Integrate everything into FastAPI + LangGraph workflow.

| # | Task | File | Description |
|---|------|------|-------------|
| 1 | Main App | `main.py` | FastAPI + LangGraph |
| 2 | 6-Node Workflow | `main.py` | Full agent orchestration |
| 3 | Confidence Routing | `main.py` | Auto-execute vs review |
| 4 | Mode Switching | `main.py` | Mock/input handling |
| 5 | E2E Test | Manual | End-to-end verification |

**`main.py` Implementation:**
```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
import numpy as np
from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from models.schemas import InventoryRequest, InventoryResponse
from agents.data_loader import load_data
from agents.safety_calculator import process_inventory_data
from agents.reasoning_agent import ReasoningAgent
from agents.action_agent import generate_action
from utils.logging import setup_logging, get_logger
from utils.metrics import record_request, record_decision, get_metrics, PROCESSING_TIME

load_dotenv()
setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Inventory Restocking Agent", version="1.0.0")

# --- State Definition ---
class AgentState(TypedDict):
    request: InventoryRequest
    data: Dict[str, Any]
    safety_params: Dict[str, float]
    needs_restock: bool
    recommendation: Dict[str, Any]
    order: Dict[str, Any]
    response: InventoryResponse

# --- Node Functions ---
def load_data_node(state: AgentState) -> AgentState:
    """Node 1: Load data based on mode."""
    logger.info("Loading data", mode=state["request"].mode)
    state["data"] = load_data(state["request"])
    return state

def calculate_safety_node(state: AgentState) -> AgentState:
    """Node 2: Calculate safety stock and ROP."""
    data = state["data"]
    avg, std, ss, rop = process_inventory_data(
        data["demand_history"],
        data["lead_time_days"],
        data["service_level"]
    )
    state["safety_params"] = {
        "avg_demand": avg,
        "std_dev": std,
        "safety_stock": ss,
        "reorder_point": rop
    }
    logger.info("Calculated safety params", safety_stock=ss, reorder_point=rop)
    return state

def detect_trigger_node(state: AgentState) -> AgentState:
    """Node 3: Check if restock is needed."""
    current = state["data"]["current_stock"]
    rop = state["safety_params"]["reorder_point"]
    state["needs_restock"] = current < rop
    logger.info("Trigger check", current=current, rop=rop, triggered=state["needs_restock"])
    return state

async def reasoning_node(state: AgentState) -> AgentState:
    """Node 4: LLM reasoning for decision."""
    if not state["needs_restock"]:
        state["recommendation"] = {"action": "none", "quantity": 0, "confidence": 1.0, "reasoning": "Stock above ROP"}
        return state
    
    context = {
        **state["data"],
        **state["safety_params"],
        "shortage": state["safety_params"]["reorder_point"] - state["data"]["current_stock"]
    }
    
    agent = ReasoningAgent()
    state["recommendation"] = await agent.analyze(context)
    logger.info("LLM recommendation", recommendation=state["recommendation"])
    return state

def action_node(state: AgentState) -> AgentState:
    """Node 5: Generate order action."""
    if state["recommendation"]["action"] == "none":
        state["order"] = None
        return state
    
    order = generate_action(state["data"]["product_id"], state["recommendation"])
    state["order"] = order.model_dump()
    return state

def routing_node(state: AgentState) -> AgentState:
    """Node 6: Route based on confidence."""
    confidence = state["recommendation"]["confidence"]
    auto_execute = confidence >= 0.6
    
    status = "executed" if auto_execute else "pending_review"
    if state["recommendation"]["action"] == "none":
        status = "no_action_needed"
    
    record_decision(state["recommendation"]["action"], auto_execute)
    
    state["response"] = InventoryResponse(
        status=status,
        safety_stock=state["safety_params"]["safety_stock"],
        reorder_point=state["safety_params"]["reorder_point"],
        current_stock=state["data"]["current_stock"],
        shortage=max(0, state["safety_params"]["reorder_point"] - state["data"]["current_stock"]),
        recommended_action=state["recommendation"]["action"],
        recommended_quantity=state["recommendation"]["quantity"],
        confidence_score=confidence,
        order=state["order"],
        reasoning=state["recommendation"]["reasoning"]
    )
    return state

# --- Build Workflow ---
workflow = StateGraph(AgentState)
workflow.add_node("load_data", load_data_node)
workflow.add_node("calculate_safety", calculate_safety_node)
workflow.add_node("detect_trigger", detect_trigger_node)
workflow.add_node("reasoning", reasoning_node)
workflow.add_node("action", action_node)
workflow.add_node("routing", routing_node)

workflow.set_entry_point("load_data")
workflow.add_edge("load_data", "calculate_safety")
workflow.add_edge("calculate_safety", "detect_trigger")
workflow.add_edge("detect_trigger", "reasoning")
workflow.add_edge("reasoning", "action")
workflow.add_edge("action", "routing")
workflow.add_edge("routing", END)

graph = workflow.compile()

# --- API Endpoints ---
@app.post("/inventory-trigger", response_model=InventoryResponse)
async def trigger_inventory(request: InventoryRequest):
    """Main endpoint to trigger inventory analysis."""
    with PROCESSING_TIME.time():
        try:
            initial_state = {"request": request}
            result = await graph.ainvoke(initial_state)
            record_request(request.mode, result["response"].status)
            return result["response"]
        except Exception as e:
            logger.error("Processing failed", error=str(e))
            record_request(request.mode, "error")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/{product_id}")
async def debug_product(product_id: str, mode: str = "mock"):
    """Debug endpoint to view calculations."""
    request = InventoryRequest(product_id=product_id, mode=mode)
    data = load_data(request)
    avg, std, ss, rop = process_inventory_data(
        data["demand_history"],
        data["lead_time_days"],
        data["service_level"]
    )
    return {
        "product_id": product_id,
        "mode": mode,
        "calculations": {
            "avg_daily_demand": round(avg, 2),
            "std_dev": round(std, 2),
            "safety_stock": round(ss, 2),
            "reorder_point": round(rop, 2)
        },
        "current_status": {
            "current_stock": data["current_stock"],
            "shortage": round(max(0, rop - data["current_stock"]), 2)
        },
        "would_trigger": data["current_stock"] < rop,
        "trigger_reason": f"current_stock ({data['current_stock']}) < reorder_point ({round(rop)})"
    }

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics()

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}
```

---

### 📅 WEEK 2: Testing + Polish

---

#### Day 1: Unit Tests

| # | Task | File | Tests |
|---|------|------|-------|
| 1 | Data Loader Tests | `tests/test_data_loader.py` | Mock/input loading |
| 2 | Reasoning Agent Tests | `tests/test_reasoning_agent.py` | LLM mocking |
| 3 | Action Agent Tests | `tests/test_action_agent.py` | JSON generation |

---

#### Day 2: Integration Tests

| # | Task | File | Tests |
|---|------|------|-------|
| 1 | Workflow Tests | `tests/test_workflow.py` | Full flow |
| 2 | Mock Mode | `tests/test_workflow.py` | Mock data path |
| 3 | Input Mode | `tests/test_workflow.py` | API input path |
| 4 | Error Scenarios | `tests/test_workflow.py` | Error handling |

---

#### Day 3: Observability

| # | Task | Description |
|---|------|-------------|
| 1 | Verify Logging | Check JSON logs in console |
| 2 | Verify Metrics | Hit `/metrics` endpoint |
| 3 | Add Tracing | Add request IDs to logs |

---

#### Day 4: Documentation

| # | Task | File |
|---|------|------|
| 1 | README | `README.md` |
| 2 | API Examples | Included in README |
| 3 | Deployment Notes | Included in README |

---

#### Day 5: Final Verification

| # | Task | Target |
|---|------|--------|
| 1 | All tests pass | ✅ 100% |
| 2 | Coverage | > 80% |
| 3 | Response time | < 5 seconds |
| 4 | Manual API test | Both modes |
| 5 | Code review | Complete |

---

## 8. Testing Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run safety calculation tests
pytest tests/test_safety_calc.py -v

# Run all agent tests
pytest tests/test_agents.py -v

# Run workflow tests
pytest tests/test_workflow.py -v

# Run ALL tests with coverage
pytest tests/ -v --cov=. --cov-report=term-missing

# Start server
uvicorn main:app --reload

# Test mock mode
curl -X POST http://localhost:8000/inventory-trigger \
  -H "Content-Type: application/json" \
  -d '{"product_id":"STEEL_SHEETS","mode":"mock"}'

# Test input mode
curl -X POST http://localhost:8000/inventory-trigger \
  -H "Content-Type: application/json" \
  -d '{"product_id":"STEEL_SHEETS","mode":"input","current_stock":150,"demand_history":[100,120,110],"lead_time_days":7,"service_level":0.95}'

# Check debug endpoint
curl "http://localhost:8000/debug/STEEL_SHEETS?mode=mock"

# Check metrics
curl http://localhost:8000/metrics
```

---

## 9. Success Criteria Checklist

| Criteria | Target | Verification |
|----------|--------|--------------|
| ✅ Safety stock calculation | Accurate | `pytest tests/test_safety_calc.py` |
| ✅ Mock mode | Working | Manual API test |
| ✅ Input mode | Working | Manual API test |
| ✅ Agent generates valid JSON | PO/Transfer | Check response schema |
| ✅ Confidence routing | ≥0.6 auto, <0.6 review | Check `status` field |
| ✅ Response time | < 5 seconds | Measure with timer |
| ✅ All tests pass | 100% | `pytest tests/` |
| ✅ Test coverage | > 80% | `pytest --cov` |
| ✅ Metrics endpoint | Returns data | `GET /metrics` |

---

## 10. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM rate limits | Medium | High | Implement retry with backoff |
| Bad LLM JSON response | Medium | Medium | Validate + fallback parsing |
| Missing mock data | Low | Medium | Validate CSV on startup |
| Slow response time | Low | High | Cache calculations, async LLM |

---

## 11. Quick Reference Card

### Key Formulas
```
SS = Z × σ × √L          (Safety Stock)
ROP = (D × L) + SS        (Reorder Point)
Trigger: stock < ROP      (When to restock)
Route: confidence ≥ 0.6   (Auto-execute threshold)
```

### Key Endpoints
```
POST /inventory-trigger   → Main workflow
GET  /debug/{product_id}  → View calculations
GET  /metrics             → Prometheus metrics
GET  /health              → Health check
```

### Key Files
```
main.py                   → FastAPI + LangGraph
agents/safety_calculator.py → Core formulas
agents/reasoning_agent.py → Gemini LLM
agents/action_agent.py    → Order generation
```

---

> [!IMPORTANT]
> This PDR is the **single source of truth** for implementation. Follow tasks day-by-day in order. Each day's output should be tested before moving to the next day.
