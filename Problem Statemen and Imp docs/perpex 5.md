# ⚡ QUICK REFERENCE CARD
## Intelligent Inventory Management System - One-Page Cheat Sheet

---

## 🎯 YOUR SYSTEM AT A GLANCE

```
INPUT                 PROCESSING              OUTPUT
════════              ══════════              ══════

SQLite          ──→   [TRIGGER]    ──→   PO JSON
Inventory DB         (stock <             or
                      safety)             Transfer
                                          JSON
CSV Demand ──→   [DATA RETRIEVE]  ──→   with cost
Forecast              (avg demand,        estimate
                      trend, forecast)    + confidence
                                  
                ──→   [REASON]     ──→   Auto-exec
                      (LLM decides)       or Manager
                                         approval
                      or Reject
```

---

## 🏗️ 5-NODE WORKFLOW

| Node | Input | Logic | Output | Fail → |
|------|-------|-------|--------|---------|
| **1. Trigger** | SQLite | Detect: stock < safety | Inventory event | Retry |
| **2. Retrieve** | CSV | Load + cache forecast | DemandAnalysis | Reject |
| **3. Reason** | Demand + Stock | LLM: RESTOCK? TRANSFER? | Decision + confidence | Fallback rule |
| **4. Generate** | Decision | Create JSON payload | ActionPayload | Retry |
| **5. Approve** | Confidence | High→Auto, Med→Notify, Low→Reject | Execute or Wait | Alert |

---

## 📊 DECISION MATRIX

```
Confidence    │ Action        │ Cost      │ Approval
──────────────┼───────────────┼───────────┼─────────────
> 0.85        │ AUTO-EXECUTE  │ Minimal   │ None needed
0.7 - 0.85    │ PENDING       │ Moderate  │ Manager webhook
< 0.7         │ REJECT        │ Low       │ Alert only
```

---

## 🔧 TECH STACK (FINAL)

```
├─ Backend:       FastAPI (HTTP server)
├─ Orchestration: LangGraph (state machine)
├─ AI/LLM:        Gemini 2.5 Flash (reasoning)
├─ Data:          Pandas + SQLite (CSV + database)
├─ Language:      Python 3.10+
├─ Frameworks:    Pydantic (validation)
└─ Deployment:    Docker (optional but recommended)
```

---

## 📈 PERFORMANCE TARGETS

| Metric | Target | Cost Impact |
|--------|--------|------------|
| Latency | <5 sec | ✅ Real-time |
| Accuracy | >85% | ✅ Production-grade |
| Cost/decision | <$0.01 | ✅ Scalable |
| Throughput | 100+/min | ✅ Multi-warehouse ready |

---

## 🎓 TOP 3 REPOS TO STUDY

| Rank | Repo | GitHub | Key Learning |
|------|------|--------|--------------|
| #1 | Supply-Chain-Optimization-Agent | Abbas-Asad | Approval workflow |
| #2 | InvAgent | zefang-liu | Zero-shot LLM reasoning |
| #3 | LangGraph Examples | sushmitanandi | Event-driven orchestration |

---

## 🚀 IMPLEMENTATION TIMELINE

```
Week 1    Week 2         Week 3             Week 4+
─────────────────────────────────────────────────
MVP      Testing &      Production        Multi-warehouse
Build    Refinement     Hardening         Scaling
│        │              │                 │
├─ Core  ├─ Unit tests  ├─ Audit log     ├─ Coordinator
│  loop  │ ├─ Integ     │ ├─ Webhooks    │  agent
├─ Nodes │  tests       │ ├─ Monitoring  ├─ Transfer
│        │ ├─ Load test │ └─ Deploy      │  optimization
├─ Data  │ └─ Fallbacks │                ├─ ML feedback
│  load  └─ Docs        └─ Go live       └─ Fine-tuning
└─ LLM
  prompt
```

---

## 📋 PRE-LAUNCH CHECKLIST

- [ ] FastAPI server running locally
- [ ] Inventory polling working (every 5 min)
- [ ] CSV loading + caching tested
- [ ] LLM calls returning decisions
- [ ] JSON payloads validated
- [ ] Approval gate confidence scoring
- [ ] End-to-end workflow tested
- [ ] Error handling + fallbacks in place
- [ ] Monitoring dashboards setup
- [ ] Deployment guide documented

---

## 💡 CRITICAL DECISION POINTS

1. **Confidence Threshold**
   - Current: > 0.85 = auto-execute
   - **Tune based:** Stockout rate vs false positives

2. **Data Refresh Rate**
   - Current: CSV cache = 1 hour
   - **Tune based:** Demand volatility + compute cost

3. **Trigger Frequency**
   - Current: Poll every 5 minutes
   - **Tune based:** Safety stock sensitivity

4. **Approval Workflow**
   - Current: Webhook to manager
   - **Alternative:** Slack, Email, Dashboard

---

## 🔄 DECISION REASONING (What LLM Sees)

```
Current Stock: 150 units
Safety Level:  300 units
Avg Demand:    51.2 units/day
Days Supply:   2.9 days
30-Day Need:   1,536 units
Trend:         Stable
Confidence:    75% (good data)

LLM Decision Tree:
─────────────────
If demand_trend == "increasing":
  └─ RESTOCK (prevent stockout)
  
Elif demand_trend == "declining":
  └─ TRANSFER (excess inventory elsewhere)
  
Else (stable):
  If days_supply < 3:
    └─ RESTOCK (buffer needed)
  Else if days_supply > 7:
    └─ HOLD or TRANSFER
  Else:
    └─ RESTOCK (conservative)
```

---

## 🎯 SUCCESS INDICATORS (Week 4)

✅ System is live and processing triggers  
✅ No stockouts when system was active  
✅ Cost savings >= automation costs  
✅ Manager approval rate < 10% (high confidence)  
✅ Decision accuracy > 85%  
✅ API latency < 5 seconds  
✅ Zero critical errors in logs  

---

## ⚠️ COMMON PITFALLS & FIXES

| Pitfall | Solution |
|---------|----------|
| LLM latency | Use streaming or cache decisions |
| Non-deterministic output | Structured prompts + JSON parsing |
| Demand forecast errors | Add confidence scoring + fallback rules |
| Too many false triggers | Adjust safety stock threshold |
| Manager approval bottleneck | Increase confidence threshold |
| High API costs | Use cheaper models (Gemini Flash) |

---

## 🔗 FILE MAP IN YOUR CODE

```
main.py
├─ @app.post("/inventory-trigger")  ← Entry point
├─ node_receive_trigger()            ← Node 1
├─ node_retrieve_demand_data()       ← Node 2 (calls DataRetrievalAgent)
├─ node_reason_about_shortage()      ← Node 3 (calls ReasoningAgent)
├─ node_generate_action()            ← Node 4 (calls ActionAgent)
├─ node_approval_gate()              ← Node 5
├─ node_execute_action()             ← Node 6
└─ graph = workflow.compile()        ← Orchestration

agents/
├─ retrieval_agent.py   ← Load CSV + cache
├─ reasoning_agent.py   ← LLM decision
└─ action_agent.py      ← JSON generator

models/
└─ schemas.py           ← Pydantic models
```

---

## 🚨 DEBUGGING QUICK TIPS

```bash
# Check if trigger fires
sqlite3 inventory.db "SELECT * WHERE stock < safety_level"

# Test data retrieval
python -c "from agents.retrieval_agent import DataRetrievalAgent; \
           da = DataRetrievalAgent(); \
           print(da.load_forecast('STEEL_001'))"

# Test LLM connection
python -c "from langchain_google_generativeai import ChatGoogleGenerativeAI; \
           m = ChatGoogleGenerativeAI(model='gemini-2.5-flash'); \
           print(m.invoke('hello'))"

# Test full workflow
curl -X POST http://localhost:8000/inventory-trigger \
  -H "Content-Type: application/json" \
  -d '{"product_id":"STEEL_001","warehouse_id":"WH_BLR","current_stock":150,...}'

# Check logs
tail -f /var/log/inventory-agent.log
```

---

## 📞 QUICK DECISION TABLE

**Q: Which framework?**
- Event-driven → LangGraph ✅
- Ease of use → CrewAI
- Conversational → AutoGen

**Q: Which LLM?**
- Cost-efficient → Gemini Flash ✅
- Best reasoning → GPT-4o-mini
- Local deployment → Llama 3

**Q: Approval strategy?**
- No oversight → Full auto (risky)
- Balanced → Confidence gates ✅
- High control → All manual (slow)

**Q: Data source?**
- CSV (simple) ✅
- Database (scalable)
- API (real-time)

---

## 📊 SAMPLE RESPONSES (What Success Looks Like)

```json
// High Confidence Auto-Execute
{
  "status": "executed",
  "decision": "restock",
  "confidence": 0.92,
  "action": "purchase_order",
  "quantity": 2000,
  "cost_estimate": 20000,
  "reasoning": "Demand increasing, stock only 3 days"
}

// Medium Confidence Pending Approval
{
  "status": "pending_approval",
  "decision": "transfer",
  "confidence": 0.76,
  "action": "stock_transfer",
  "from_warehouse": "WH_MUMBAI",
  "to_warehouse": "WH_BANGALORE",
  "cost_estimate": 1000,
  "webhook_sent": true,
  "manager_notified": "manager@company.com"
}

// Low Confidence Rejection
{
  "status": "rejected",
  "decision": "uncertain",
  "confidence": 0.54,
  "error": "Insufficient data for reliable decision",
  "recommendation": "Manual review recommended",
  "alert_sent": true
}
```

---

## 🎉 YOU'RE READY!

This quick reference has everything for quick lookups.  
Keep it bookmarked. Print it out for your team.

**For detailed info:** See full documentation in main README.md

**To start coding:** Open production_code_example.md

**To understand architecture:** Read inventory_arch_design.md

---

*Last Updated: Feb 4, 2026*  
*Bookmark this for quick reference during implementation* 📌