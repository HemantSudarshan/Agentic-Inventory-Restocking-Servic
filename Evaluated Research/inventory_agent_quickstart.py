"""
Quick-Start Implementation: Intelligent Inventory Agent
======================================================
This is a complete, runnable implementation based on the research findings.
Copy this file to start building your inventory agent.
"""

# ============ REQUIREMENTS ============
"""
pip install langgraph langchain langchain-openai pandas prophet sqlite3
"""

import os
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import TypedDict, Optional, Literal
from scipy import stats

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Set your API key
os.environ["OPENAI_API_KEY"] = "your-api-key-here"

# ============ STATE SCHEMA ============

class InventoryState(TypedDict):
    """State schema for the inventory agent workflow"""
    # Inputs
    material_id: str
    material_name: str
    current_stock: int
    safety_threshold: int

    # Retrieved data
    demand_forecast: Optional[pd.DataFrame]
    warehouse_inventory: Optional[dict]

    # Analysis results
    demand_trend: Optional[Literal["increasing", "declining", "stable"]]
    forecast_confidence: float
    shortage_risk: bool

    # Inventory metrics
    safety_stock: Optional[int]
    reorder_point: Optional[int]
    eoq: Optional[int]

    # Decision
    recommended_action: Optional[Literal["restock", "transfer", "hold"]]
    recommended_quantity: Optional[int]
    source_warehouse: Optional[str]

    # Output
    purchase_order: Optional[dict]
    transfer_order: Optional[dict]
    execution_status: str
    validation_errors: list
    is_valid: bool

# ============ TOOLS ============

@tool
def query_current_inventory(material_id: str) -> dict:
    """Query current inventory levels for a material"""
    # Mock implementation - replace with actual DB query
    mock_data = {
        "STEEL_SHEETS": {"current_stock": 150, "reserved_stock": 50, "available_stock": 100},
        "ALUMINUM_BARS": {"current_stock": 300, "reserved_stock": 100, "available_stock": 200},
    }
    return mock_data.get(material_id, {"current_stock": 0, "reserved_stock": 0, "available_stock": 0})

@tool
def load_demand_forecast(material_id: str) -> pd.DataFrame:
    """Load demand forecast from CSV/Database"""
    # Mock implementation - generate synthetic forecast
    dates = pd.date_range(start=datetime.now(), periods=90, freq='D')
    base_demand = 50 if material_id == "STEEL_SHEETS" else 30

    # Add trend and seasonality
    trend = np.linspace(0, 20, 90)
    seasonal = 10 * np.sin(2 * np.pi * np.arange(90) / 7)
    noise = np.random.normal(0, 5, 90)

    demand = base_demand + trend + seasonal + noise
    demand = np.maximum(demand, 0)  # Ensure non-negative

    return pd.DataFrame({
        'date': dates,
        'demand': demand.astype(int)
    })

@tool
def analyze_demand_trend(forecast_df: pd.DataFrame) -> dict:
    """Analyze demand trend using statistical methods"""
    from prophet import Prophet

    # Prepare data for Prophet
    df = forecast_df.rename(columns={'date': 'ds', 'demand': 'y'})

    # Fit model
    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False
    )
    model.fit(df)

    # Predict future
    future = model.make_future_dataframe(periods=30)
    prediction = model.predict(future)

    # Analyze trend
    recent_trend = prediction['trend'].iloc[-30:].mean()
    previous_trend = prediction['trend'].iloc[-60:-30].mean()

    if recent_trend > previous_trend * 1.1:
        trend = "increasing"
    elif recent_trend < previous_trend * 0.9:
        trend = "declining"
    else:
        trend = "stable"

    confidence = min(abs(recent_trend - previous_trend) / previous_trend, 1.0)

    return {
        "trend": trend,
        "confidence": round(confidence, 2),
        "predicted_demand_next_30d": int(prediction['yhat'].iloc[-30:].sum())
    }

@tool
def calculate_inventory_metrics(
    avg_daily_demand: float,
    demand_std: float,
    lead_time_days: int = 7,
    service_level: float = 0.95
) -> dict:
    """Calculate safety stock, reorder point, and EOQ"""

    # Z-score for service level
    z_score = stats.norm.ppf(service_level)

    # Safety Stock: SS = Z * σ_d * sqrt(L)
    safety_stock = z_score * demand_std * np.sqrt(lead_time_days)

    # Reorder Point: ROP = (avg_demand * L) + safety_stock
    reorder_point = (avg_daily_demand * lead_time_days) + safety_stock

    # EOQ: sqrt((2 * D * S) / H)
    annual_demand = avg_daily_demand * 365
    ordering_cost = 100  # Fixed cost per order
    unit_cost = 10  # Cost per unit
    holding_cost_rate = 0.20  # 20% annual holding cost
    holding_cost = unit_cost * holding_cost_rate

    eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost)

    return {
        "safety_stock": int(safety_stock),
        "reorder_point": int(reorder_point),
        "eoq": int(eoq),
        "service_level": service_level
    }

@tool
def find_transfer_source(material_id: str, required_qty: int) -> Optional[str]:
    """Find warehouse with excess stock for transfer"""
    # Mock implementation
    warehouses = {
        "WAREHOUSE_A": {"STEEL_SHEETS": 500, "ALUMINUM_BARS": 200},
        "WAREHOUSE_B": {"STEEL_SHEETS": 100, "ALUMINUM_BARS": 400},
        "WAREHOUSE_C": {"STEEL_SHEETS": 800, "ALUMINUM_BARS": 100},
    }

    for warehouse_id, inventory in warehouses.items():
        available = inventory.get(material_id, 0)
        if available > required_qty + 100:  # Buffer
            return warehouse_id

    return None

@tool
def generate_purchase_order_payload(
    material_id: str,
    material_name: str,
    quantity: int,
    priority: str = "normal"
) -> dict:
    """Generate structured Purchase Order JSON payload"""

    po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{material_id}"

    return {
        "po_number": po_number,
        "type": "purchase_order",
        "status": "draft",
        "priority": priority,
        "items": [{
            "line_number": 1,
            "material_id": material_id,
            "material_name": material_name,
            "quantity": quantity,
            "unit": "units",
            "required_by": (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        }],
        "created_at": datetime.utcnow().isoformat(),
        "approval_workflow": "pending"
    }

@tool
def generate_transfer_order_payload(
    material_id: str,
    material_name: str,
    quantity: int,
    source_warehouse: str,
    destination_warehouse: str = "MAIN"
) -> dict:
    """Generate Stock Transfer Order JSON payload"""

    to_number = f"TO-{datetime.now().strftime('%Y%m%d')}-{material_id}"

    return {
        "to_number": to_number,
        "type": "transfer_order",
        "status": "draft",
        "material_id": material_id,
        "material_name": material_name,
        "quantity": quantity,
        "source_warehouse": source_warehouse,
        "destination_warehouse": destination_warehouse,
        "created_at": datetime.utcnow().isoformat(),
        "expected_transfer_date": (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    }

# ============ LLM SETUP ============

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

# ============ NODE IMPLEMENTATIONS ============

def retrieve_data_node(state: InventoryState):
    """Step A: Data Retrieval"""
    material_id = state["material_id"]

    # Query current inventory
    inventory = query_current_inventory.invoke({"material_id": material_id})

    # Load demand forecast
    forecast_df = load_demand_forecast.invoke({"material_id": material_id})

    return {
        "current_stock": inventory["available_stock"],
        "demand_forecast": forecast_df
    }

def analyze_demand_node(state: InventoryState):
    """Step B: Reasoning & Analysis - Part 1"""
    forecast_df = state["demand_forecast"]

    trend_analysis = analyze_demand_trend.invoke({"forecast_df": forecast_df})

    # Determine if shortage is real risk
    current_stock = state["current_stock"]
    safety_threshold = state["safety_threshold"]

    # Smart shortage detection
    if trend_analysis["trend"] == "declining" and current_stock > safety_threshold * 0.5:
        shortage_risk = False
    else:
        shortage_risk = current_stock < safety_threshold

    return {
        "demand_trend": trend_analysis["trend"],
        "forecast_confidence": trend_analysis["confidence"],
        "shortage_risk": shortage_risk
    }

def optimize_inventory_node(state: InventoryState):
    """Step B: Reasoning & Analysis - Part 2"""
    if not state["shortage_risk"]:
        return {
            "recommended_action": "hold",
            "recommended_quantity": 0,
            "safety_stock": 0,
            "reorder_point": 0,
            "eoq": 0
        }

    # Calculate optimal order quantity
    forecast = state["demand_forecast"]
    avg_demand = forecast['demand'].mean()
    demand_std = forecast['demand'].std()

    metrics = calculate_inventory_metrics.invoke({
        "avg_daily_demand": avg_demand,
        "demand_std": demand_std,
        "lead_time_days": 7,
        "service_level": 0.95
    })

    # Check if transfer is possible
    required_qty = max(0, metrics["reorder_point"] - state["current_stock"])
    source_warehouse = find_transfer_source.invoke({
        "material_id": state["material_id"],
        "required_qty": required_qty
    })

    if source_warehouse and required_qty > 0:
        return {
            "recommended_action": "transfer",
            "recommended_quantity": required_qty,
            "source_warehouse": source_warehouse,
            **metrics
        }
    elif required_qty > 0:
        return {
            "recommended_action": "restock",
            "recommended_quantity": max(required_qty, metrics["eoq"]),
            "source_warehouse": None,
            **metrics
        }
    else:
        return {
            "recommended_action": "hold",
            "recommended_quantity": 0,
            **metrics
        }

def assess_risk_node(state: InventoryState):
    """Step B: Reasoning & Analysis - Part 3"""
    confidence = state["forecast_confidence"]

    # Boost confidence if we have transfer option
    if state["recommended_action"] == "transfer":
        confidence = min(confidence + 0.2, 1.0)

    # Reduce confidence if demand is volatile
    forecast = state["demand_forecast"]
    cv = forecast['demand'].std() / forecast['demand'].mean()
    if cv > 0.5:
        confidence *= 0.8

    return {"forecast_confidence": round(confidence, 2)}

def validate_decision_node(state: InventoryState):
    """Step B: Reasoning & Analysis - Part 4"""
    errors = []

    if state["recommended_quantity"] < 0:
        errors.append("Quantity cannot be negative")

    if state["recommended_action"] == "transfer" and not state["source_warehouse"]:
        errors.append("Transfer source not specified")

    if state["recommended_quantity"] > 10000:
        errors.append("Quantity exceeds maximum order limit")

    return {
        "validation_errors": errors,
        "is_valid": len(errors) == 0
    }

def route_based_on_confidence(state: InventoryState) -> str:
    """Conditional routing logic"""
    confidence = state["forecast_confidence"]
    is_valid = state.get("is_valid", True)

    if confidence < 0.60 or not is_valid:
        return "human_review"
    return "generate_action"

def human_review_node(state: InventoryState):
    """Human-in-the-loop checkpoint"""
    return {
        "approval_status": "pending_review",
        "review_reason": f"Low confidence ({state['forecast_confidence']}) or validation errors: {state['validation_errors']}"
    }

def generate_action_node(state: InventoryState):
    """Step C: Action Generation"""
    action = state["recommended_action"]

    if action == "restock":
        po = generate_purchase_order_payload.invoke({
            "material_id": state["material_id"],
            "material_name": state["material_name"],
            "quantity": state["recommended_quantity"],
            "priority": "high" if state["shortage_risk"] else "normal"
        })
        return {
            "purchase_order": po,
            "transfer_order": None,
            "execution_status": "po_generated"
        }

    elif action == "transfer":
        to = generate_transfer_order_payload.invoke({
            "material_id": state["material_id"],
            "material_name": state["material_name"],
            "quantity": state["recommended_quantity"],
            "source_warehouse": state["source_warehouse"]
        })
        return {
            "purchase_order": None,
            "transfer_order": to,
            "execution_status": "transfer_generated"
        }

    else:  # hold
        return {
            "purchase_order": None,
            "transfer_order": None,
            "execution_status": "no_action_required"
        }

# ============ BUILD WORKFLOW ============

def build_inventory_agent():
    """Build and compile the inventory agent workflow"""

    workflow = StateGraph(InventoryState)

    # Add nodes
    workflow.add_node("retrieve_data", retrieve_data_node)
    workflow.add_node("analyze_demand", analyze_demand_node)
    workflow.add_node("optimize_inventory", optimize_inventory_node)
    workflow.add_node("assess_risk", assess_risk_node)
    workflow.add_node("validate_decision", validate_decision_node)
    workflow.add_node("generate_action", generate_action_node)
    workflow.add_node("human_review", human_review_node)

    # Define edges
    workflow.set_entry_point("retrieve_data")
    workflow.add_edge("retrieve_data", "analyze_demand")
    workflow.add_edge("analyze_demand", "optimize_inventory")
    workflow.add_edge("optimize_inventory", "assess_risk")
    workflow.add_edge("assess_risk", "validate_decision")

    # Conditional routing
    workflow.add_conditional_edges(
        "validate_decision",
        route_based_on_confidence,
        {
            "human_review": "human_review",
            "generate_action": "generate_action"
        }
    )

    workflow.add_edge("human_review", "generate_action")
    workflow.add_edge("generate_action", END)

    # Compile with checkpointing
    memory = SqliteSaver.from_conn_string(":memory:")
    return workflow.compile(checkpointer=memory)

# ============ USAGE EXAMPLE ============

def main():
    """Run the inventory agent"""

    # Build agent
    agent = build_inventory_agent()

    # Example: Steel Sheets inventory alert
    initial_state = {
        "material_id": "STEEL_SHEETS",
        "material_name": "Steel Sheets",
        "current_stock": 150,
        "safety_threshold": 200,
        "demand_forecast": None,
        "warehouse_inventory": None,
        "demand_trend": None,
        "forecast_confidence": 0.0,
        "shortage_risk": False,
        "safety_stock": None,
        "reorder_point": None,
        "eoq": None,
        "recommended_action": None,
        "recommended_quantity": None,
        "source_warehouse": None,
        "purchase_order": None,
        "transfer_order": None,
        "execution_status": "pending",
        "validation_errors": [],
        "is_valid": True
    }

    # Run workflow
    config = {"configurable": {"thread_id": "STEEL_SHEETS_001"}}
    result = agent.invoke(initial_state, config)

    # Print results
    print("=" * 60)
    print("INVENTORY AGENT RESULTS")
    print("=" * 60)
    print(f"Material: {result['material_name']} ({result['material_id']})")
    print(f"Current Stock: {result['current_stock']}")
    print(f"Safety Threshold: {result['safety_threshold']}")
    print(f"Shortage Risk: {result['shortage_risk']}")
    print(f"Demand Trend: {result['demand_trend']}")
    print(f"Confidence Score: {result['forecast_confidence']}")
    print(f"Recommended Action: {result['recommended_action']}")
    print(f"Recommended Quantity: {result['recommended_quantity']}")

    if result['purchase_order']:
        print("\n📋 PURCHASE ORDER GENERATED:")
        print(json.dumps(result['purchase_order'], indent=2))

    if result['transfer_order']:
        print("\n🚚 TRANSFER ORDER GENERATED:")
        print(json.dumps(result['transfer_order'], indent=2))

    print(f"\nExecution Status: {result['execution_status']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
