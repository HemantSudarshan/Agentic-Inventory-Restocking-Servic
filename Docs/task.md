# Agentic Inventory Restocking Service - Task Tracker

## ✅ Planning Phase (Complete)
- [x] Problem analysis
- [x] Research review
- [x] Reviewer feedback incorporated
- [x] Final implementation plan created

---

## Week 1: Core Implementation

### Day 1: Setup + Data Models
- [ ] Create project structure
- [ ] `requirements.txt` - all dependencies
- [ ] `models/schemas.py` - Pydantic models (InventoryRequest, SafetyParams, etc.)
- [ ] `.env.example` - environment template

### Day 2: Data Layer + Safety Calculation
- [ ] `agents/data_loader.py` - mock + input mode handling
- [ ] `agents/safety_calculator.py` - SS, ROP, EOQ formulas
- [ ] `data/mock_inventory.csv` - sample inventory
- [ ] `data/mock_demand.csv` - sample demand history
- [ ] `tests/test_safety_calc.py` - formula validation

### Day 3: Reasoning Agent
- [ ] `agents/reasoning_agent.py` - Gemini LLM integration
- [ ] Prompt templates for restock/transfer decision
- [ ] Test LLM connection

### Day 4: Action Agent + Utils
- [ ] `agents/action_agent.py` - PO/Transfer JSON generation
- [ ] `utils/logging.py` - structlog setup
- [ ] `utils/retry.py` - error handling with tenacity
- [ ] `utils/metrics.py` - Prometheus counters

### Day 5: Main Workflow
- [ ] `main.py` - FastAPI + LangGraph integration
- [ ] Implement 6-node workflow
- [ ] Implement confidence routing
- [ ] Implement mock/input mode switch
- [ ] Test end-to-end flow

---

## Week 2: Testing + Polish

### Day 1: Unit Tests
- [ ] `tests/test_data_loader.py`
- [ ] `tests/test_reasoning_agent.py`
- [ ] `tests/test_action_agent.py`

### Day 2: Integration Tests
- [ ] `tests/test_workflow.py` - full flow tests
- [ ] Test mock mode
- [ ] Test input mode
- [ ] Test error scenarios

### Day 3: Observability
- [ ] Verify structured logging works
- [ ] Verify /metrics endpoint
- [ ] Add request tracing

### Day 4: Documentation
- [ ] `README.md` - setup + usage guide
- [ ] API examples for both modes
- [ ] Deployment notes

### Day 5: Final Verification
- [ ] All tests pass (>80% coverage)
- [ ] Response time <5 seconds
- [ ] Manual API testing
- [ ] Code review + cleanup

---

## Success Criteria
| Criteria | Target |
|----------|--------|
| Tests passing | 100% |
| Coverage | >80% |
| Response time | <5s |
| Mock mode | Working |
| Input mode | Working |
| Safety calc | Accurate |
| Confidence routing | Working |
