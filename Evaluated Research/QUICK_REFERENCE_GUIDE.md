
# QUICK REFERENCE: Your Plan vs Best Practice

## Score Summary

| Category | Your Plan | Best Practice | Gap | Priority |
|----------|-----------|---------------|-----|----------|
| **Architecture** | 9/10 | 10/10 | Minor | P2 |
| **Cost Efficiency** | 10/10 | 10/10 | None | - |
| **Risk Management** | 8/10 | 10/10 | Medium | P1 |
| **Observability** | 6/10 | 10/10 | Large | P0 |
| **Security** | 6/10 | 9/10 | Large | P1 |
| **Testing** | 7/10 | 9/10 | Medium | P1 |
| **Documentation** | 9/10 | 9/10 | None | - |
| **OVERALL** | **8.5/10** | **9.6/10** | **Good** | - |

---

## What to Add (Code Snippets)

### 1. Structured Logging (P0 - Must Have)

```python
# requirements.txt
structlog==24.1.0

# main.py
import structlog

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
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage in workflow
logger.info(
    "inventory_decision",
    product_id=state["product_id"],
    action=state["recommended_action"],
    confidence=state["confidence_score"],
    latency_ms=elapsed_time
)
```

---

### 2. Error Handling with Retry (P0 - Must Have)

```python
# utils/retry.py
import functools
import time
import random
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((LLMError, NetworkError))
)
def llm_reasoning_with_retry(state: InventoryState):
    """Retry LLM calls on failure"""
    return reasoning_agent.invoke(state)

# Circuit breaker pattern
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60, expected_exception=LLMError)
def execute_workflow_with_circuit_breaker(state):
    """Circuit breaker for LLM failures"""
    return workflow.invoke(state)

# Fallback decision
async def fallback_decision(request):
    """Rule-based fallback when LLM fails"""
    if request.current_stock < request.safety_stock_level * 0.5:
        return {
            "recommended_action": "restock",
            "recommended_quantity": request.safety_stock_level - request.current_stock,
            "confidence_score": 0.5,
            "fallback": True
        }
    return {
        "recommended_action": "hold",
        "recommended_quantity": 0,
        "confidence_score": 0.5,
        "fallback": True
    }
```

---

### 3. Metrics with Prometheus (P1 - Should Have)

```python
# requirements.txt
prometheus-client==0.19.0

# metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Define metrics
DECISION_LATENCY = Histogram(
    'inventory_decision_latency_seconds',
    'Time taken for inventory decision',
    ['product_id', 'action']
)

CONFIDENCE_SCORE = Gauge(
    'inventory_confidence_score',
    'Confidence score of decision',
    ['product_id']
)

DECISION_COUNT = Counter(
    'inventory_decisions_total',
    'Total decisions made',
    ['action', 'result']
)

ERROR_COUNT = Counter(
    'inventory_errors_total',
    'Total errors',
    ['error_type']
)

# Usage in workflow
@DECISION_LATENCY.time()
def process_decision(state):
    result = workflow.invoke(state)
    CONFIDENCE_SCORE.labels(product_id=state["product_id"]).set(result["confidence_score"])
    DECISION_COUNT.labels(action=result["action"], result="success").inc()
    return result

# FastAPI endpoint for metrics
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

---

### 4. Human Review Notification (P1 - Should Have)

```python
# notifications.py
import aiohttp
from datetime import datetime, timedelta

class HumanReviewNotifier:
    def __init__(self, slack_webhook: str = None, email_service = None):
        self.slack_webhook = slack_webhook
        self.email_service = email_service

    async def notify_low_confidence(self, state: InventoryState, reason: str):
        """Notify when decision needs human review"""
        message = f"""
        ⚠️ *Inventory Decision Requires Review*

        Product: {state['product_id']}
        Current Stock: {state['current_stock']}
        Safety Level: {state['safety_stock_level']}
        Recommended Action: {state['recommended_action']}
        Confidence: {state['confidence_score']:.2f}
        Reason: {reason}

        [Approve] [Reject] [Modify]
        """

        if self.slack_webhook:
            await self._send_slack(message)

        # Store in DB for dashboard
        await self._create_review_ticket(state, reason)

    async def _send_slack(self, message: str):
        async with aiohttp.ClientSession() as session:
            await session.post(self.slack_webhook, json={"text": message})

    async def _create_review_ticket(self, state: InventoryState, reason: str):
        """Create review ticket in database"""
        conn = sqlite3.connect("inventory.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO review_queue 
            (workflow_id, product_id, state_json, reason, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            state.get("thread_id"),
            state["product_id"],
            json.dumps(state),
            reason,
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=4)
        ))
        conn.commit()
        conn.close()

# Usage in workflow
def route_based_on_confidence(state: InventoryState) -> str:
    confidence = state["forecast_confidence"]

    if confidence < 0.60:
        # Notify and pause
        await notifier.notify_low_confidence(state, f"Low confidence: {confidence}")
        return "awaiting_human_review"

    return "generate_action"

# Resume endpoint
@app.post("/approve/{workflow_id}")
async def approve_decision(workflow_id: str, approval: ApprovalRequest):
    """Human approves/rejects pending decision"""
    # Resume workflow
    result = await workflow.ainvoke(
        None,
        config={"configurable": {"thread_id": workflow_id}},
        input={"human_decision": approval.decision}
    )
    return result
```

---

### 5. API Security (P1 - Should Have)

```python
# security.py
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# API Key authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Verify API key"""
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return api_key

# Apply to endpoints
@app.post("/inventory-trigger")
@limiter.limit("100/minute")
async def trigger_inventory_decision(
    request: InventoryTriggerRequest,
    api_key: str = Security(verify_api_key)
):
    ...
```

---

### 6. Redis Caching (P2 - Nice to Have)

```python
# cache.py
import redis
import json
import pickle
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cached(ttl_seconds: int = 3600):
    """Cache decorator for expensive operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try cache
            cached = redis_client.get(cache_key)
            if cached:
                return pickle.loads(cached)

            # Execute and cache
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl_seconds, pickle.dumps(result))
            return result
        return wrapper
    return decorator

# Usage
@cached(ttl_seconds=3600)  # 1 hour
def load_demand_forecast(material_id: str) -> pd.DataFrame:
    """Cached demand forecast loading"""
    return pd.read_csv(f"forecasts/{material_id}.csv")
```

---

## Implementation Checklist

### Week 1: Core (As Planned)
- [ ] Project structure
- [ ] Pydantic schemas
- [ ] 6-node LangGraph workflow
- [ ] Basic error handling
- [ ] Unit tests

### Week 2: Production Hardening (ADD THESE)
- [ ] Structured logging (structlog)
- [ ] Error handling with retry
- [ ] Circuit breaker pattern
- [ ] Prometheus metrics
- [ ] Human review notification
- [ ] API authentication
- [ ] Rate limiting

### Week 3: Performance & Scale (Future)
- [ ] Redis caching
- [ ] Load testing
- [ ] PostgreSQL migration guide
- [ ] Documentation
- [ ] Monitoring dashboards

---

## Final Verdict

**Your plan is 85% production-ready.**

**Strongest points:**
1. Excellent LangGraph architecture
2. Cost-conscious model choice
3. Clear modular structure
4. Good documentation

**Add these 4 things for 95% production-ready:**
1. **Structured logging** (2 hours)
2. **Error handling with retry** (4 hours)
3. **Metrics collection** (4 hours)
4. **Human review notification** (4 hours)

**Total additional effort: ~14 hours**
